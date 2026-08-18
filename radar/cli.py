import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

from radar.collectors.github import latest_release, repository_metrics, search_repositories
from radar.collectors.pypi import package_metadata
from radar.indexing import rebuild_index
from radar.models import Change, DiscoveryCandidate, DiscoveryRun, PopularitySignal
from radar.paths import DATABASE_PATH, INBOX_ROOT, PROJECT_ROOT, STATE_ROOT
from radar.store import load_catalog


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _repository_name(url: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    return "/".join(parts[:2])


def _load_manifest(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _save_manifest(path: Path, manifest: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _save_change(change: Change) -> Path:
    target = INBOX_ROOT / "changes" / f"generated-{change.id}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(change.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return target


def _save_popularity(signal: PopularitySignal) -> Path:
    target = INBOX_ROOT / "metrics" / f"generated-{signal.id}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(signal.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return target


def _candidate_id(repository: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", repository.lower()).strip("-")
    return f"candidate-{slug}"


def _save_candidate(candidate: DiscoveryCandidate) -> Path:
    target = INBOX_ROOT / "candidates" / f"generated-{candidate.id}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(candidate.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return target


def _save_discovery_run(run: DiscoveryRun) -> Path:
    target = INBOX_ROOT / "discovery_runs" / f"{run.id}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(run.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return target


def collect() -> int:
    catalog = load_catalog()
    manifest_path = STATE_ROOT / "manifests" / "sources.json"
    manifest = _load_manifest(manifest_path)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    created = 0

    for technology in catalog.technologies:
        repository = _repository_name(str(technology.repository))
        metrics = repository_metrics(repository)
        _save_popularity(
            PopularitySignal(
                id=f"popularity-{technology.id}",
                technology_id=technology.id,
                github_stars=metrics["github_stars"],
                github_forks=metrics["github_forks"],
                last_activity_at=metrics["last_activity_at"],
                observed_at=now,
                source_url=metrics["source_url"],
            )
        )
        release_payload = latest_release(repository)
        release_hash = _hash(release_payload)
        release_key = f"github-release:{repository}"
        if manifest.get(release_key) != release_hash:
            release = release_payload.get("release")
            url = release.get("html_url") if release else str(technology.repository)
            title = (
                f"{technology.name} 发布 {release.get('tag_name')}"
                if release
                else f"{technology.name} 暂无 GitHub Release"
            )
            _save_change(
                Change(
                    id=f"{technology.id}-github-{release_hash[:10]}",
                    source_id=release_key,
                    technology_id=technology.id,
                    source_kind="GitHub Releases API",
                    title=title,
                    url=url,
                    detected_at=now,
                    content_hash=release_hash,
                    importance="high" if release else "low",
                    status="new",
                    summary="API 返回发生变化，等待 Codex 阅读 release 内容并判断是否影响已有结论。",
                )
            )
            manifest[release_key] = release_hash
            created += 1

        if technology.package:
            package_payload = package_metadata(technology.package)
            package_hash = _hash(package_payload)
            package_key = f"pypi:{technology.package}"
            if manifest.get(package_key) != package_hash:
                _save_change(
                    Change(
                        id=f"{technology.id}-pypi-{package_hash[:10]}",
                        source_id=package_key,
                        technology_id=technology.id,
                        source_kind="PyPI JSON API",
                        title=f"{technology.name} 包版本为 {package_payload['version']}",
                        url=package_payload["release_url"],
                        detected_at=now,
                        content_hash=package_hash,
                        importance="medium",
                        status="new",
                        summary="包版本事实已记录；这本身不代表技术优劣发生变化。",
                    )
                )
                manifest[package_key] = package_hash
                created += 1

    _save_manifest(manifest_path, manifest)
    rebuild_index(load_catalog(), DATABASE_PATH)
    print(f"Collected {created} material changes.")
    return created


def discover(per_query: int = 25) -> int:
    catalog = load_catalog()
    started_at = datetime.now(UTC).isoformat(timespec="seconds")
    known_repositories = {
        str(item.repository).rstrip("/").lower()
        for item in [*catalog.technologies, *catalog.discovery_candidates]
    }
    discovered: dict[str, dict] = {}
    observed_repositories: set[str] = set()
    known_matches: set[str] = set()
    fetched_result_count = 0
    incomplete_query_ids: list[str] = []
    query_total_counts: dict[str, int] = {}
    now = datetime.now(UTC).isoformat(timespec="seconds")

    for query in catalog.discovery_queries:
        result = search_repositories(query.query, per_page=per_query)
        query_total_counts[query.id] = result["total_count"]
        fetched_result_count += len(result["items"])
        if result["incomplete_results"]:
            incomplete_query_ids.append(query.id)
        for item in result["items"]:
            repository_url = (item.get("html_url") or "").rstrip("/")
            if not repository_url:
                continue
            key = repository_url.lower()
            observed_repositories.add(key)
            if key in known_repositories:
                known_matches.add(key)
                continue
            record = discovered.setdefault(
                key,
                {
                    **item,
                    "source_query_ids": [],
                    "category_ids": [],
                },
            )
            if query.id not in record["source_query_ids"]:
                record["source_query_ids"].append(query.id)
            for category_id in query.category_ids:
                if category_id not in record["category_ids"]:
                    record["category_ids"].append(category_id)

    created = 0
    for item in discovered.values():
        homepage = item.get("homepage")
        if homepage and not str(homepage).startswith(("http://", "https://")):
            homepage = None
        candidate = DiscoveryCandidate(
            id=_candidate_id(item["full_name"]),
            name=item["name"],
            repository=item["html_url"],
            homepage=homepage,
            description=item["description"] or "仓库暂无简介，等待人工判读。",
            category_ids=item["category_ids"],
            ecosystem=item["language"],
            status="discovered",
            relevance="unreviewed",
            review_note="由广度搜索自动发现；尚未判断是框架、应用、资源列表还是无关项。",
            source_query_ids=item["source_query_ids"],
            github_stars=item["stargazers_count"],
            github_forks=item["forks_count"],
            last_activity_at=item["pushed_at"],
            observed_at=now,
            license=item["license"],
            archived=item["archived"],
        )
        _save_candidate(candidate)
        created += 1

    completed_at = datetime.now(UTC).isoformat(timespec="microseconds")
    unique_result_count = len(observed_repositories)
    _save_discovery_run(
        DiscoveryRun(
            id=f"discovery-run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}",
            started_at=started_at,
            completed_at=completed_at,
            query_count=len(catalog.discovery_queries),
            fetched_result_count=fetched_result_count,
            unique_result_count=unique_result_count,
            known_result_count=len(known_matches),
            new_candidate_count=created,
            duplicate_hit_count=max(0, fetched_result_count - unique_result_count),
            new_unique_rate=(created / unique_result_count) if unique_result_count else 0,
            incomplete_query_ids=incomplete_query_ids,
            query_total_counts=query_total_counts,
        )
    )
    rebuild_index(load_catalog(), DATABASE_PATH)
    print(f"Discovered {created} new repositories for human triage.")
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Tech Radar maintenance commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("index", help="Rebuild the derived SQLite index")
    subparsers.add_parser("collect", help="Poll official APIs and record material changes")
    discover_parser = subparsers.add_parser(
        "discover", help="Run bounded breadth queries and save unreviewed candidates"
    )
    discover_parser.add_argument("--per-query", type=int, default=25)
    args = parser.parse_args()

    if args.command == "index":
        path = rebuild_index(load_catalog(), DATABASE_PATH)
        print(path)
    elif args.command == "collect":
        collect()
    elif args.command == "discover":
        discover(per_query=max(1, min(args.per_query, 100)))


if __name__ == "__main__":
    main()
