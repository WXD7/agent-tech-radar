from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_primary_routes_render() -> None:
    for path in (
        "/",
        "/graph",
        "/discovery",
        "/nodes",
        "/nodes/new",
        "/conversations/import",
        "/research/tech-pydantic-ai",
        "/changes",
        "/reviews",
        "/experiments",
    ):
        response = client.get(path)
        assert response.status_code == 200, path


def test_discovery_page_keeps_candidates_separate_from_evaluated_tech() -> None:
    response = client.get("/discovery")
    assert response.status_code == 200
    assert "已评估技术" in response.text
    assert "待评估候选" in response.text
    assert "Google Agent Development Kit" in response.text
    assert "已排除，但不遗忘" in response.text


def test_graph_api_has_elements() -> None:
    response = client.get("/api/graph")
    assert response.status_code == 200
    assert response.json()["elements"]


def test_research_handoff_contains_codex_deep_link() -> None:
    response = client.get("/research/tech-pydantic-ai")
    assert response.status_code == 200
    assert "codex://new?" in response.text
    assert "在 Codex 中继续研究" in response.text


def test_technology_detail_renders() -> None:
    response = client.get("/technologies/tech-pydantic-ai")
    assert response.status_code == 200
    assert "Pydantic AI" in response.text


def test_knowledge_node_detail_and_edit_render() -> None:
    for path in (
        "/nodes/node-pydantic-retry-question",
        "/nodes/node-pydantic-retry-question/edit",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "复杂嵌套校验失败" in response.text
