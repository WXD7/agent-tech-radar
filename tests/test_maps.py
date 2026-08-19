import shutil

from fastapi.testclient import TestClient

import app.main as main
from radar.conversations import create_conversation_source
from radar.maps import add_node_to_map, create_knowledge_map, graph_view, resolve_map
from radar.nodes import create_node
from radar.paths import PROJECT_ROOT
from radar.store import load_catalog


def _copy_project_data(tmp_path) -> None:
    for directory in (
        "knowledge",
        "proposals",
        "inbox",
        "experiments",
        "discovery",
    ):
        shutil.copytree(PROJECT_ROOT / directory, tmp_path / directory)


def test_topic_map_keeps_private_notes_separate_and_connected(tmp_path) -> None:
    _copy_project_data(tmp_path)
    source = create_conversation_source(
        title="专题研究会话",
        thread_reference="codex://threads/018f2a6c-7b3d-7e4f-8a9b-1c2d3e4f5a6b",
        project_root=tmp_path,
    )
    node = create_node(
        title="只进入专题图谱的私有笔记",
        body="这条笔记应通过能力节点连接到相关技术，而不进入共享全景。",
        node_type="note",
        target_id="cap-human-loop",
        relation_type="extends",
        source_kind="codex_conversation",
        conversation_source_ids=[source.id],
        visibility="private",
        project_root=tmp_path,
    )
    topic_map = create_knowledge_map(
        map_id="map-private-topic",
        title="私有专题图谱",
        description="用于验证专题隔离与关系闭合。",
        visibility="private",
        conversation_source_ids=[source.id],
        context_ids=["tech-langgraph"],
        project_root=tmp_path,
    )
    catalog = load_catalog(tmp_path)

    overview = graph_view(catalog, resolve_map(catalog))
    topic = graph_view(catalog, topic_map)
    overview_ids = {
        item["data"]["id"]
        for item in overview["elements"]
        if "source" not in item["data"]
    }
    topic_ids = {
        item["data"]["id"]
        for item in topic["elements"]
        if "source" not in item["data"]
    }

    assert node.id not in overview_ids
    assert node.id in topic_ids
    assert topic["metrics"]["orphan_count"] == 0
    assert topic["metrics"]["component_count"] == 1


def test_graph_page_can_select_a_topic_map(tmp_path, monkeypatch) -> None:
    _copy_project_data(tmp_path)
    create_knowledge_map(
        map_id="map-pydantic-topic",
        title="PydanticAI 专题图谱",
        description="只观察 PydanticAI 及其相关能力和证据。",
        visibility="shared",
        node_ids=["node-pydantic-retry-question"],
        context_ids=["tech-pydantic-ai"],
        project_root=tmp_path,
    )
    monkeypatch.setattr(main, "APP_PROJECT_ROOT", tmp_path)

    with TestClient(main.app) as client:
        page = client.get("/graph?map_id=map-pydantic-topic")
        assert page.status_code == 200
        assert "选择研究主题" in page.text
        assert "PydanticAI 专题图谱" in page.text
        data = client.get("/api/graph?map_id=map-pydantic-topic").json()
        assert data["map"]["id"] == "map-pydantic-topic"
        assert data["metrics"]["orphan_count"] == 0
        assert data["metrics"]["component_count"] == 1


def test_manual_note_can_be_added_to_its_current_topic_map(tmp_path) -> None:
    _copy_project_data(tmp_path)
    topic_map = create_knowledge_map(
        map_id="map-manual-learning",
        title="手写学习专题",
        description="从当前图谱继续记录的笔记不应掉出该主题。",
        visibility="private",
        context_ids=["tech-pydantic-ai"],
        project_root=tmp_path,
    )
    node = create_node(
        title="在专题图中新建的手写笔记",
        body="保留所属图谱，并通过 PydanticAI 技术节点建立关系。",
        node_type="note",
        target_id="tech-pydantic-ai",
        relation_type="extends",
        visibility="private",
        project_root=tmp_path,
    )

    add_node_to_map(topic_map, node.id, tmp_path)
    catalog = load_catalog(tmp_path)
    updated_map = catalog.knowledge_map(topic_map.id)
    view = graph_view(catalog, updated_map)
    node_ids = {
        item["data"]["id"]
        for item in view["elements"]
        if "source" not in item["data"]
    }

    assert node.id in updated_map.node_ids
    assert node.id in node_ids
    assert view["metrics"]["orphan_count"] == 0
