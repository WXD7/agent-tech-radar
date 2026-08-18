import httpx


def package_metadata(package: str) -> dict:
    response = httpx.get(
        f"https://pypi.org/pypi/{package}/json",
        headers={"User-Agent": "agent-tech-radar-demo"},
        timeout=20,
        follow_redirects=True,
    )
    response.raise_for_status()
    info = response.json()["info"]
    return {
        "package": package,
        "version": info.get("version"),
        "requires_python": info.get("requires_python"),
        "project_url": info.get("project_url"),
        "release_url": f"https://pypi.org/project/{package}/{info.get('version')}/",
    }

