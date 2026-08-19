from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_primary_routes_render() -> None:
    for path in (
        "/",
        "/graph",
        "/discovery",
        "/documents",
        "/documents/doc-agent-research-method",
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


def test_graph_has_hover_document_reader() -> None:
    response = client.get("/graph")
    assert response.status_code == 200
    assert 'id="graph-document-preview"' in response.text
    assert "在章节上稍作停留" in response.text
    assert "滚轮上下阅读" in response.text
    assert "mermaid-11.16.1.min.js" in response.text
    assert "document-diagrams.js" in response.text


def test_document_preview_api_returns_full_document_and_section_target() -> None:
    response = client.get(
        "/api/documents/doc-agent-research-method/preview?section=section-1"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["section"] == "section-1"
    assert payload["section_title"] == "1. 文档是知识主体"
    assert 'id="section-1"' in payload["html"]
    assert 'id="section-4"' in payload["html"]
    assert payload["full_href"].endswith("#section-1")


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


def test_document_reader_is_the_primary_long_form_surface() -> None:
    response = client.get("/documents/doc-agent-research-method")
    assert response.status_code == 200
    assert "文档是知识主体" in response.text
    assert "本文目录" in response.text
    assert "/documents/doc-agent-research-method/research" in response.text
