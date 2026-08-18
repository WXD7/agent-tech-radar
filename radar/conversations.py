import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import yaml

from radar.models import ConversationSource
from radar.paths import PROJECT_ROOT


CONVERSATION_ID_PATTERN = re.compile(
    r"^conversation-[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
UUID_PATTERN = re.compile(
    r"(?<![0-9a-f])"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})"
    r"(?![0-9a-f])",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_thread_id(reference: str) -> str:
    """Extract and canonicalize one Codex thread UUID from a pasted reference."""
    value = reference.strip()
    matches = UUID_PATTERN.findall(value)
    if len(matches) != 1:
        raise ValueError("请输入一个有效的 Codex 会话链接或会话 ID。")
    try:
        thread_id = str(UUID(matches[0]))
    except ValueError as exc:
        raise ValueError("Codex 会话 ID 格式不正确。") from exc
    if value == matches[0]:
        return thread_id
    if not (
        value.startswith("codex://")
        or value.startswith("https://")
        or value.startswith("http://")
    ):
        raise ValueError("会话引用必须是 UUID、Codex 深链接或网页链接。")
    return thread_id


def _conversation_directory(project_root: Path) -> Path:
    return project_root / "knowledge" / "conversations"


def _conversation_path(source_id: str, project_root: Path) -> Path:
    if not CONVERSATION_ID_PATTERN.fullmatch(source_id):
        raise ValueError("Invalid conversation source id")
    return _conversation_directory(project_root) / f"{source_id}.yaml"


def _atomic_write(path: Path, source: ConversationSource) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(
        source.model_dump(mode="json"),
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


def read_conversation_source(
    source_id: str,
    project_root: Path = PROJECT_ROOT,
) -> ConversationSource:
    path = _conversation_path(source_id, project_root)
    if not path.exists():
        raise FileNotFoundError(source_id)
    return ConversationSource.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )


def create_conversation_source(
    *,
    title: str,
    thread_reference: str,
    project_root: Path = PROJECT_ROOT,
) -> ConversationSource:
    thread_id = parse_thread_id(thread_reference)
    source_id = f"conversation-{thread_id}"
    path = _conversation_path(source_id, project_root)
    if path.exists():
        return read_conversation_source(source_id, project_root)
    timestamp = _now()
    source = ConversationSource(
        id=source_id,
        title=title.strip(),
        thread_id=thread_id,
        thread_url=f"codex://threads/{thread_id}",
        imported_at=timestamp,
        updated_at=timestamp,
    )
    _atomic_write(path, source)
    return source


def update_conversation_source(
    source_id: str,
    *,
    title: str | None = None,
    status: str | None = None,
    summary: str | None = None,
    note_ids: list[str] | None = None,
    last_synced_turn_id: str | None = None,
    mark_synced: bool = False,
    project_root: Path = PROJECT_ROOT,
) -> ConversationSource:
    current = read_conversation_source(source_id, project_root)
    timestamp = _now()
    source = current.model_copy(
        update={
            "title": title.strip() if title is not None else current.title,
            "status": "synced" if mark_synced else (status or current.status),
            "summary": summary if summary is not None else current.summary,
            "note_ids": note_ids if note_ids is not None else current.note_ids,
            "last_synced_turn_id": (
                last_synced_turn_id
                if last_synced_turn_id is not None
                else current.last_synced_turn_id
            ),
            "last_synced_at": timestamp if mark_synced else current.last_synced_at,
            "updated_at": timestamp,
        }
    )
    source = ConversationSource.model_validate(source.model_dump())
    _atomic_write(_conversation_path(source.id, project_root), source)
    return source
