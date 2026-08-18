import os

import httpx


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "agent-tech-radar-demo",
    }
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    return headers


def latest_release(repository: str) -> dict:

    response = httpx.get(
        f"https://api.github.com/repos/{repository}/releases/latest",
        headers=_headers(),
        timeout=20,
        follow_redirects=True,
    )
    if response.status_code == 404:
        return {"repository": repository, "release": None}
    response.raise_for_status()
    payload = response.json()
    return {
        "repository": repository,
        "release": {
            "tag_name": payload.get("tag_name"),
            "name": payload.get("name"),
            "published_at": payload.get("published_at"),
            "html_url": payload.get("html_url"),
            "body": payload.get("body") or "",
        },
    }


def repository_metrics(repository: str) -> dict:
    response = httpx.get(
        f"https://api.github.com/repos/{repository}",
        headers=_headers(),
        timeout=20,
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    return {
        "repository": repository,
        "github_stars": payload.get("stargazers_count", 0),
        "github_forks": payload.get("forks_count", 0),
        "last_activity_at": payload.get("pushed_at") or payload.get("updated_at"),
        "source_url": payload.get("url"),
    }


def search_repositories(query: str, per_page: int = 25) -> dict:
    response = httpx.get(
        "https://api.github.com/search/repositories",
        params={
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": max(1, min(per_page, 100)),
        },
        headers=_headers(),
        timeout=30,
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    return {
        "total_count": payload.get("total_count", 0),
        "incomplete_results": payload.get("incomplete_results", False),
        "items": [
            {
                "full_name": item.get("full_name"),
                "name": item.get("name"),
                "description": item.get("description") or "",
                "html_url": item.get("html_url"),
                "homepage": item.get("homepage") or None,
                "language": item.get("language") or "Unknown",
                "stargazers_count": item.get("stargazers_count", 0),
                "forks_count": item.get("forks_count", 0),
                "pushed_at": item.get("pushed_at") or item.get("updated_at"),
                "archived": item.get("archived", False),
                "license": (item.get("license") or {}).get("spdx_id"),
            }
            for item in payload.get("items", [])
        ],
    }
