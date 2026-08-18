import sqlite3

from radar.indexing import rebuild_index
from radar.paths import PROJECT_ROOT
from radar.store import graph_elements, load_catalog


def test_seed_catalog_loads() -> None:
    catalog = load_catalog()
    assert len(catalog.technologies) == 5
    assert len(catalog.capabilities) >= 5
    assert len(catalog.proposals) == 2
    assert len(catalog.knowledge_nodes) >= 3
    assert len(catalog.popularity_signals) == 5
    assert len(catalog.discovery_candidates) == 20
    assert len(catalog.discovery_categories) == 6
    assert len(catalog.discovery_queries) == 10
    assert len(catalog.discovery_sources) == 6


def test_graph_contains_nodes_and_edges() -> None:
    catalog = load_catalog()
    elements = graph_elements(catalog)
    nodes = [item for item in elements if "source" not in item["data"]]
    edges = [item for item in elements if "source" in item["data"]]
    assert any(item["data"]["type"] == "technology" for item in nodes)
    assert any(item["data"]["relation"] == "supports" for item in edges)
    assert any(item["data"]["type"] == "knowledge" for item in nodes)
    assert any(item["data"]["relation"] == "documented_by" for item in edges)

    connected_ids = {
        endpoint
        for edge in edges
        for endpoint in (edge["data"]["source"], edge["data"]["target"])
    }
    assert all(item["data"]["id"] in connected_ids for item in nodes)

    technology_sizes = {
        item["data"]["id"]: item["data"]["node_size"]
        for item in nodes
        if item["data"]["type"] == "technology"
    }
    assert max(technology_sizes.values()) > min(technology_sizes.values())

    candidate_nodes = [item for item in nodes if item["data"]["type"] == "candidate"]
    category_nodes = [
        item for item in nodes if item["data"]["type"] == "discovery_category"
    ]
    candidate_edges = [
        item for item in edges if item["data"]["relation"] == "classified_as"
    ]
    assert len(candidate_nodes) == 19
    assert len(category_nodes) == 6
    assert all(
        any(edge["data"]["source"] == node["data"]["id"] for edge in candidate_edges)
        for node in candidate_nodes
    )
    assert not any(item["data"]["id"] == "candidate-flowise" for item in nodes)
    assert len({item["data"]["node_size"] for item in candidate_nodes}) > 1

    adjacency: dict[str, set[str]] = {item["data"]["id"]: set() for item in nodes}
    for edge in edges:
        source = edge["data"]["source"]
        target = edge["data"]["target"]
        adjacency[source].add(target)
        adjacency[target].add(source)
    start = next(iter(adjacency))
    visited = {start}
    pending = [start]
    while pending:
        current = pending.pop()
        for neighbor in adjacency[current] - visited:
            visited.add(neighbor)
            pending.append(neighbor)
    assert visited == set(adjacency), "图谱不应再次裂成互不相连的群落"


def test_sqlite_index_is_rebuildable(tmp_path) -> None:
    path = rebuild_index(load_catalog(PROJECT_ROOT), tmp_path / "radar.db")
    assert path.exists()
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM discovery_candidates").fetchone()[0] == 20
        assert connection.execute("SELECT COUNT(*) FROM discovery_categories").fetchone()[0] == 6
        assert connection.execute("SELECT COUNT(*) FROM discovery_queries").fetchone()[0] == 10
        assert connection.execute("SELECT COUNT(*) FROM discovery_sources").fetchone()[0] == 6
        assert connection.execute("SELECT COUNT(*) FROM discovery_runs").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM conversation_sources").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM knowledge_node_provenance").fetchone()[0] >= 3
        assert connection.execute(
            "SELECT COUNT(*) FROM relationships WHERE relation = 'classified_as'"
        ).fetchone()[0] >= 24
