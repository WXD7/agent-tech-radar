import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml

from radar.documents import featured_sections, load_document_text
from radar.models import Catalog, KnowledgeMap, KnowledgeNode, ResearchDocument
from radar.paths import PROJECT_ROOT
from radar.store import graph_elements


MAP_ID_PATTERN = re.compile(r"^map-[a-z0-9-]+$")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _map_directory(project_root: Path, visibility: str = "shared") -> Path:
    directory = project_root / "knowledge" / "maps"
    return directory / "private" if visibility == "private" else directory


def _map_path(map_id: str, project_root: Path, visibility: str = "shared") -> Path:
    if not MAP_ID_PATTERN.fullmatch(map_id):
        raise ValueError("Invalid knowledge map id")
    return _map_directory(project_root, visibility) / f"{map_id}.yaml"


def _atomic_write(path: Path, knowledge_map: KnowledgeMap) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(
        knowledge_map.model_dump(mode="json"),
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


def create_knowledge_map(
    *,
    map_id: str,
    title: str,
    description: str,
    visibility: str = "private",
    selection_mode: str = "topic",
    conversation_source_ids: list[str] | None = None,
    document_ids: list[str] | None = None,
    node_ids: list[str] | None = None,
    context_ids: list[str] | None = None,
    include_evidence: bool = True,
    project_root: Path = PROJECT_ROOT,
) -> KnowledgeMap:
    path = _map_path(map_id, project_root, visibility)
    if path.exists():
        return KnowledgeMap.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    timestamp = _now()
    knowledge_map = KnowledgeMap(
        id=map_id,
        title=title.strip(),
        description=description.strip(),
        visibility=visibility,
        selection_mode=selection_mode,
        conversation_source_ids=conversation_source_ids or [],
        document_ids=document_ids or [],
        node_ids=node_ids or [],
        context_ids=context_ids or [],
        include_evidence=include_evidence,
        created_at=timestamp,
        updated_at=timestamp,
    )
    _atomic_write(path, knowledge_map)
    return knowledge_map


def add_node_to_map(
    knowledge_map: KnowledgeMap,
    node_id: str,
    project_root: Path = PROJECT_ROOT,
) -> KnowledgeMap:
    if node_id in knowledge_map.node_ids:
        return knowledge_map
    updated = knowledge_map.model_copy(
        update={
            "node_ids": [*knowledge_map.node_ids, node_id],
            "updated_at": _now(),
        }
    )
    updated = KnowledgeMap.model_validate(updated.model_dump())
    path = _map_path(updated.id, project_root, updated.visibility)
    if not path.exists():
        raise FileNotFoundError(updated.id)
    _atomic_write(path, updated)
    return updated


def add_document_to_map(
    knowledge_map: KnowledgeMap,
    document_id: str,
    project_root: Path = PROJECT_ROOT,
) -> KnowledgeMap:
    if document_id in knowledge_map.document_ids:
        return knowledge_map
    updated = knowledge_map.model_copy(
        update={
            "document_ids": [*knowledge_map.document_ids, document_id],
            "updated_at": _now(),
        }
    )
    updated = KnowledgeMap.model_validate(updated.model_dump())
    path = _map_path(updated.id, project_root, updated.visibility)
    if not path.exists():
        raise FileNotFoundError(updated.id)
    _atomic_write(path, updated)
    return updated


def active_maps(catalog: Catalog) -> list[KnowledgeMap]:
    return sorted(
        (item for item in catalog.knowledge_maps if item.status == "active"),
        key=lambda item: (item.selection_mode != "overview", item.title),
    )


def resolve_map(catalog: Catalog, map_id: str | None = None) -> KnowledgeMap:
    maps = active_maps(catalog)
    if map_id:
        selected = catalog.knowledge_map(map_id)
        if selected and selected.status == "active":
            return selected
        raise KeyError(map_id)
    if not maps:
        raise KeyError("No active knowledge maps")
    return next((item for item in maps if item.selection_mode == "overview"), maps[0])


def map_for_node(catalog: Catalog, node: KnowledgeNode) -> KnowledgeMap | None:
    maps = active_maps(catalog)
    for knowledge_map in maps:
        if knowledge_map.selection_mode != "topic":
            continue
        if node.id in knowledge_map.node_ids or set(node.conversation_source_ids) & set(
            knowledge_map.conversation_source_ids
        ):
            return knowledge_map
    return next((item for item in maps if item.selection_mode == "overview"), None)


def map_for_document(
    catalog: Catalog,
    document: ResearchDocument,
) -> KnowledgeMap | None:
    maps = active_maps(catalog)
    return next(
        (
            item
            for item in maps
            if item.selection_mode == "topic" and document.id in item.document_ids
        ),
        next((item for item in maps if item.selection_mode == "overview"), None),
    )


def _topic_ids(
    catalog: Catalog,
    knowledge_map: KnowledgeMap,
    project_root: Path,
) -> set[str]:
    source_ids = set(knowledge_map.conversation_source_ids)
    included = (
        set(knowledge_map.document_ids)
        | set(knowledge_map.node_ids)
        | set(knowledge_map.context_ids)
    )
    for document_id in knowledge_map.document_ids:
        document = catalog.research_document(document_id)
        if document is None or document.status == "archived":
            continue
        included.update(document.technology_ids)
        included.update(document.capability_ids)
        included.update(
            context_id
            for context_ids in document.section_context_ids.values()
            for context_id in context_ids
        )
        try:
            text = load_document_text(document, project_root)
            included.update(
                f"{document.id}-{section.anchor}"
                for section in featured_sections(document, text)
            )
        except (FileNotFoundError, OSError, ValueError):
            continue
    selected_notes = [
        item
        for item in catalog.knowledge_nodes
        if item.status != "archived"
        and (
            item.id in included
            or (
                not knowledge_map.document_ids
                and bool(source_ids & set(item.conversation_source_ids))
            )
        )
    ]
    included.update(item.id for item in selected_notes)
    included.update(item.target_id for item in selected_notes)
    included.update(item.parent_id for item in selected_notes if item.parent_id)

    capability_ids = {item.id for item in catalog.capabilities}
    technology_ids = {item.id for item in catalog.technologies}
    selected_capability_ids = included & capability_ids
    selected_technology_ids = included & technology_ids

    for technology in catalog.technologies:
        if technology.id in selected_technology_ids or selected_capability_ids & set(
            technology.capability_ids
        ):
            selected_technology_ids.add(technology.id)
            included.add(technology.id)
            included.update(technology.capability_ids)

    if knowledge_map.include_evidence:
        selected_claim_ids: set[str] = set()
        for claim in catalog.claims:
            if (
                claim.id in included
                or claim.technology_id in selected_technology_ids
                or claim.capability_id in included
            ):
                selected_claim_ids.add(claim.id)
                included.add(claim.id)
                included.add(claim.technology_id)
                included.add(claim.capability_id)
                included.update(claim.evidence_ids)
                included.update(claim.experiment_ids)
        for technology in catalog.technologies:
            if technology.id in selected_technology_ids:
                included.update(technology.source_ids)
        for evidence in catalog.evidence:
            if set(evidence.supports_claim_ids + evidence.contradicts_claim_ids) & selected_claim_ids:
                included.add(evidence.id)
        for experiment in catalog.experiments:
            if set(experiment.claim_ids) & selected_claim_ids or set(
                experiment.technology_ids
            ) & selected_technology_ids:
                included.add(experiment.id)

    return included


def _with_connectivity(elements: list[dict]) -> tuple[list[dict], dict[str, int]]:
    nodes = [item for item in elements if "source" not in item["data"]]
    edges = [item for item in elements if "source" in item["data"]]
    adjacency: dict[str, set[str]] = {item["data"]["id"]: set() for item in nodes}
    for edge in edges:
        source = edge["data"]["source"]
        target = edge["data"]["target"]
        adjacency[source].add(target)
        adjacency[target].add(source)
    orphan_ids = {node_id for node_id, neighbors in adjacency.items() if not neighbors}
    for node in nodes:
        node["data"]["orphan"] = node["data"]["id"] in orphan_ids

    visited: set[str] = set()
    component_count = 0
    for node_id in adjacency:
        if node_id in visited:
            continue
        component_count += 1
        pending = [node_id]
        visited.add(node_id)
        while pending:
            current = pending.pop()
            for neighbor in adjacency[current] - visited:
                visited.add(neighbor)
                pending.append(neighbor)

    return [*nodes, *edges], {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "orphan_count": len(orphan_ids),
        "component_count": component_count,
    }


def graph_view(
    catalog: Catalog,
    knowledge_map: KnowledgeMap,
    project_root: Path = PROJECT_ROOT,
) -> dict:
    elements = graph_elements(catalog, project_root)
    if knowledge_map.selection_mode == "overview":
        allowed_node_ids = {
            item["data"]["id"]
            for item in elements
            if "source" not in item["data"]
            and not (
                item["data"].get("type") in {"knowledge", "document", "section"}
                and item["data"].get("visibility") == "private"
            )
        }
    else:
        allowed_node_ids = _topic_ids(catalog, knowledge_map, project_root)

    filtered = [
        item
        for item in elements
        if (
            item["data"]["id"] in allowed_node_ids
            if "source" not in item["data"]
            else item["data"]["source"] in allowed_node_ids
            and item["data"]["target"] in allowed_node_ids
        )
    ]
    connected_elements, metrics = _with_connectivity(filtered)
    counts: dict[str, int] = {}
    for item in connected_elements:
        if "source" in item["data"]:
            continue
        node_type = item["data"]["type"]
        counts[node_type] = counts.get(node_type, 0) + 1
    return {
        "elements": connected_elements,
        "metrics": metrics,
        "node_counts": counts,
        "map": knowledge_map.model_dump(mode="json"),
    }
