import re
import shutil

from fastapi.testclient import TestClient

import app.main as main
from radar.anchors import create_anchor
from radar.conversations import create_conversation_source
from radar.nodes import archive_node, create_node, restore_node, update_node
from radar.paths import PROJECT_ROOT
from radar.store import load_catalog


def _copy_catalog(tmp_path) -> None:
    for directory in ("knowledge", "proposals", "inbox", "experiments"):
        shutil.copytree(PROJECT_ROOT / directory, tmp_path / directory)


def test_node_service_create_update_archive_restore(tmp_path) -> None:
    node = create_node(
        title="要验证的问题",
        body="这是一条需要通过实验回答的问题。",
        node_type="question",
        target_id="claim-example",
        relation_type="questions",
        project_root=tmp_path,
    )
    assert node.status == "open"

    updated = update_node(
        node.id,
        title="已修正的问题",
        body="更完整地记录质疑依据与待验证边界。",
        node_type="challenge",
        target_id="claim-example",
        relation_type="challenges",
        parent_id=None,
        status="active",
        project_root=tmp_path,
    )
    assert updated.title == "已修正的问题"

    archived = archive_node(node.id, tmp_path)
    assert archived.status == "archived"
    restored = restore_node(node.id, tmp_path)
    assert restored.status == "active"


def test_node_routes_full_lifecycle(tmp_path, monkeypatch) -> None:
    _copy_catalog(tmp_path)
    monkeypatch.setattr(main, "APP_PROJECT_ROOT", tmp_path)

    with TestClient(main.app) as client:
        form = client.get("/nodes/new?target_id=tech-pydantic-ai&node_type=question")
        assert form.status_code == 200
        token = re.search(r'name="csrf_token" value="([^"]+)"', form.text).group(1)
        created = client.post(
            "/nodes",
            data={
                "csrf_token": token,
                "title": "这个框架的重试是否可控？",
                "body": "需要通过实验区分框架重试与模型自行修正。",
                "node_type": "question",
                "status": "open",
                "target_id": "tech-pydantic-ai",
                "relation_type": "questions",
                "parent_id": "",
            },
            follow_redirects=False,
        )
        assert created.status_code == 303, created.text
        node_id = created.headers["location"].split("/")[2].split("?")[0]

        detail = client.get(f"/nodes/{node_id}")
        assert detail.status_code == 200
        token = re.search(r'name="csrf_token" value="([^"]+)"', detail.text).group(1)
        archived = client.post(
            f"/nodes/{node_id}/archive",
            data={"csrf_token": token},
            follow_redirects=False,
        )
        assert archived.status_code == 303
        assert load_catalog(tmp_path).knowledge_node(node_id).status == "archived"

        detail = client.get(f"/nodes/{node_id}")
        token = re.search(r'name="csrf_token" value="([^"]+)"', detail.text).group(1)
        restored = client.post(
            f"/nodes/{node_id}/restore",
            data={"csrf_token": token},
            follow_redirects=False,
        )
        assert restored.status_code == 303
        assert load_catalog(tmp_path).knowledge_node(node_id).status == "open"


def test_node_detail_renders_codex_anchor_actions(tmp_path, monkeypatch) -> None:
    _copy_catalog(tmp_path)
    source = create_conversation_source(
        title="PydanticAI 学习会话",
        thread_reference="codex://threads/018f2a6c-7b3d-7e4f-8a9b-1c2d3e4f5a6b",
        project_root=tmp_path,
    )
    node = create_node(
        title="Guardrail 的真实边界",
        body="会话只是认知来源，结论仍待查证。",
        node_type="concept",
        target_id="cap-human-loop",
        relation_type="relates_to",
        source_kind="codex_conversation",
        conversation_source_ids=[source.id],
        visibility="private",
        project_root=tmp_path,
    )
    create_anchor(
        node_id=node.id,
        conversation_source_id=source.id,
        turn_id="turn-1",
        item_id="item-2",
        role="assistant",
        anchor_kind="answer_basis",
        excerpt="Guardrail 是检查位置，不是检测模型。",
        locator_text="Guardrail 是检查位置",
        project_root=tmp_path,
    )
    monkeypatch.setattr(main, "APP_PROJECT_ROOT", tmp_path)

    with TestClient(main.app) as client:
        detail = client.get(f"/nodes/{node.id}")
        assert detail.status_code == 200
        assert "形成这条认识的原始片段" in detail.text
        assert "回到原会话并复制定位句" in detail.text
        assert "从这里开启新追问" in detail.text
        assert "codex://threads/" in detail.text
        assert "codex://new?" in detail.text
