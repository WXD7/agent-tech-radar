import hashlib
import os
import re
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml

from radar.models import ConversationAnchor
from radar.paths import PROJECT_ROOT


ANCHOR_ID_PATTERN = re.compile(r"^anchor-[0-9a-f]{12,32}$")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _anchor_directory(project_root: Path) -> Path:
    return project_root / "knowledge" / "conversations" / "anchors"


def _anchor_path(anchor_id: str, project_root: Path) -> Path:
    if not ANCHOR_ID_PATTERN.fullmatch(anchor_id):
        raise ValueError("Invalid conversation anchor id")
    return _anchor_directory(project_root) / f"{anchor_id}.yaml"


def _atomic_write(path: Path, anchor: ConversationAnchor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(
        anchor.model_dump(mode="json"),
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


def read_anchor(
    anchor_id: str,
    project_root: Path = PROJECT_ROOT,
) -> ConversationAnchor:
    path = _anchor_path(anchor_id, project_root)
    if not path.exists():
        raise FileNotFoundError(anchor_id)
    return ConversationAnchor.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )


def create_anchor(
    *,
    node_id: str,
    conversation_source_id: str,
    turn_id: str,
    item_id: str,
    role: str,
    anchor_kind: str,
    excerpt: str,
    locator_text: str | None = None,
    project_root: Path = PROJECT_ROOT,
) -> ConversationAnchor:
    clean_excerpt = excerpt.strip()
    clean_locator = (locator_text or clean_excerpt[:200]).strip()
    anchor = ConversationAnchor(
        id=f"anchor-{secrets.token_hex(8)}",
        node_id=node_id,
        conversation_source_id=conversation_source_id,
        turn_id=turn_id.strip(),
        item_id=item_id.strip(),
        role=role,
        anchor_kind=anchor_kind,
        excerpt=clean_excerpt,
        locator_text=clean_locator,
        content_hash=hashlib.sha256(clean_excerpt.encode("utf-8")).hexdigest(),
        captured_at=_now(),
    )
    _atomic_write(_anchor_path(anchor.id, project_root), anchor)
    return anchor


def archive_anchor(
    anchor_id: str,
    project_root: Path = PROJECT_ROOT,
) -> ConversationAnchor:
    current = read_anchor(anchor_id, project_root)
    if current.status == "archived":
        return current
    anchor = current.model_copy(update={"status": "archived"})
    _atomic_write(_anchor_path(anchor.id, project_root), anchor)
    return anchor
