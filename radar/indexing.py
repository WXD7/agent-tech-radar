import json
import sqlite3
from pathlib import Path

from radar.models import Catalog
from radar.paths import DATABASE_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS technologies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    description TEXT NOT NULL,
    repository TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS capabilities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    group_name TEXT NOT NULL,
    priority TEXT NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    technology_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence INTEGER NOT NULL,
    text TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    summary TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    technology_id TEXT NOT NULL,
    status TEXT NOT NULL,
    action TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS changes (
    id TEXT PRIMARY KEY,
    technology_id TEXT,
    status TEXT NOT NULL,
    importance TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    title TEXT NOT NULL,
    source_kind TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    last_run_at TEXT
);
CREATE TABLE IF NOT EXISTS popularity_signals (
    id TEXT PRIMARY KEY,
    technology_id TEXT NOT NULL,
    github_stars INTEGER NOT NULL,
    github_forks INTEGER NOT NULL,
    last_activity_at TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    source_url TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS discovery_categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    priority TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS discovery_sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    cadence TEXT NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS discovery_queries (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    query TEXT NOT NULL,
    category_ids_json TEXT NOT NULL,
    ecosystem_focus TEXT NOT NULL,
    cadence TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS discovery_candidates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    repository TEXT NOT NULL,
    homepage TEXT,
    description TEXT NOT NULL,
    category_ids_json TEXT NOT NULL,
    ecosystem TEXT NOT NULL,
    status TEXT NOT NULL,
    relevance TEXT NOT NULL,
    review_note TEXT,
    source_query_ids_json TEXT NOT NULL,
    github_stars INTEGER NOT NULL,
    github_forks INTEGER NOT NULL,
    last_activity_at TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    license TEXT,
    archived INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS discovery_runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    query_count INTEGER NOT NULL,
    fetched_result_count INTEGER NOT NULL,
    unique_result_count INTEGER NOT NULL,
    known_result_count INTEGER NOT NULL,
    new_candidate_count INTEGER NOT NULL,
    duplicate_hit_count INTEGER NOT NULL,
    new_unique_rate REAL NOT NULL,
    incomplete_query_ids_json TEXT NOT NULL,
    query_total_counts_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    node_type TEXT NOT NULL,
    status TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    parent_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversation_sources (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    thread_url TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT,
    imported_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_synced_at TEXT,
    last_synced_turn_id TEXT
);
CREATE TABLE IF NOT EXISTS conversation_anchors (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    conversation_source_id TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    role TEXT NOT NULL,
    anchor_kind TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    locator_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    content_path TEXT NOT NULL,
    document_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    visibility TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    conversation_source_ids_json TEXT NOT NULL,
    technology_ids_json TEXT NOT NULL,
    capability_ids_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_node_provenance (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_id TEXT,
    relation TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_technologies_status ON technologies(status);
CREATE INDEX IF NOT EXISTS idx_claims_technology_status ON claims(technology_id, status);
CREATE INDEX IF NOT EXISTS idx_proposals_status_created ON proposals(status, created_at);
CREATE INDEX IF NOT EXISTS idx_changes_status_detected ON changes(status, detected_at);
CREATE INDEX IF NOT EXISTS idx_popularity_technology ON popularity_signals(technology_id);
CREATE INDEX IF NOT EXISTS idx_discovery_candidates_status_relevance ON discovery_candidates(status, relevance);
CREATE INDEX IF NOT EXISTS idx_discovery_candidates_ecosystem ON discovery_candidates(ecosystem);
CREATE INDEX IF NOT EXISTS idx_discovery_candidates_repository ON discovery_candidates(repository);
CREATE INDEX IF NOT EXISTS idx_discovery_candidates_activity ON discovery_candidates(last_activity_at);
CREATE INDEX IF NOT EXISTS idx_discovery_runs_completed ON discovery_runs(completed_at);
CREATE INDEX IF NOT EXISTS idx_knowledge_type_status ON knowledge_nodes(node_type, status);
CREATE INDEX IF NOT EXISTS idx_knowledge_target ON knowledge_nodes(target_id);
CREATE INDEX IF NOT EXISTS idx_conversation_status ON conversation_sources(status);
CREATE INDEX IF NOT EXISTS idx_conversation_thread ON conversation_sources(thread_id);
CREATE INDEX IF NOT EXISTS idx_anchor_node ON conversation_anchors(node_id);
CREATE INDEX IF NOT EXISTS idx_anchor_source ON conversation_anchors(conversation_source_id);
CREATE INDEX IF NOT EXISTS idx_research_document_status ON research_documents(status, visibility);
CREATE INDEX IF NOT EXISTS idx_node_provenance_node ON knowledge_node_provenance(node_id);
CREATE INDEX IF NOT EXISTS idx_node_provenance_source ON knowledge_node_provenance(source_id);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_id);
"""


def rebuild_index(catalog: Catalog, database_path: Path = DATABASE_PATH) -> Path:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(SCHEMA)
        with connection:
            for table in (
                "technologies",
                "capabilities",
                "claims",
                "evidence",
                "proposals",
                "changes",
                "experiments",
                "popularity_signals",
                "discovery_categories",
                "discovery_sources",
                "discovery_queries",
                "discovery_candidates",
                "discovery_runs",
                "knowledge_nodes",
                "conversation_sources",
                "conversation_anchors",
                "research_documents",
                "knowledge_node_provenance",
                "relationships",
            ):
                connection.execute(f"DELETE FROM {table}")

            connection.executemany(
                "INSERT INTO technologies VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.id,
                        item.name,
                        item.kind,
                        item.status,
                        item.description,
                        str(item.repository),
                    )
                    for item in catalog.technologies
                ],
            )
            connection.executemany(
                "INSERT INTO capabilities VALUES (?, ?, ?, ?, ?)",
                [
                    (item.id, item.name, item.group, item.priority, item.description)
                    for item in catalog.capabilities
                ],
            )
            connection.executemany(
                "INSERT INTO claims VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.id,
                        item.technology_id,
                        item.capability_id,
                        item.status,
                        item.confidence,
                        item.text,
                        item.updated_at,
                    )
                    for item in catalog.claims
                ],
            )
            connection.executemany(
                "INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.id,
                        item.title,
                        str(item.url),
                        item.source_type,
                        item.retrieved_at,
                        item.summary,
                    )
                    for item in catalog.evidence
                ],
            )
            connection.executemany(
                "INSERT INTO proposals VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.id,
                        item.technology_id,
                        item.status,
                        item.action,
                        item.title,
                        item.created_at,
                    )
                    for item in catalog.proposals
                ],
            )
            connection.executemany(
                "INSERT INTO changes VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.id,
                        item.technology_id,
                        item.status,
                        item.importance,
                        item.detected_at,
                        item.title,
                        item.source_kind,
                    )
                    for item in catalog.changes
                ],
            )
            connection.executemany(
                "INSERT INTO experiments VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        item.id,
                        item.name,
                        item.status,
                        item.hypothesis,
                        item.last_run_at,
                    )
                    for item in catalog.experiments
                ],
            )
            connection.executemany(
                "INSERT INTO popularity_signals VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.id,
                        item.technology_id,
                        item.github_stars,
                        item.github_forks,
                        item.last_activity_at,
                        item.observed_at,
                        str(item.source_url),
                    )
                    for item in catalog.popularity_signals
                ],
            )
            connection.executemany(
                "INSERT INTO discovery_categories VALUES (?, ?, ?, ?)",
                [
                    (item.id, item.name, item.description, item.priority)
                    for item in catalog.discovery_categories
                ],
            )
            connection.executemany(
                "INSERT INTO discovery_sources VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.id,
                        item.name,
                        item.source_type,
                        item.role,
                        item.status,
                        item.cadence,
                        item.description,
                    )
                    for item in catalog.discovery_sources
                ],
            )
            connection.executemany(
                "INSERT INTO discovery_queries VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.id,
                        item.name,
                        item.query,
                        json.dumps(item.category_ids, ensure_ascii=False),
                        item.ecosystem_focus,
                        item.cadence,
                    )
                    for item in catalog.discovery_queries
                ],
            )
            connection.executemany(
                "INSERT INTO discovery_candidates VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.id,
                        item.name,
                        str(item.repository),
                        str(item.homepage) if item.homepage else None,
                        item.description,
                        json.dumps(item.category_ids, ensure_ascii=False),
                        item.ecosystem,
                        item.status,
                        item.relevance,
                        item.review_note,
                        json.dumps(item.source_query_ids, ensure_ascii=False),
                        item.github_stars,
                        item.github_forks,
                        item.last_activity_at,
                        item.observed_at,
                        item.license,
                        int(item.archived),
                    )
                    for item in catalog.discovery_candidates
                ],
            )
            connection.executemany(
                "INSERT INTO discovery_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.id,
                        item.started_at,
                        item.completed_at,
                        item.query_count,
                        item.fetched_result_count,
                        item.unique_result_count,
                        item.known_result_count,
                        item.new_candidate_count,
                        item.duplicate_hit_count,
                        item.new_unique_rate,
                        json.dumps(item.incomplete_query_ids, ensure_ascii=False),
                        json.dumps(item.query_total_counts, ensure_ascii=False),
                    )
                    for item in catalog.discovery_runs
                ],
            )
            connection.executemany(
                "INSERT INTO knowledge_nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.id,
                        item.title,
                        item.body,
                        item.node_type,
                        item.status,
                        item.target_id,
                        item.relation_type,
                        item.parent_id,
                        item.created_at,
                        item.updated_at,
                    )
                    for item in catalog.knowledge_nodes
                ],
            )
            connection.executemany(
                "INSERT INTO conversation_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.id,
                        item.title,
                        item.thread_id,
                        item.thread_url,
                        item.status,
                        item.summary,
                        item.imported_at,
                        item.updated_at,
                        item.last_synced_at,
                        item.last_synced_turn_id,
                    )
                    for item in catalog.conversation_sources
                ],
            )
            connection.executemany(
                "INSERT INTO conversation_anchors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.id,
                        item.node_id,
                        item.conversation_source_id,
                        item.turn_id,
                        item.item_id,
                        item.role,
                        item.anchor_kind,
                        item.excerpt,
                        item.locator_text,
                        item.content_hash,
                        item.captured_at,
                        item.status,
                    )
                    for item in catalog.conversation_anchors
                ],
            )
            connection.executemany(
                "INSERT INTO research_documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.id,
                        item.title,
                        item.summary,
                        item.content_path,
                        item.document_kind,
                        item.status,
                        item.visibility,
                        item.verification_status,
                        json.dumps(item.conversation_source_ids, ensure_ascii=False),
                        json.dumps(item.technology_ids, ensure_ascii=False),
                        json.dumps(item.capability_ids, ensure_ascii=False),
                        item.updated_at,
                    )
                    for item in catalog.research_documents
                ],
            )

            provenance: list[tuple[str, str, str, str | None, str]] = []
            for node in catalog.knowledge_nodes:
                provenance.append(
                    (
                        f"{node.id}:origin:{node.source_kind}",
                        node.id,
                        node.source_kind,
                        None,
                        "originated_as",
                    )
                )
                provenance.extend(
                    (
                        f"{node.id}:conversation:{source_id}",
                        node.id,
                        node.source_kind,
                        source_id,
                        "summarized_from",
                    )
                    for source_id in node.conversation_source_ids
                )
                provenance.extend(
                    (
                        f"{node.id}:evidence:{evidence_id}",
                        node.id,
                        node.source_kind,
                        evidence_id,
                        "verified_by",
                    )
                    for evidence_id in node.evidence_ids
                )
            connection.executemany(
                "INSERT INTO knowledge_node_provenance VALUES (?, ?, ?, ?, ?)",
                provenance,
            )

            relationships: list[tuple[str, str, str, str, str]] = []
            for technology in catalog.technologies:
                for capability_id in technology.capability_ids:
                    relationships.append(
                        (
                            f"{technology.id}:provides:{capability_id}",
                            technology.id,
                            capability_id,
                            "provides",
                            "{}",
                        )
                    )
                for category_id in technology.discovery_category_ids:
                    relationships.append(
                        (
                            f"{technology.id}:classified_as:{category_id}",
                            technology.id,
                            category_id,
                            "classified_as",
                            json.dumps({"layer": "evaluated"}, ensure_ascii=False),
                        )
                    )
                for evidence_id in technology.source_ids:
                    relationships.append(
                        (
                            f"{technology.id}:documented_by:{evidence_id}",
                            technology.id,
                            evidence_id,
                            "documented_by",
                            "{}",
                        )
                    )
            for candidate in catalog.discovery_candidates:
                for category_id in candidate.category_ids:
                    relationships.append(
                        (
                            f"{candidate.id}:classified_as:{category_id}",
                            candidate.id,
                            category_id,
                            "classified_as",
                            json.dumps(
                                {
                                    "status": candidate.status,
                                    "relevance": candidate.relevance,
                                },
                                ensure_ascii=False,
                            ),
                        )
                    )
            for claim in catalog.claims:
                relationships.extend(
                    [
                        (
                            f"{claim.id}:about:{claim.technology_id}",
                            claim.id,
                            claim.technology_id,
                            "about",
                            json.dumps({"confidence": claim.confidence}),
                        ),
                        (
                            f"{claim.id}:evaluates:{claim.capability_id}",
                            claim.id,
                            claim.capability_id,
                            "evaluates",
                            "{}",
                        ),
                    ]
                )
            for evidence in catalog.evidence:
                for claim_id in evidence.supports_claim_ids:
                    relationships.append(
                        (
                            f"{evidence.id}:supports:{claim_id}",
                            evidence.id,
                            claim_id,
                            "supports",
                            "{}",
                        )
                    )
                for claim_id in evidence.contradicts_claim_ids:
                    relationships.append(
                        (
                            f"{evidence.id}:contradicts:{claim_id}",
                            evidence.id,
                            claim_id,
                            "contradicts",
                            "{}",
                        )
                    )
            for experiment in catalog.experiments:
                for claim_id in experiment.claim_ids:
                    relationships.append(
                        (
                            f"{experiment.id}:tests:{claim_id}",
                            experiment.id,
                            claim_id,
                            "tests",
                            "{}",
                        )
                    )
                for technology_id in experiment.technology_ids:
                    relationships.append(
                        (
                            f"{experiment.id}:tests_technology:{technology_id}",
                            experiment.id,
                            technology_id,
                            "tests_technology",
                            "{}",
                        )
                    )
            for node in catalog.knowledge_nodes:
                target_id = node.parent_id or node.target_id
                relationships.append(
                    (
                        f"{node.id}:{node.relation_type}:{target_id}",
                        node.id,
                        target_id,
                        node.relation_type,
                        json.dumps({"status": node.status}, ensure_ascii=False),
                    )
                )
                for source_id in node.conversation_source_ids:
                    relationships.append(
                        (
                            f"{source_id}:summarized_into:{node.id}",
                            source_id,
                            node.id,
                            "summarized_into",
                            json.dumps(
                                {"verification_status": node.verification_status},
                                ensure_ascii=False,
                            ),
                        )
                    )
                for evidence_id in node.evidence_ids:
                    relationships.append(
                        (
                            f"{evidence_id}:verifies_note:{node.id}",
                            evidence_id,
                            node.id,
                            "verifies_note",
                            json.dumps(
                                {"verification_status": node.verification_status},
                                ensure_ascii=False,
                            ),
                        )
                    )
            for document in catalog.research_documents:
                for source_id in document.conversation_source_ids:
                    relationships.append(
                        (
                            f"{source_id}:summarized_into_document:{document.id}",
                            source_id,
                            document.id,
                            "summarized_into_document",
                            json.dumps(
                                {"verification_status": document.verification_status},
                                ensure_ascii=False,
                            ),
                        )
                    )
                for target_id in [
                    *document.technology_ids,
                    *document.capability_ids,
                ]:
                    relationships.append(
                        (
                            f"{document.id}:covers:{target_id}",
                            document.id,
                            target_id,
                            "covers",
                            "{}",
                        )
                    )
            connection.executemany("INSERT INTO relationships VALUES (?, ?, ?, ?, ?)", relationships)
            connection.execute("PRAGMA optimize")
    finally:
        connection.close()
    return database_path
