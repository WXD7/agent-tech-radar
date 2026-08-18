from datetime import UTC, date, datetime
from math import sqrt
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

from radar.models import (
    Capability,
    Catalog,
    Change,
    Claim,
    ConversationSource,
    DiscoveryCandidate,
    DiscoveryCategory,
    DiscoveryQuery,
    DiscoveryRun,
    DiscoverySource,
    Evidence,
    Experiment,
    KnowledgeNode,
    PopularitySignal,
    Proposal,
    Technology,
)
from radar.paths import INBOX_ROOT, KNOWLEDGE_ROOT, PROPOSALS_ROOT, PROJECT_ROOT


ModelT = TypeVar("ModelT", bound=BaseModel)


def normalize_yaml(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [normalize_yaml(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_yaml(item) for key, item in value.items()}
    return value


def _load_records(directory: Path, model: type[ModelT]) -> list[ModelT]:
    records: dict[str, ModelT] = {}
    if not directory.exists():
        return []

    for path in sorted(directory.glob("*.yaml")):
        raw = normalize_yaml(yaml.safe_load(path.read_text(encoding="utf-8")))
        if raw is None:
            continue
        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            record = model.model_validate(item)
            records[getattr(record, "id")] = record
    return list(records.values())


def load_catalog(project_root: Path = PROJECT_ROOT) -> Catalog:
    knowledge = project_root / KNOWLEDGE_ROOT.relative_to(PROJECT_ROOT)
    proposals = project_root / PROPOSALS_ROOT.relative_to(PROJECT_ROOT)
    inbox = project_root / INBOX_ROOT.relative_to(PROJECT_ROOT)
    experiments = project_root / "experiments" / "catalog"
    discovery = project_root / "discovery"

    return Catalog(
        technologies=_load_records(knowledge / "technologies", Technology),
        capabilities=_load_records(knowledge / "capabilities", Capability),
        claims=_load_records(knowledge / "claims", Claim),
        evidence=_load_records(knowledge / "evidence", Evidence),
        proposals=_load_records(proposals, Proposal),
        changes=_load_records(inbox / "changes", Change),
        experiments=_load_records(experiments, Experiment),
        popularity_signals=_load_records(inbox / "metrics", PopularitySignal),
        knowledge_nodes=_load_records(knowledge / "nodes", KnowledgeNode),
        conversation_sources=_load_records(
            knowledge / "conversations", ConversationSource
        ),
        discovery_categories=_load_records(discovery / "categories", DiscoveryCategory),
        discovery_sources=_load_records(discovery / "sources", DiscoverySource),
        discovery_queries=_load_records(discovery / "queries", DiscoveryQuery),
        discovery_candidates=_load_records(inbox / "candidates", DiscoveryCandidate),
        discovery_runs=_load_records(inbox / "discovery_runs", DiscoveryRun),
    )


def _activity_score(value: str) -> int:
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return 20
    age_days = max(0, (datetime.now(UTC) - observed).days)
    if age_days <= 14:
        return 100
    if age_days <= 60:
        return 75
    if age_days <= 180:
        return 40
    return 15


def _visual_values(
    stars: int,
    forks: int,
    last_activity_at: str,
    max_stars: int,
    max_forks: int,
) -> dict[str, int | str]:
    scale = (
        0.72 * sqrt(stars / max(max_stars, 1))
        + 0.28 * sqrt(forks / max(max_forks, 1))
    )
    score = round(
        (scale * 0.8 + (_activity_score(last_activity_at) / 100) * 0.2) * 100
    )
    if stars >= 50_000:
        tier = "主流"
    elif stars >= 25_000:
        tier = "成熟"
    elif stars >= 10_000:
        tier = "成长"
    else:
        tier = "小众"
    return {
        "popularity_score": score,
        "node_size": round(76 + score * 0.72),
        "popularity_tier": tier,
    }


def _popularity_visuals(catalog: Catalog) -> dict[str, dict[str, int | str]]:
    signals = catalog.popularity_signals
    candidates = [
        item
        for item in catalog.discovery_candidates
        if item.status not in {"excluded", "promoted"} and not item.archived
    ]
    max_stars = max(
        [item.github_stars for item in signals]
        + [item.github_stars for item in candidates]
        + [1]
    )
    max_forks = max(
        [item.github_forks for item in signals]
        + [item.github_forks for item in candidates]
        + [1]
    )
    visuals: dict[str, dict[str, int | str]] = {}
    for item in signals:
        visuals[item.technology_id] = _visual_values(
            item.github_stars,
            item.github_forks,
            item.last_activity_at,
            max_stars,
            max_forks,
        )
    for item in candidates:
        visuals[item.id] = _visual_values(
            item.github_stars,
            item.github_forks,
            item.last_activity_at,
            max_stars,
            max_forks,
        )
    return visuals


def graph_elements(catalog: Catalog) -> list[dict]:
    nodes: list[dict] = []
    edges: list[dict] = []
    popularity_visuals = _popularity_visuals(catalog)
    popularity = {item.technology_id: item for item in catalog.popularity_signals}

    def add_edge(edge_id: str, source: str, target: str, relation: str) -> None:
        edges.append(
            {
                "data": {
                    "id": edge_id,
                    "source": source,
                    "target": target,
                    "relation": relation,
                }
            }
        )

    for technology in catalog.technologies:
        signal = popularity.get(technology.id)
        visual = popularity_visuals.get(
            technology.id,
            {"popularity_score": 30, "node_size": 98, "popularity_tier": "暂无信号"},
        )
        nodes.append(
            {
                "data": {
                    "id": technology.id,
                    "label": technology.name,
                    "type": "technology",
                    "status": technology.status,
                    "description": technology.description,
                    "href": f"/technologies/{technology.id}",
                    **visual,
                    "github_stars": signal.github_stars if signal else None,
                    "github_forks": signal.github_forks if signal else None,
                    "last_activity_at": signal.last_activity_at if signal else None,
                    "popularity_observed_at": signal.observed_at if signal else None,
                }
            }
        )
        for capability_id in technology.capability_ids:
            add_edge(
                f"edge-{technology.id}-{capability_id}",
                technology.id,
                capability_id,
                "provides",
            )
        for category_id in technology.discovery_category_ids:
            add_edge(
                f"edge-{technology.id}-classified-as-{category_id}",
                technology.id,
                category_id,
                "classified_as",
            )
        for evidence_id in technology.source_ids:
            add_edge(
                f"edge-{technology.id}-documented-by-{evidence_id}",
                technology.id,
                evidence_id,
                "documented_by",
            )

    for capability in catalog.capabilities:
        nodes.append(
            {
                "data": {
                    "id": capability.id,
                    "label": capability.name,
                    "type": "capability",
                    "status": capability.priority,
                    "description": capability.description,
                }
            }
        )

    for claim in catalog.claims:
        nodes.append(
            {
                "data": {
                    "id": claim.id,
                    "label": claim.text,
                    "type": "claim",
                    "status": claim.status,
                    "description": claim.text,
                    "confidence": claim.confidence,
                }
            }
        )
        add_edge(
            f"edge-{claim.id}-{claim.technology_id}",
            claim.id,
            claim.technology_id,
            "about",
        )
        add_edge(
            f"edge-{claim.id}-{claim.capability_id}",
            claim.id,
            claim.capability_id,
            "evaluates",
        )

    for item in catalog.evidence:
        nodes.append(
            {
                "data": {
                    "id": item.id,
                    "label": item.title,
                    "type": "evidence",
                    "status": item.source_type,
                    "description": item.summary,
                    "href": str(item.url),
                }
            }
        )
        for claim_id in item.supports_claim_ids:
            add_edge(
                f"edge-{item.id}-supports-{claim_id}",
                item.id,
                claim_id,
                "supports",
            )
        for claim_id in item.contradicts_claim_ids:
            add_edge(
                f"edge-{item.id}-contradicts-{claim_id}",
                item.id,
                claim_id,
                "contradicts",
            )

    for experiment in catalog.experiments:
        nodes.append(
            {
                "data": {
                    "id": experiment.id,
                    "label": experiment.name,
                    "type": "experiment",
                    "status": experiment.status,
                    "description": experiment.hypothesis,
                }
            }
        )
        for claim_id in experiment.claim_ids:
            add_edge(
                f"edge-{experiment.id}-{claim_id}",
                experiment.id,
                claim_id,
                "tests",
            )
        for technology_id in experiment.technology_ids:
            add_edge(
                f"edge-{experiment.id}-tests-{technology_id}",
                experiment.id,
                technology_id,
                "tests_technology",
            )

    visible_candidates = [
        item
        for item in catalog.discovery_candidates
        if item.status == "triaged" and not item.archived
    ]
    visible_category_ids = {
        category_id
        for item in visible_candidates
        for category_id in item.category_ids
    } | {
        category_id
        for technology in catalog.technologies
        for category_id in technology.discovery_category_ids
    }
    for category in catalog.discovery_categories:
        if category.id not in visible_category_ids:
            continue
        nodes.append(
            {
                "data": {
                    "id": category.id,
                    "label": category.name,
                    "type": "discovery_category",
                    "status": category.priority,
                    "description": category.description,
                    "href": f"/discovery#{category.id}",
                }
            }
        )

    for candidate in visible_candidates:
        visual = popularity_visuals.get(
            candidate.id,
            {"popularity_score": 30, "node_size": 98, "popularity_tier": "暂无信号"},
        )
        nodes.append(
            {
                "data": {
                    "id": candidate.id,
                    "label": candidate.name,
                    "type": "candidate",
                    "status": candidate.status,
                    "description": candidate.description,
                    "href": f"/discovery#{candidate.id}",
                    "repository": str(candidate.repository),
                    "ecosystem": candidate.ecosystem,
                    "relevance": candidate.relevance,
                    "github_stars": candidate.github_stars,
                    "github_forks": candidate.github_forks,
                    "last_activity_at": candidate.last_activity_at,
                    "popularity_observed_at": candidate.observed_at,
                    **visual,
                }
            }
        )
        for category_id in candidate.category_ids:
            add_edge(
                f"edge-{candidate.id}-classified-as-{category_id}",
                candidate.id,
                category_id,
                "classified_as",
            )

    active_knowledge_nodes = [
        item for item in catalog.knowledge_nodes if item.status != "archived"
    ]
    active_knowledge_ids = {item.id for item in active_knowledge_nodes}
    for item in active_knowledge_nodes:
        nodes.append(
            {
                "data": {
                    "id": item.id,
                    "label": item.title,
                    "type": "knowledge",
                    "subtype": item.node_type,
                    "status": item.status,
                    "description": item.body,
                    "href": f"/nodes/{item.id}",
                    "editable": True,
                    "target_id": item.target_id,
                    "created_at": item.created_at,
                    "source_kind": item.source_kind,
                    "verification_status": item.verification_status,
                }
            }
        )
        edge_target = (
            item.parent_id
            if item.parent_id and item.parent_id in active_knowledge_ids
            else item.target_id
        )
        add_edge(
            f"edge-{item.id}-{item.relation_type}-{edge_target}",
            item.id,
            edge_target,
            item.relation_type,
        )

    node_ids = {item["data"]["id"] for item in nodes}
    valid_edges = [
        item
        for item in edges
        if item["data"]["source"] in node_ids and item["data"]["target"] in node_ids
    ]
    return [*nodes, *valid_edges]
