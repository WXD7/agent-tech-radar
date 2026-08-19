import os
import re
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml

from radar.models import KnowledgeNode
from radar.paths import PROJECT_ROOT


NODE_ID_PATTERN = re.compile(r"^node-[a-z0-9-]+$")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _default_status(node_type: str) -> str:
    return "open" if node_type in {"question", "challenge"} else "active"


def _node_directory(project_root: Path, visibility: str = "shared") -> Path:
    directory = project_root / "knowledge" / "nodes"
    return directory / "private" if visibility == "private" else directory


def _node_path(
    node_id: str,
    project_root: Path,
    visibility: str = "shared",
) -> Path:
    if not NODE_ID_PATTERN.fullmatch(node_id):
        raise ValueError("Invalid knowledge node id")
    return _node_directory(project_root, visibility) / f"{node_id}.yaml"


def _find_node_path(node_id: str, project_root: Path) -> Path:
    shared_path = _node_path(node_id, project_root)
    private_path = _node_path(node_id, project_root, "private")
    if shared_path.exists():
        return shared_path
    if private_path.exists():
        return private_path
    return shared_path


def _atomic_write(path: Path, node: KnowledgeNode) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(
        node.model_dump(mode="json"),
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


def read_node(node_id: str, project_root: Path = PROJECT_ROOT) -> KnowledgeNode:
    path = _find_node_path(node_id, project_root)
    if not path.exists():
        raise FileNotFoundError(node_id)
    return KnowledgeNode.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def create_node(
    *,
    title: str,
    body: str,
    node_type: str,
    target_id: str,
    relation_type: str,
    parent_id: str | None = None,
    status: str | None = None,
    source_kind: str = "manual",
    conversation_source_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    verification_status: str = "unverified",
    visibility: str = "shared",
    project_root: Path = PROJECT_ROOT,
) -> KnowledgeNode:
    timestamp = _now()
    node_id = f"node-{secrets.token_hex(6)}"
    node = KnowledgeNode(
        id=node_id,
        title=title.strip(),
        body=body.strip(),
        node_type=node_type,
        status=status or _default_status(node_type),
        target_id=target_id,
        relation_type=relation_type,
        parent_id=parent_id or None,
        created_at=timestamp,
        updated_at=timestamp,
        source_kind=source_kind,
        conversation_source_ids=conversation_source_ids or [],
        evidence_ids=evidence_ids or [],
        verification_status=verification_status,
        visibility=visibility,
    )
    _atomic_write(_node_path(node.id, project_root, node.visibility), node)
    return node


def update_node(
    node_id: str,
    *,
    title: str,
    body: str,
    node_type: str,
    target_id: str,
    relation_type: str,
    parent_id: str | None,
    status: str,
    source_kind: str | None = None,
    conversation_source_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    verification_status: str | None = None,
    visibility: str | None = None,
    project_root: Path = PROJECT_ROOT,
) -> KnowledgeNode:
    current = read_node(node_id, project_root)
    if current.status == "archived":
        raise ValueError("请先恢复该节点，再进行编辑。")
    node = current.model_copy(
        update={
            "title": title.strip(),
            "body": body.strip(),
            "node_type": node_type,
            "target_id": target_id,
            "relation_type": relation_type,
            "parent_id": parent_id or None,
            "status": status,
            "source_kind": source_kind or current.source_kind,
            "conversation_source_ids": (
                conversation_source_ids
                if conversation_source_ids is not None
                else current.conversation_source_ids
            ),
            "evidence_ids": (
                evidence_ids if evidence_ids is not None else current.evidence_ids
            ),
            "verification_status": (
                verification_status or current.verification_status
            ),
            "visibility": visibility or current.visibility,
            "updated_at": _now(),
        }
    )
    node = KnowledgeNode.model_validate(node.model_dump())
    current_path = _find_node_path(node.id, project_root)
    next_path = _node_path(node.id, project_root, node.visibility)
    _atomic_write(next_path, node)
    if current_path != next_path and current_path.exists():
        current_path.unlink()
    return node


def archive_node(node_id: str, project_root: Path = PROJECT_ROOT) -> KnowledgeNode:
    current = read_node(node_id, project_root)
    if current.status == "archived":
        return current
    node = current.model_copy(
        update={
            "archived_from": current.status,
            "status": "archived",
            "updated_at": _now(),
        }
    )
    _atomic_write(_find_node_path(node.id, project_root), node)
    return node


def restore_node(node_id: str, project_root: Path = PROJECT_ROOT) -> KnowledgeNode:
    current = read_node(node_id, project_root)
    if current.status != "archived":
        return current
    node = current.model_copy(
        update={
            "status": current.archived_from or _default_status(current.node_type),
            "archived_from": None,
            "updated_at": _now(),
        }
    )
    _atomic_write(_find_node_path(node.id, project_root), node)
    return node
