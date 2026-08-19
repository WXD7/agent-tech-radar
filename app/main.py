import secrets
from collections import Counter
from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from radar.anchors import archive_anchor, create_anchor
from radar.conversations import create_conversation_source
from radar.documents import (
    document_section_text,
    load_document_text,
    parse_document_outline,
    render_markdown,
)
from radar.indexing import rebuild_index
from radar.maps import (
    active_maps,
    add_node_to_map,
    graph_view,
    map_for_document,
    map_for_node,
    resolve_map,
)
from radar.models import Catalog
from radar.nodes import archive_node, create_node, restore_node, update_node
from radar.paths import PROJECT_ROOT
from radar.review import decide_proposal
from radar.store import load_catalog


APP_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Agent 技术雷达",
    description="持续发现、验证和审核 Agent 开发技术。",
    version="1.1.0",
)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")
APP_PROJECT_ROOT = PROJECT_ROOT

NODE_TYPE_LABELS = {
    "concept": "概念",
    "question": "追问",
    "challenge": "质疑",
    "answer": "回答",
    "note": "笔记",
}
RELATION_LABELS = {
    "relates_to": "关联",
    "questions": "追问",
    "challenges": "质疑",
    "answers": "回答",
    "extends": "补充",
    "corrects": "校正",
}
DEFAULT_RELATIONS = {
    "concept": "relates_to",
    "question": "questions",
    "challenge": "challenges",
    "answer": "answers",
    "note": "extends",
}
SOURCE_KIND_LABELS = {
    "manual": "手写笔记",
    "codex_conversation": "Codex 会话提炼",
    "automated_research": "自动研究",
}
VERIFICATION_LABELS = {
    "unverified": "待查证",
    "researching": "查证中",
    "partially_verified": "部分证实",
    "verified": "已查证",
    "contested": "存在争议",
}
VISIBILITY_LABELS = {"private": "仅本机", "shared": "可共享"}
ANCHOR_KIND_LABELS = {
    "question_context": "当时的问题",
    "answer_basis": "形成认识的回答",
    "correction": "纠正与反驳",
    "decision_context": "决策上下文",
}
ROLE_LABELS = {"user": "我", "assistant": "Codex"}
DOCUMENT_KIND_LABELS = {
    "research_note": "研究文档",
    "architecture_note": "架构文档",
    "decision_record": "决策记录",
}
DOCUMENT_VERIFICATION_LABELS = {
    **VERIFICATION_LABELS,
    "mixed": "分层查证",
}


def _catalog() -> Catalog:
    catalog = load_catalog(APP_PROJECT_ROOT)
    rebuild_index(catalog, APP_PROJECT_ROOT / ".radar" / "radar.db")
    return catalog


def _context(request: Request, page: str, catalog: Catalog, **extra: object) -> dict:
    return {
        "request": request,
        "page": page,
        "pending_count": sum(item.status == "pending" for item in catalog.proposals),
        **extra,
    }


def _csrf_token(request: Request) -> str:
    return request.cookies.get("radar_csrf") or secrets.token_urlsafe(32)


def _set_csrf_cookie(response: HTMLResponse, token: str) -> HTMLResponse:
    response.set_cookie(
        "radar_csrf",
        token,
        httponly=True,
        samesite="strict",
        secure=False,
    )
    return response


def _check_csrf(request: Request, csrf_token: str) -> None:
    cookie_token = request.cookies.get("radar_csrf") or ""
    if not cookie_token or not secrets.compare_digest(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid form token")


def _target_options(catalog: Catalog) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    options.extend(
        {"id": item.id, "label": item.name, "type": "技术"}
        for item in catalog.technologies
    )
    options.extend(
        {"id": item.id, "label": item.name, "type": "候选技术"}
        for item in catalog.discovery_candidates
        if item.status == "triaged" and not item.archived
    )
    options.extend(
        {"id": item.id, "label": item.name, "type": "能力"}
        for item in catalog.capabilities
    )
    options.extend(
        {"id": item.id, "label": item.text, "type": "结论"}
        for item in catalog.claims
    )
    options.extend(
        {"id": item.id, "label": item.title, "type": "证据"}
        for item in catalog.evidence
    )
    options.extend(
        {"id": item.id, "label": item.name, "type": "实验"}
        for item in catalog.experiments
    )
    options.extend(
        {"id": item.id, "label": item.title, "type": NODE_TYPE_LABELS[item.node_type]}
        for item in catalog.knowledge_nodes
        if item.status != "archived"
    )
    options.extend(
        {"id": item.id, "label": item.title, "type": "研究文档"}
        for item in catalog.research_documents
        if item.status != "archived"
    )
    return options


def _target_map(catalog: Catalog) -> dict[str, dict[str, str]]:
    return {item["id"]: item for item in _target_options(catalog)}


def _knowledge_options(catalog: Catalog, exclude_id: str | None = None) -> list[dict[str, str]]:
    return [
        {"id": item.id, "label": item.title}
        for item in catalog.knowledge_nodes
        if item.status != "archived" and item.id != exclude_id
    ]


def _validate_links(
    catalog: Catalog,
    target_id: str,
    parent_id: str | None,
    current_id: str | None = None,
) -> None:
    if target_id not in _target_map(catalog):
        raise HTTPException(status_code=400, detail="关联目标不存在或已归档。")
    if current_id and (target_id == current_id or parent_id == current_id):
        raise HTTPException(status_code=400, detail="节点不能关联自己。")
    if parent_id:
        parent = catalog.knowledge_node(parent_id)
        if parent is None or parent.status == "archived":
            raise HTTPException(status_code=400, detail="上一层知识节点不存在或已归档。")
        seen: set[str] = set()
        while parent and parent.id not in seen:
            if parent.id == current_id:
                raise HTTPException(status_code=400, detail="这会产生循环知识链。")
            seen.add(parent.id)
            parent = catalog.knowledge_node(parent.parent_id) if parent.parent_id else None


def _validate_node_fields(node_type: str, status: str, relation_type: str) -> None:
    if node_type not in NODE_TYPE_LABELS:
        raise HTTPException(status_code=400, detail="未知的知识节点类型。")
    if status not in {"open", "active", "resolved"}:
        raise HTTPException(status_code=400, detail="未知的节点状态。")
    if relation_type not in RELATION_LABELS:
        raise HTTPException(status_code=400, detail="未知的关系类型。")


def _validate_provenance(
    catalog: Catalog,
    source_kind: str,
    verification_status: str,
    conversation_source_ids: list[str],
    evidence_ids: list[str],
) -> None:
    if source_kind not in SOURCE_KIND_LABELS:
        raise HTTPException(status_code=400, detail="未知的笔记来源。")
    if verification_status not in VERIFICATION_LABELS:
        raise HTTPException(status_code=400, detail="未知的查证状态。")
    unknown_conversations = [
        item for item in conversation_source_ids if catalog.conversation_source(item) is None
    ]
    if unknown_conversations:
        raise HTTPException(status_code=400, detail="关联的 Codex 会话不存在。")
    unknown_evidence = [
        item for item in evidence_ids if catalog.evidence_item(item) is None
    ]
    if unknown_evidence:
        raise HTTPException(status_code=400, detail="关联的外部证据不存在。")
    if source_kind == "codex_conversation" and not conversation_source_ids:
        raise HTTPException(status_code=400, detail="会话提炼笔记至少要关联一个 Codex 会话。")


def _absolute_page_url(request: Request, path: str) -> str:
    return str(request.base_url).rstrip("/") + path


def _codex_new_url(prompt: str, browser_url: str) -> str:
    query = urlencode(
        {
            "prompt": prompt,
            "path": str(APP_PROJECT_ROOT),
            "browserUrl": browser_url,
        },
        quote_via=quote,
    )
    return f"codex://new?{query}"


def _codex_thread_url(thread_id: str, prompt: str, browser_url: str) -> str:
    query = urlencode(
        {"prompt": prompt, "browserUrl": browser_url},
        quote_via=quote,
    )
    return f"codex://threads/{thread_id}?{query}"


def _conversation_sync_prompt(source_id: str) -> str:
    return (
        "请把当前 Codex 会话同步到 Agent Radar。"
        f"项目目录是 {APP_PROJECT_ROOT}，会话来源 ID 是 {source_id}。"
        "请使用 sync-agent-radar 技能，但把一篇连贯、可阅读、可持续修订的 Markdown "
        "研究文档作为默认产物，不要把每个观点机械拆成独立图谱节点。"
        "文档至少根据内容组织一页结论、概念/技术分层、核心方案深入解释、"
        "横向比较、证据权重、风险与边界、PoC/实验、实施路线和一手资料索引。"
        "新认识应补充、修正或反驳原文档的对应章节，不要覆盖历史。"
        "只有尚未能合理放入文档结构的临时疑问，才作为 knowledge/nodes/private/ 认知片段。"
        "把需要外部确认的内容标成待查证，并优先查官方文档、官方仓库、"
        "版本发布说明或可重复实验。不要把 AI 回答本身当作事实证据，"
        "也不要直接改写已审核的 claims/decisions。"
        "私人会话文档默认保存到 knowledge/documents/private/ 并设为 visibility: private。"
        "完成后更新 knowledge/conversations/、knowledge/documents/private/ 及所属专题图谱，再简要说明新增、"
        "修正和仍有争议的内容。"
    )


def _document_research_prompt(
    document_title: str,
    document_id: str,
    section_title: str | None,
    section_text: str | None,
) -> str:
    focus = f"，重点是章节《{section_title}》" if section_title else ""
    excerpt = f"\n当前章节原文：\n{section_text[:6000]}\n" if section_text else ""
    return (
        f"请继续研究 Agent Radar 中的文档《{document_title}》（ID: {document_id}）{focus}。"
        f"{excerpt}项目目录是 {APP_PROJECT_ROOT}。"
        "请先阅读完整文档及相关上下文，再进行追问、质疑、查源或实验。"
        "本次的默认写回单位是文档章节：新结果应补充、修正或反驳对应段落，"
        "并保留修订历史与 Codex 会话来源；不要把回答拆成一批仅有标题的孤立节点。"
        "外部技术断言必须区分官方证据、社区经验、AI 推断、实验结果与人工决策；"
        "无法证实的内容保持待查证或争议状态。"
    )


def _research_prompt(
    target: dict[str, str],
    node_body: str | None = None,
    anchor_excerpts: list[str] | None = None,
) -> str:
    context = ""
    if node_body:
        context += f"\n当前笔记摘要：{node_body}"
    if anchor_excerpts:
        context += "\n形成这条认识的会话片段：\n- " + "\n- ".join(anchor_excerpts[:4])
    return (
        "请围绕 Agent Radar 中的这个对象继续研究："
        f"[{target['type']}] {target['label']}（ID: {target['id']}）。"
        f"{context}"
        f"项目目录是 {APP_PROJECT_ROOT}。先阅读该对象及相邻结论、证据和笔记，"
        "明确这次最值得回答的问题；再使用官方文档、官方仓库、发布说明、论文"
        "或最小可重复实验进行二次查证。把会话中的学习过程提炼为"
        " knowledge/nodes/ 笔记；本次交接没有已登记的会话来源 ID，因此先标记"
        " source_kind: automated_research，绝不要编造 conversation_source_ids。"
        "无法证实的内容保持为"
        "待查证或争议项；如需改变正式结论，只生成 proposal，不要直接改 claims。"
    )


def _anchor_continue_prompt(node_title: str, excerpt: str) -> str:
    return (
        f"我想继续追问 Agent Radar 中的知识点《{node_title}》。\n"
        f"当时形成这条认识的会话片段是：\n{excerpt}\n\n"
        "请先判断我这次最值得追问、质疑或查证的部分，再继续讨论。"
        f"项目目录是 {APP_PROJECT_ROOT}。讨论结束后，在我确认时把新增认识同步回 Radar；"
        "保留为新的补充、纠正或反驳节点，不要覆盖历史，也不要把 AI 回答当成事实证据。"
    )


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    catalog = _catalog()
    supported_claims = sum(item.status == "supported" for item in catalog.claims)
    pending = [item for item in catalog.proposals if item.status == "pending"]
    changes = sorted(catalog.changes, key=lambda item: item.detected_at, reverse=True)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=_context(
            request,
            "dashboard",
            catalog,
            stats=[
                {"label": "已见过技术", "value": len(catalog.technologies) + len(catalog.discovery_candidates), "delta": "已评估与待评估分层保存"},
                {"label": "研究文档", "value": len(catalog.research_documents), "delta": f"保留 {len(catalog.knowledge_nodes)} 条认知片段"},
                {"label": "已支持结论", "value": supported_claims, "delta": f"共 {len(catalog.claims)} 条正式结论"},
                {"label": "等待审核", "value": len(pending), "delta": "Codex 不能静默发布"},
            ],
            changes=changes[:3],
            pending=pending[:2],
            experiments=catalog.experiments,
        ),
    )


@app.get("/graph", response_class=HTMLResponse)
def graph(request: Request, map_id: str | None = None) -> HTMLResponse:
    catalog = _catalog()
    try:
        selected_map = resolve_map(catalog, map_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Knowledge map not found") from exc
    view = graph_view(catalog, selected_map, APP_PROJECT_ROOT)
    return templates.TemplateResponse(
        request=request,
        name="graph.html",
        context=_context(
            request,
            "graph",
            catalog,
            node_counts=view["node_counts"],
            graph_metrics=view["metrics"],
            selected_map=selected_map,
            knowledge_maps=active_maps(catalog),
        ),
    )


@app.get("/discovery", response_class=HTMLResponse)
def discovery(request: Request) -> HTMLResponse:
    catalog = _catalog()
    candidates = catalog.discovery_candidates
    triaged = [
        item for item in candidates if item.status == "triaged" and not item.archived
    ]
    excluded = [item for item in candidates if item.status == "excluded"]
    unreviewed = [item for item in candidates if item.status == "discovered"]
    query_map = {item.id: item for item in catalog.discovery_queries}
    category_groups = []
    covered_category_ids: set[str] = set()
    for category in catalog.discovery_categories:
        matches = [item for item in triaged if category.id in item.category_ids]
        if matches:
            covered_category_ids.add(category.id)
        category_groups.append(
            {
                "category": category,
                "candidates": sorted(
                    matches,
                    key=lambda item: (item.github_stars, item.github_forks),
                    reverse=True,
                ),
            }
        )

    ecosystem_counts = Counter(item.ecosystem for item in triaged)
    candidate_anchor_category = {
        item.id: item.category_ids[0] for item in triaged if item.category_ids
    }
    recent_runs = sorted(
        catalog.discovery_runs,
        key=lambda item: item.completed_at,
        reverse=True,
    )[:3]
    saturation_round_count = 0
    for run in recent_runs:
        if run.new_unique_rate >= 0.05 or run.incomplete_query_ids:
            break
        saturation_round_count += 1
    return templates.TemplateResponse(
        request=request,
        name="discovery.html",
        context=_context(
            request,
            "discovery",
            catalog,
            stats=[
                {
                    "label": "已评估技术",
                    "value": len(catalog.technologies),
                    "note": "已经进入结论与证据层",
                },
                {
                    "label": "待评估候选",
                    "value": len(triaged),
                    "note": "进入图谱，但不冒充结论",
                },
                {
                    "label": "已见过总数",
                    "value": len(catalog.technologies) + len(candidates),
                    "note": f"含 {len(excluded)} 个已排除项目",
                },
                {
                    "label": "发现查询族",
                    "value": len(catalog.discovery_queries),
                    "note": f"覆盖 {len(covered_category_ids)}/{len(catalog.discovery_categories)} 类",
                },
            ],
            category_groups=category_groups,
            covered_category_ids=covered_category_ids,
            sources=catalog.discovery_sources,
            queries=catalog.discovery_queries,
            query_map=query_map,
            candidate_anchor_category=candidate_anchor_category,
            excluded=excluded,
            unreviewed=unreviewed,
            ecosystem_counts=ecosystem_counts.most_common(),
            active_source_count=sum(
                item.status == "active" for item in catalog.discovery_sources
            ),
            recent_runs=recent_runs,
            saturation_round_count=saturation_round_count,
            is_saturated=saturation_round_count == 3,
        ),
    )


@app.get("/api/graph")
def graph_api(map_id: str | None = None) -> dict:
    catalog = _catalog()
    try:
        selected_map = resolve_map(catalog, map_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Knowledge map not found") from exc
    return graph_view(catalog, selected_map, APP_PROJECT_ROOT)


@app.get("/api/documents/{document_id}/preview")
def document_preview(document_id: str, section: str | None = None) -> dict:
    catalog = _catalog()
    document = catalog.research_document(document_id)
    if document is None or document.status == "archived":
        raise HTTPException(status_code=404, detail="Research document not found")
    try:
        text = load_document_text(document, APP_PROJECT_ROOT)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Document content not found") from exc
    outline = parse_document_outline(text)
    section_item = next((item for item in outline if item.anchor == section), None)
    if section and section_item is None:
        raise HTTPException(status_code=404, detail="Document section not found")
    suffix = f"#{section}" if section else ""
    return {
        "id": document.id,
        "title": document.title,
        "summary": document.summary,
        "verification_label": DOCUMENT_VERIFICATION_LABELS[
            document.verification_status
        ],
        "visibility_label": VISIBILITY_LABELS[document.visibility],
        "section": section,
        "section_title": section_item.title if section_item else None,
        "html": str(render_markdown(text)),
        "full_href": f"/documents/{document.id}{suffix}",
        "research_href": (
            f"/documents/{document.id}/research?section={section}"
            if section
            else f"/documents/{document.id}/research"
        ),
    }


@app.get("/technologies/{technology_id}", response_class=HTMLResponse)
def technology_detail(request: Request, technology_id: str) -> HTMLResponse:
    catalog = _catalog()
    technology = catalog.technology(technology_id)
    if technology is None:
        raise HTTPException(status_code=404, detail="Technology not found")

    claims = [item for item in catalog.claims if item.technology_id == technology_id]
    claim_evidence = {
        claim.id: [item for item in catalog.evidence if item.id in claim.evidence_ids]
        for claim in claims
    }
    capabilities = [item for item in catalog.capabilities if item.id in technology.capability_ids]
    changes = [item for item in catalog.changes if item.technology_id == technology_id]
    return templates.TemplateResponse(
        request=request,
        name="technology.html",
        context=_context(
            request,
            "graph",
            catalog,
            technology=technology,
            claims=claims,
            claim_evidence=claim_evidence,
            capabilities=capabilities,
            changes=changes,
            popularity=catalog.popularity(technology_id),
        ),
    )


@app.get("/documents", response_class=HTMLResponse)
def documents(request: Request) -> HTMLResponse:
    catalog = _catalog()
    active_documents = sorted(
        (
            item
            for item in catalog.research_documents
            if item.status != "archived"
        ),
        key=lambda item: item.updated_at,
        reverse=True,
    )
    source_map = {item.id: item for item in catalog.conversation_sources}
    return templates.TemplateResponse(
        request=request,
        name="documents.html",
        context=_context(
            request,
            "documents",
            catalog,
            documents=active_documents,
            source_map=source_map,
            document_kind_labels=DOCUMENT_KIND_LABELS,
            verification_labels=DOCUMENT_VERIFICATION_LABELS,
            visibility_labels=VISIBILITY_LABELS,
        ),
    )


@app.get("/documents/{document_id}", response_class=HTMLResponse)
def document_detail(request: Request, document_id: str) -> HTMLResponse:
    catalog = _catalog()
    document = catalog.research_document(document_id)
    if document is None or document.status == "archived":
        raise HTTPException(status_code=404, detail="Research document not found")
    try:
        text = load_document_text(document, APP_PROJECT_ROOT)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Document content not found") from exc
    outline = parse_document_outline(text)
    sources = [
        item
        for item in catalog.conversation_sources
        if item.id in document.conversation_source_ids
    ]
    target_map = _target_map(catalog)
    related_targets = [
        target_map[target_id]
        for target_id in [*document.technology_ids, *document.capability_ids]
        if target_id in target_map
    ]
    selected_map = map_for_document(catalog, document)
    return templates.TemplateResponse(
        request=request,
        name="document_detail.html",
        context=_context(
            request,
            "documents",
            catalog,
            document=document,
            rendered_document=render_markdown(text),
            outline=[item for item in outline if item.level in {2, 3}],
            chapter_count=sum(item.level == 2 for item in outline),
            character_count=len(text),
            conversation_sources=sources,
            related_targets=related_targets,
            selected_map=selected_map,
            document_kind_labels=DOCUMENT_KIND_LABELS,
            verification_labels=DOCUMENT_VERIFICATION_LABELS,
            visibility_labels=VISIBILITY_LABELS,
        ),
    )


@app.get("/documents/{document_id}/research", response_class=HTMLResponse)
def document_research(
    request: Request,
    document_id: str,
    section: str | None = None,
) -> HTMLResponse:
    catalog = _catalog()
    document = catalog.research_document(document_id)
    if document is None or document.status == "archived":
        raise HTTPException(status_code=404, detail="Research document not found")
    try:
        text = load_document_text(document, APP_PROJECT_ROOT)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Document content not found") from exc
    section_title = None
    section_text = None
    if section:
        try:
            section_item, section_text = document_section_text(text, section)
            section_title = section_item.title
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Document section not found") from exc
    prompt = _document_research_prompt(
        document.title,
        document.id,
        section_title,
        section_text,
    )
    suffix = f"#{section}" if section else ""
    browser_url = _absolute_page_url(request, f"/documents/{document.id}{suffix}")
    target = {
        "id": document.id,
        "label": section_title or document.title,
        "type": "文档章节" if section_title else "研究文档",
    }
    return templates.TemplateResponse(
        request=request,
        name="research_launch.html",
        context=_context(
            request,
            "documents",
            catalog,
            target=target,
            prompt=prompt,
            codex_url=_codex_new_url(prompt, browser_url),
            back_url=f"/documents/{document.id}{suffix}",
            handoff_note="新认识将优先更新这篇文档的对应章节，而不是生成一批孤立标题节点。",
        ),
    )


@app.get("/nodes", response_class=HTMLResponse)
def nodes(request: Request) -> HTMLResponse:
    catalog = _catalog()
    active = sorted(
        (item for item in catalog.knowledge_nodes if item.status != "archived"),
        key=lambda item: item.updated_at,
        reverse=True,
    )
    archived = sorted(
        (item for item in catalog.knowledge_nodes if item.status == "archived"),
        key=lambda item: item.updated_at,
        reverse=True,
    )
    return templates.TemplateResponse(
        request=request,
        name="nodes.html",
        context=_context(
            request,
            "nodes",
            catalog,
            active_nodes=active,
            archived_nodes=archived,
            node_type_labels=NODE_TYPE_LABELS,
            source_kind_labels=SOURCE_KIND_LABELS,
            verification_labels=VERIFICATION_LABELS,
            visibility_labels=VISIBILITY_LABELS,
            target_map=_target_map(catalog),
            conversation_sources=sorted(
                catalog.conversation_sources,
                key=lambda item: item.updated_at,
                reverse=True,
            ),
            conversation_note_count=sum(
                item.source_kind == "codex_conversation"
                for item in catalog.knowledge_nodes
            ),
            research_note_count=sum(
                item.source_kind == "automated_research"
                for item in catalog.knowledge_nodes
            ),
        ),
    )


@app.get("/conversations/import", response_class=HTMLResponse)
def conversation_import(request: Request) -> HTMLResponse:
    catalog = _catalog()
    csrf_token = _csrf_token(request)
    response = templates.TemplateResponse(
        request=request,
        name="conversation_import.html",
        context=_context(
            request,
            "nodes",
            catalog,
            csrf_token=csrf_token,
            error=None,
            values={"title": "", "thread_reference": ""},
        ),
    )
    return _set_csrf_cookie(response, csrf_token)


@app.post("/conversations/import", response_class=HTMLResponse)
def conversation_import_create(
    request: Request,
    csrf_token: str = Form(...),
    title: str = Form(..., min_length=2, max_length=160),
    thread_reference: str = Form(..., min_length=8, max_length=1000),
) -> HTMLResponse:
    _check_csrf(request, csrf_token)
    try:
        source = create_conversation_source(
            title=title,
            thread_reference=thread_reference,
            project_root=APP_PROJECT_ROOT,
        )
    except ValueError as exc:
        catalog = _catalog()
        response = templates.TemplateResponse(
            request=request,
            name="conversation_import.html",
            status_code=400,
            context=_context(
                request,
                "nodes",
                catalog,
                csrf_token=csrf_token,
                error=str(exc),
                values={"title": title, "thread_reference": thread_reference},
            ),
        )
        return _set_csrf_cookie(response, csrf_token)
    return RedirectResponse(
        url=f"/conversations/{source.id}?imported=1",
        status_code=303,
    )


@app.get("/conversations/{source_id}", response_class=HTMLResponse)
def conversation_detail(request: Request, source_id: str) -> HTMLResponse:
    catalog = _catalog()
    source = catalog.conversation_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Conversation source not found")
    documents = sorted(
        (
            item
            for item in catalog.research_documents
            if item.status != "archived"
            and (
                source.id in item.conversation_source_ids
                or item.id in source.document_ids
            )
        ),
        key=lambda item: item.updated_at,
        reverse=True,
    )
    notes = [
        item
        for item in catalog.knowledge_nodes
        if source.id in item.conversation_source_ids
    ]
    anchors = [
        item
        for item in catalog.anchors_for_conversation(source.id)
        if item.status == "active"
    ]
    prompt = _conversation_sync_prompt(source.id)
    page_url = _absolute_page_url(request, f"/conversations/{source.id}")
    return templates.TemplateResponse(
        request=request,
        name="conversation_detail.html",
        context=_context(
            request,
            "documents",
            catalog,
            source=source,
            documents=documents,
            notes=notes,
            anchors=anchors,
            prompt=prompt,
            codex_url=_codex_thread_url(source.thread_id, prompt, page_url),
            document_kind_labels=DOCUMENT_KIND_LABELS,
            document_verification_labels=DOCUMENT_VERIFICATION_LABELS,
            visibility_labels=VISIBILITY_LABELS,
            source_kind_labels=SOURCE_KIND_LABELS,
            verification_labels=VERIFICATION_LABELS,
            anchor_kind_labels=ANCHOR_KIND_LABELS,
        ),
    )


@app.get("/research/{target_id}", response_class=HTMLResponse)
def research_target(
    request: Request,
    target_id: str,
    map_id: str | None = None,
) -> HTMLResponse:
    catalog = _catalog()
    target = _target_map(catalog).get(target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Research target not found")
    node = catalog.knowledge_node(target_id)
    active_anchors = [
        item
        for item in catalog.anchors_for_node(target_id)
        if item.status == "active"
    ]
    prompt = _research_prompt(
        target,
        node.body if node else None,
        [item.excerpt for item in active_anchors],
    )
    try:
        selected_map = (
            resolve_map(catalog, map_id)
            if map_id
            else (map_for_node(catalog, node) if node else resolve_map(catalog))
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Knowledge map not found") from exc
    browser_url = _absolute_page_url(
        request,
        f"/graph?map_id={quote(selected_map.id)}&focus={quote(target_id)}",
    )
    return templates.TemplateResponse(
        request=request,
        name="research_launch.html",
        context=_context(
            request,
            "nodes",
            catalog,
            target=target,
            prompt=prompt,
            codex_url=_codex_new_url(prompt, browser_url),
        ),
    )


@app.get("/nodes/new", response_class=HTMLResponse)
def node_new(
    request: Request,
    target_id: str | None = None,
    node_type: str = "question",
    relation_type: str | None = None,
    parent_id: str | None = None,
    map_id: str | None = None,
) -> HTMLResponse:
    catalog = _catalog()
    try:
        selected_map = resolve_map(catalog, map_id) if map_id else None
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Knowledge map not found") from exc
    if node_type not in NODE_TYPE_LABELS:
        node_type = "question"
    parent = catalog.knowledge_node(parent_id) if parent_id else None
    if parent and not target_id:
        target_id = parent.target_id
    target_id = target_id if target_id in _target_map(catalog) else ""
    relation_type = (
        relation_type
        if relation_type in RELATION_LABELS
        else DEFAULT_RELATIONS[node_type]
    )
    csrf_token = _csrf_token(request)
    response = templates.TemplateResponse(
        request=request,
        name="node_form.html",
        context=_context(
            request,
            "nodes",
            catalog,
            node=None,
            form_title=f"新建{NODE_TYPE_LABELS[node_type]}节点",
            form_action="/nodes",
            csrf_token=csrf_token,
            target_options=_target_options(catalog),
            knowledge_options=_knowledge_options(catalog),
            node_type_labels=NODE_TYPE_LABELS,
            relation_labels=RELATION_LABELS,
            values={
                "title": "",
                "body": "",
                "node_type": node_type,
                "status": "open" if node_type in {"question", "challenge"} else "active",
                "target_id": target_id,
                "relation_type": relation_type,
                "parent_id": parent_id or "",
                "source_kind": "manual",
                "conversation_source_ids": [],
                "evidence_ids": [],
                "verification_status": "unverified",
                "visibility": selected_map.visibility if selected_map else "private",
                "map_id": selected_map.id if selected_map else "",
            },
            parent=parent,
            selected_map=selected_map,
            source_kind_labels=SOURCE_KIND_LABELS,
            verification_labels=VERIFICATION_LABELS,
            conversation_sources=catalog.conversation_sources,
            evidence_options=catalog.evidence,
            visibility_labels=VISIBILITY_LABELS,
        ),
    )
    return _set_csrf_cookie(response, csrf_token)


@app.post("/nodes")
def node_create(
    request: Request,
    csrf_token: str = Form(...),
    title: str = Form(..., min_length=2, max_length=120),
    body: str = Form(..., min_length=2, max_length=4000),
    node_type: str = Form(...),
    status: str = Form(...),
    target_id: str = Form(...),
    relation_type: str = Form(...),
    parent_id: str = Form(default=""),
    source_kind: str = Form(default="manual"),
    conversation_source_ids: list[str] = Form(default=[]),
    evidence_ids: list[str] = Form(default=[]),
    verification_status: str = Form(default="unverified"),
    visibility: str = Form(default="private"),
    map_id: str = Form(default=""),
) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    catalog = _catalog()
    _validate_node_fields(node_type, status, relation_type)
    _validate_provenance(
        catalog,
        source_kind,
        verification_status,
        conversation_source_ids,
        evidence_ids,
    )
    _validate_links(catalog, target_id, parent_id or None)
    if visibility not in VISIBILITY_LABELS:
        raise HTTPException(status_code=400, detail="未知的可见范围。")
    try:
        selected_map = resolve_map(catalog, map_id) if map_id else None
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="未知的知识图谱。") from exc
    if selected_map and selected_map.visibility == "shared" and visibility == "private":
        raise HTTPException(
            status_code=400,
            detail="仅本机笔记不能直接加入共享图谱；请选择可共享，或从私有专题图谱中新建。",
        )
    try:
        node = create_node(
            title=title,
            body=body,
            node_type=node_type,
            status=status,
            target_id=target_id,
            relation_type=relation_type,
            parent_id=parent_id or None,
            source_kind=source_kind,
            conversation_source_ids=conversation_source_ids,
            evidence_ids=evidence_ids,
            verification_status=verification_status,
            visibility=visibility,
            project_root=APP_PROJECT_ROOT,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if selected_map:
        add_node_to_map(selected_map, node.id, APP_PROJECT_ROOT)
    return RedirectResponse(url=f"/nodes/{node.id}?created=1", status_code=303)


@app.get("/nodes/{node_id}", response_class=HTMLResponse)
def node_detail(request: Request, node_id: str) -> HTMLResponse:
    catalog = _catalog()
    node = catalog.knowledge_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Knowledge node not found")
    targets = _target_map(catalog)
    parent = catalog.knowledge_node(node.parent_id) if node.parent_id else None
    children = sorted(
        (item for item in catalog.knowledge_nodes if item.parent_id == node.id),
        key=lambda item: item.created_at,
    )
    conversation_sources = [
        item
        for item in catalog.conversation_sources
        if item.id in node.conversation_source_ids
    ]
    source_map = {item.id: item for item in conversation_sources}
    selected_map = map_for_node(catalog, node)
    anchor_views = []
    for anchor in sorted(
        catalog.anchors_for_node(node.id),
        key=lambda item: (item.status == "archived", item.captured_at, item.id),
    ):
        source = source_map.get(anchor.conversation_source_id)
        if source is None:
            continue
        continue_prompt = _anchor_continue_prompt(node.title, anchor.excerpt)
        anchor_views.append(
            {
                "anchor": anchor,
                "source": source,
                "open_url": source.thread_url,
                "continue_url": _codex_new_url(
                    continue_prompt,
                    _absolute_page_url(request, f"/nodes/{node.id}"),
                ),
            }
        )
    csrf_token = _csrf_token(request)
    response = templates.TemplateResponse(
        request=request,
        name="node_detail.html",
        context=_context(
            request,
            "nodes",
            catalog,
            node=node,
            target=targets.get(node.target_id),
            parent=parent,
            children=children,
            csrf_token=csrf_token,
            node_type_labels=NODE_TYPE_LABELS,
            relation_labels=RELATION_LABELS,
            source_kind_labels=SOURCE_KIND_LABELS,
            verification_labels=VERIFICATION_LABELS,
            conversation_sources=conversation_sources,
            anchor_views=anchor_views,
            evidence_items=[
                item for item in catalog.evidence if item.id in node.evidence_ids
            ],
            codex_research_url=f"/research/{node.id}",
            anchor_kind_labels=ANCHOR_KIND_LABELS,
            role_labels=ROLE_LABELS,
            visibility_labels=VISIBILITY_LABELS,
            graph_focus_url=(
                f"/graph?map_id={quote(selected_map.id)}&focus={quote(node.target_id)}"
                if selected_map
                else f"/graph?focus={quote(node.target_id)}"
            ),
        ),
    )
    return _set_csrf_cookie(response, csrf_token)


@app.get("/nodes/{node_id}/edit", response_class=HTMLResponse)
def node_edit(request: Request, node_id: str) -> HTMLResponse:
    catalog = _catalog()
    node = catalog.knowledge_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Knowledge node not found")
    if node.status == "archived":
        return RedirectResponse(url=f"/nodes/{node.id}", status_code=303)
    csrf_token = _csrf_token(request)
    response = templates.TemplateResponse(
        request=request,
        name="node_form.html",
        context=_context(
            request,
            "nodes",
            catalog,
            node=node,
            form_title="编辑知识节点",
            form_action=f"/nodes/{node.id}",
            csrf_token=csrf_token,
            target_options=_target_options(catalog),
            knowledge_options=_knowledge_options(catalog, node.id),
            node_type_labels=NODE_TYPE_LABELS,
            relation_labels=RELATION_LABELS,
            values=node.model_dump(mode="json"),
            parent=catalog.knowledge_node(node.parent_id) if node.parent_id else None,
            source_kind_labels=SOURCE_KIND_LABELS,
            verification_labels=VERIFICATION_LABELS,
            conversation_sources=catalog.conversation_sources,
            evidence_options=catalog.evidence,
            visibility_labels=VISIBILITY_LABELS,
        ),
    )
    return _set_csrf_cookie(response, csrf_token)


@app.post("/nodes/{node_id}")
def node_update(
    request: Request,
    node_id: str,
    csrf_token: str = Form(...),
    title: str = Form(..., min_length=2, max_length=120),
    body: str = Form(..., min_length=2, max_length=4000),
    node_type: str = Form(...),
    status: str = Form(...),
    target_id: str = Form(...),
    relation_type: str = Form(...),
    parent_id: str = Form(default=""),
    source_kind: str = Form(default="manual"),
    conversation_source_ids: list[str] = Form(default=[]),
    evidence_ids: list[str] = Form(default=[]),
    verification_status: str = Form(default="unverified"),
    visibility: str = Form(default="private"),
) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    catalog = _catalog()
    if catalog.knowledge_node(node_id) is None:
        raise HTTPException(status_code=404, detail="Knowledge node not found")
    _validate_node_fields(node_type, status, relation_type)
    _validate_provenance(
        catalog,
        source_kind,
        verification_status,
        conversation_source_ids,
        evidence_ids,
    )
    _validate_links(catalog, target_id, parent_id or None, node_id)
    if visibility not in VISIBILITY_LABELS:
        raise HTTPException(status_code=400, detail="未知的可见范围。")
    try:
        update_node(
            node_id,
            title=title,
            body=body,
            node_type=node_type,
            status=status,
            target_id=target_id,
            relation_type=relation_type,
            parent_id=parent_id or None,
            source_kind=source_kind,
            conversation_source_ids=conversation_source_ids,
            evidence_ids=evidence_ids,
            verification_status=verification_status,
            visibility=visibility,
            project_root=APP_PROJECT_ROOT,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/nodes/{node_id}?updated=1", status_code=303)


@app.post("/nodes/{node_id}/anchors")
def node_anchor_create(
    request: Request,
    node_id: str,
    csrf_token: str = Form(...),
    conversation_source_id: str = Form(...),
    turn_id: str = Form(..., min_length=2, max_length=120),
    item_id: str = Form(..., min_length=2, max_length=120),
    role: str = Form(...),
    anchor_kind: str = Form(...),
    excerpt: str = Form(..., min_length=2, max_length=4000),
    locator_text: str = Form(default="", max_length=240),
) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    catalog = _catalog()
    node = catalog.knowledge_node(node_id)
    source = catalog.conversation_source(conversation_source_id)
    if node is None or node.status == "archived":
        raise HTTPException(status_code=404, detail="Knowledge node not found")
    if source is None or source.id not in node.conversation_source_ids:
        raise HTTPException(status_code=400, detail="该会话尚未关联到这条笔记。")
    if role not in ROLE_LABELS or anchor_kind not in ANCHOR_KIND_LABELS:
        raise HTTPException(status_code=400, detail="未知的会话片段类型。")
    try:
        create_anchor(
            node_id=node.id,
            conversation_source_id=source.id,
            turn_id=turn_id,
            item_id=item_id,
            role=role,
            anchor_kind=anchor_kind,
            excerpt=excerpt,
            locator_text=locator_text or None,
            project_root=APP_PROJECT_ROOT,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/nodes/{node.id}?anchor_added=1", status_code=303)


@app.post("/nodes/{node_id}/anchors/{anchor_id}/archive")
def node_anchor_archive(
    request: Request,
    node_id: str,
    anchor_id: str,
    csrf_token: str = Form(...),
) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    catalog = _catalog()
    anchor = catalog.conversation_anchor(anchor_id)
    if anchor is None or anchor.node_id != node_id:
        raise HTTPException(status_code=404, detail="Conversation anchor not found")
    archive_anchor(anchor.id, APP_PROJECT_ROOT)
    return RedirectResponse(url=f"/nodes/{node_id}?anchor_archived=1", status_code=303)


@app.post("/nodes/{node_id}/archive")
def node_archive(
    request: Request,
    node_id: str,
    csrf_token: str = Form(...),
) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    try:
        archive_node(node_id, APP_PROJECT_ROOT)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Knowledge node not found") from exc
    return RedirectResponse(url=f"/nodes/{node_id}?archived=1", status_code=303)


@app.post("/nodes/{node_id}/restore")
def node_restore(
    request: Request,
    node_id: str,
    csrf_token: str = Form(...),
) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    try:
        restore_node(node_id, APP_PROJECT_ROOT)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Knowledge node not found") from exc
    return RedirectResponse(url=f"/nodes/{node_id}?restored=1", status_code=303)


@app.get("/changes", response_class=HTMLResponse)
def changes(request: Request) -> HTMLResponse:
    catalog = _catalog()
    ordered = sorted(catalog.changes, key=lambda item: item.detected_at, reverse=True)
    return templates.TemplateResponse(
        request=request,
        name="changes.html",
        context=_context(request, "changes", catalog, changes=ordered),
    )


@app.get("/reviews", response_class=HTMLResponse)
def reviews(request: Request) -> HTMLResponse:
    catalog = _catalog()
    ordered = sorted(catalog.proposals, key=lambda item: (item.status != "pending", item.created_at))
    technologies = {item.id: item for item in catalog.technologies}
    return templates.TemplateResponse(
        request=request,
        name="reviews.html",
        context=_context(request, "reviews", catalog, proposals=ordered, technologies=technologies),
    )


@app.get("/reviews/{proposal_id}", response_class=HTMLResponse)
def review_detail(request: Request, proposal_id: str) -> HTMLResponse:
    catalog = _catalog()
    proposal = catalog.proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    technology = catalog.technology(proposal.technology_id)
    capability = catalog.capability(proposal.proposed_claim.capability_id)
    evidence = [item for item in catalog.evidence if item.id in proposal.evidence_ids]
    csrf_token = _csrf_token(request)
    response = templates.TemplateResponse(
        request=request,
        name="review_detail.html",
        context=_context(
            request,
            "reviews",
            catalog,
            proposal=proposal,
            technology=technology,
            capability=capability,
            evidence=evidence,
            csrf_token=csrf_token,
        ),
    )
    return _set_csrf_cookie(response, csrf_token)


@app.post("/reviews/{proposal_id}/decision")
def review_decision(
    request: Request,
    proposal_id: str,
    decision: str = Form(...),
    csrf_token: str = Form(...),
    edited_text: str = Form(..., min_length=8),
    confidence: int = Form(..., ge=0, le=100),
    reviewer_note: str = Form(default=""),
) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    try:
        decide_proposal(
            proposal_id=proposal_id,
            decision=decision,
            edited_text=edited_text,
            confidence=confidence,
            reviewer_note=reviewer_note,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Proposal not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RedirectResponse(url=f"/reviews/{proposal_id}?reviewed=1", status_code=303)


@app.get("/experiments", response_class=HTMLResponse)
def experiments(request: Request) -> HTMLResponse:
    catalog = _catalog()
    technologies = {item.id: item for item in catalog.technologies}
    return templates.TemplateResponse(
        request=request,
        name="experiments.html",
        context=_context(
            request,
            "experiments",
            catalog,
            experiments=catalog.experiments,
            technologies=technologies,
        ),
    )
