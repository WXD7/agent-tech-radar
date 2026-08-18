import httpx


BASE_URL = "http://127.0.0.1:8765"
ROUTES = [
    "/",
    "/graph",
    "/discovery",
    "/nodes",
    "/nodes/new?target_id=tech-pydantic-ai&node_type=question",
    "/nodes/node-pydantic-retry-question",
    "/nodes/node-pydantic-retry-question/edit",
    "/changes",
    "/reviews",
    "/reviews/proposal-pydantic-output",
    "/experiments",
    "/technologies/tech-pydantic-ai",
    "/api/graph",
]


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=10, trust_env=False) as client:
        for route in ROUTES:
            response = client.get(route)
            response.raise_for_status()
            print(f"{response.status_code} {route}")
        graph = client.get("/api/graph").json()
        if not graph.get("elements"):
            raise RuntimeError("Graph API returned no elements")


if __name__ == "__main__":
    main()
