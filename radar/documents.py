import html
import os
import re
import secrets
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha1
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from markupsafe import Markup

from radar.models import ResearchDocument
from radar.paths import PROJECT_ROOT


DOCUMENT_ID_PATTERN = re.compile(r"^doc-[a-z0-9-]+$")
HEADING_PATTERN = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
NUMBERED_HEADING_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)(?:\.\s+|\s+)")
TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*$")


@dataclass(frozen=True)
class DocumentSection:
    anchor: str
    title: str
    level: int
    line: int
    end_line: int
    summary: str

    @property
    def id_suffix(self) -> str:
        return self.anchor.removeprefix("section-")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _document_directory(project_root: Path, visibility: str = "shared") -> Path:
    directory = project_root / "knowledge" / "documents"
    return directory / "private" if visibility == "private" else directory


def _metadata_path(
    document_id: str,
    project_root: Path,
    visibility: str = "shared",
) -> Path:
    if not DOCUMENT_ID_PATTERN.fullmatch(document_id):
        raise ValueError("Invalid research document id")
    return _document_directory(project_root, visibility) / f"{document_id}.yaml"


def _content_path(document: ResearchDocument, project_root: Path) -> Path:
    candidate = (project_root / document.content_path).resolve()
    root = project_root.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("Document content must stay inside the project directory")
    return candidate


def _atomic_write(path: Path, document: ResearchDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(
        document.model_dump(mode="json"),
        allow_unicode=True,
        sort_keys=False,
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.stem}-",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(payload)
        temporary_path = Path(handle.name)
    os.replace(temporary_path, path)


def create_research_document(
    *,
    document_id: str,
    title: str,
    summary: str,
    source_file: Path,
    visibility: str = "private",
    document_kind: str = "research_note",
    verification_status: str = "mixed",
    conversation_source_ids: list[str] | None = None,
    technology_ids: list[str] | None = None,
    capability_ids: list[str] | None = None,
    featured_section_anchors: list[str] | None = None,
    section_context_ids: dict[str, list[str]] | None = None,
    project_root: Path = PROJECT_ROOT,
) -> ResearchDocument:
    metadata_path = _metadata_path(document_id, project_root, visibility)
    if metadata_path.exists():
        return ResearchDocument.model_validate(
            yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
        )
    if not source_file.is_file():
        raise FileNotFoundError(source_file)
    destination = _document_directory(project_root, visibility) / f"{document_id}.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_file, destination)
    timestamp = _now()
    document = ResearchDocument(
        id=document_id,
        title=title.strip(),
        summary=summary.strip(),
        content_path=destination.relative_to(project_root).as_posix(),
        document_kind=document_kind,
        status="active",
        visibility=visibility,
        verification_status=verification_status,
        conversation_source_ids=conversation_source_ids or [],
        technology_ids=technology_ids or [],
        capability_ids=capability_ids or [],
        featured_section_anchors=featured_section_anchors or [],
        section_context_ids=section_context_ids or {},
        created_at=timestamp,
        updated_at=timestamp,
    )
    _atomic_write(metadata_path, document)
    return document


def load_document_text(
    document: ResearchDocument,
    project_root: Path = PROJECT_ROOT,
) -> str:
    path = _content_path(document, project_root)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def _heading_anchor(title: str, used: set[str]) -> str:
    numbered = NUMBERED_HEADING_PATTERN.match(title)
    if numbered:
        base = "section-" + numbered.group(1).replace(".", "-")
    else:
        digest = sha1(title.encode("utf-8")).hexdigest()[:10]
        base = f"section-{digest}"
    anchor = base
    suffix = 2
    while anchor in used:
        anchor = f"{base}-{suffix}"
        suffix += 1
    used.add(anchor)
    return anchor


def _plain_text(value: str) -> str:
    value = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"[*_`>#]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_document_outline(text: str) -> list[DocumentSection]:
    lines = text.splitlines()
    raw_sections: list[tuple[str, str, int, int]] = []
    used: set[str] = set()
    for index, line in enumerate(lines):
        match = HEADING_PATTERN.match(line)
        if not match:
            continue
        level = len(match.group(1))
        title = _plain_text(match.group(2))
        raw_sections.append((_heading_anchor(title, used), title, level, index))

    sections: list[DocumentSection] = []
    for position, (anchor, title, level, line) in enumerate(raw_sections):
        end_line = len(lines)
        for _, _, next_level, next_line in raw_sections[position + 1 :]:
            if next_level <= level:
                end_line = next_line
                break
        summary = ""
        in_fence = False
        for candidate in lines[line + 1 : end_line]:
            stripped = candidate.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence or not stripped or stripped.startswith(("|", "#", "---")):
                continue
            stripped = re.sub(r"^(?:[-*+] |\d+\. |>\s*)", "", stripped)
            summary = _plain_text(stripped)
            if summary:
                break
        sections.append(
            DocumentSection(
                anchor=anchor,
                title=title,
                level=level,
                line=line + 1,
                end_line=end_line,
                summary=summary[:260],
            )
        )
    return sections


def featured_sections(
    document: ResearchDocument,
    text: str,
) -> list[DocumentSection]:
    sections = parse_document_outline(text)
    by_anchor = {item.anchor: item for item in sections}
    if document.featured_section_anchors:
        return [
            by_anchor[anchor]
            for anchor in document.featured_section_anchors
            if anchor in by_anchor
        ]
    return [item for item in sections if item.level == 2][:12]


def document_section_text(text: str, anchor: str) -> tuple[DocumentSection, str]:
    lines = text.splitlines()
    section = next(
        (item for item in parse_document_outline(text) if item.anchor == anchor),
        None,
    )
    if section is None:
        raise KeyError(anchor)
    return section, "\n".join(lines[section.line - 1 : section.end_line]).strip()


def _safe_href(value: str) -> str:
    value = value.strip()
    parsed = urlsplit(value)
    if value.startswith(("/", "#")) or parsed.scheme in {"http", "https", "codex"}:
        return html.escape(value, quote=True)
    return "#"


def _inline(value: str) -> str:
    escaped = html.escape(value, quote=False)
    code_tokens: list[str] = []

    def stash_code(match: re.Match[str]) -> str:
        code_tokens.append(f"<code>{match.group(1)}</code>")
        return f"\x00CODE{len(code_tokens) - 1}\x00"

    escaped = re.sub(r"`([^`]+)`", stash_code, escaped)
    escaped = re.sub(
        r"\[([^]]+)\]\(([^)]+)\)",
        lambda match: (
            f'<a href="{_safe_href(html.unescape(match.group(2)))}"'
            + (' target="_blank" rel="noreferrer"' if match.group(2).startswith(("http://", "https://")) else "")
            + f">{match.group(1)}</a>"
        ),
        escaped,
    )
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)
    for index, token in enumerate(code_tokens):
        escaped = escaped.replace(f"\x00CODE{index}\x00", token)
    return escaped


def _table_cells(line: str) -> list[str]:
    return [item.strip() for item in line.strip().strip("|").split("|")]


def render_markdown(text: str) -> Markup:
    lines = text.splitlines()
    outline = {item.line - 1: item for item in parse_document_outline(text)}
    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("```"):
            language = stripped[3:].strip()
            code: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            escaped_code = html.escape(chr(10).join(code))
            if language == "mermaid":
                output.append(
                    '<figure class="document-diagram" data-mermaid-diagram>'
                    '<figcaption><span>流程图</span><small>可缩放 · 小窗中可横向浏览</small></figcaption>'
                    '<div class="document-diagram-canvas" data-mermaid-canvas aria-label="Mermaid 流程图">'
                    '<div class="document-diagram-loading">正在绘制流程图…</div></div>'
                    '<details class="document-diagram-source"><summary>查看 Mermaid 源码</summary>'
                    f'<pre class="document-code"><code>{escaped_code}</code></pre></details></figure>'
                )
            else:
                output.append(
                    f'<pre class="document-code"><code>{escaped_code}</code></pre>'
                )
            continue
        heading = HEADING_PATTERN.match(line)
        if heading:
            level = len(heading.group(1))
            anchor = outline[index].anchor
            output.append(
                f'<h{level} id="{anchor}">{_inline(heading.group(2))}'
                f'<a class="heading-anchor" href="#{anchor}" aria-label="链接到本节">#</a></h{level}>'
            )
            index += 1
            continue
        if stripped in {"---", "***", "___"}:
            output.append("<hr>")
            index += 1
            continue
        if stripped.startswith(">"):
            quoted: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quoted.append(re.sub(r"^\s*>\s?", "", lines[index]))
                index += 1
            output.append(f"<blockquote><p>{_inline(' '.join(quoted))}</p></blockquote>")
            continue
        if stripped.startswith("|") and index + 1 < len(lines) and TABLE_SEPARATOR_PATTERN.match(lines[index + 1]):
            headers = _table_cells(line)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(_table_cells(lines[index]))
                index += 1
            output.append('<div class="document-table-wrap"><table><thead><tr>')
            output.extend(f"<th>{_inline(cell)}</th>" for cell in headers)
            output.append("</tr></thead><tbody>")
            for row in rows:
                output.append("<tr>")
                output.extend(f"<td>{_inline(cell)}</td>" for cell in row)
                output.append("</tr>")
            output.append("</tbody></table></div>")
            continue
        list_match = re.match(r"^\s*([-*+] |\d+\.\s+)(.+)$", line)
        if list_match:
            ordered = bool(re.match(r"\d", list_match.group(1)))
            tag = "ol" if ordered else "ul"
            items: list[str] = []
            while index < len(lines):
                match = re.match(r"^\s*([-*+] |\d+\.\s+)(.+)$", lines[index])
                if not match or bool(re.match(r"\d", match.group(1))) != ordered:
                    break
                items.append(match.group(2).strip())
                index += 1
            output.append(f"<{tag}>" + "".join(f"<li>{_inline(item)}</li>" for item in items) + f"</{tag}>")
            continue
        paragraph = [stripped]
        index += 1
        while index < len(lines):
            candidate = lines[index].strip()
            if (
                not candidate
                or candidate.startswith(("#", "```", ">", "|"))
                or candidate in {"---", "***", "___"}
                or re.match(r"^\s*([-*+] |\d+\.\s+)", lines[index])
            ):
                break
            paragraph.append(candidate)
            index += 1
        output.append(f"<p>{_inline(' '.join(paragraph))}</p>")
    return Markup("\n".join(output))
