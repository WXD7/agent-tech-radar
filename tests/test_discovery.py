import yaml

from radar import cli
from radar.store import load_catalog


def test_discover_saves_new_results_as_unreviewed_candidates(tmp_path, monkeypatch) -> None:
    catalog = load_catalog()
    calls: list[tuple[str, int]] = []

    def fake_search(query: str, per_page: int = 25) -> dict:
        calls.append((query, per_page))
        return {
            "total_count": 1,
            "incomplete_results": False,
            "items": [
                {
                    "full_name": "example/new-agent-kit",
                    "name": "new-agent-kit",
                    "description": "A newly discovered agent SDK",
                    "html_url": "https://github.com/example/new-agent-kit",
                    "homepage": None,
                    "language": "Python",
                    "stargazers_count": 321,
                    "forks_count": 45,
                    "pushed_at": "2026-08-17T00:00:00Z",
                    "archived": False,
                    "license": "MIT",
                }
            ],
        }

    monkeypatch.setattr(cli, "INBOX_ROOT", tmp_path / "inbox")
    monkeypatch.setattr(cli, "DATABASE_PATH", tmp_path / "radar.db")
    monkeypatch.setattr(cli, "load_catalog", lambda: catalog)
    monkeypatch.setattr(cli, "search_repositories", fake_search)
    monkeypatch.setattr(cli, "rebuild_index", lambda catalog, path: path)

    assert cli.discover(per_query=7) == 1
    assert len(calls) == len(catalog.discovery_queries)
    assert all(per_page == 7 for _, per_page in calls)

    files = list((tmp_path / "inbox" / "candidates").glob("*.yaml"))
    assert len(files) == 1
    saved = yaml.safe_load(files[0].read_text(encoding="utf-8"))
    assert saved["status"] == "discovered"
    assert saved["relevance"] == "unreviewed"
    assert len(saved["source_query_ids"]) == len(catalog.discovery_queries)

    run_files = list((tmp_path / "inbox" / "discovery_runs").glob("*.yaml"))
    assert len(run_files) == 1
    run = yaml.safe_load(run_files[0].read_text(encoding="utf-8"))
    assert run["query_count"] == len(catalog.discovery_queries)
    assert run["fetched_result_count"] == len(catalog.discovery_queries)
    assert run["unique_result_count"] == 1
    assert run["new_candidate_count"] == 1
    assert run["duplicate_hit_count"] == len(catalog.discovery_queries) - 1
