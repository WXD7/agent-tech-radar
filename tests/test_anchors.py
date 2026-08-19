from radar.anchors import archive_anchor, create_anchor
from radar.conversations import create_conversation_source
from radar.nodes import create_node, read_node
from radar.store import load_catalog


THREAD_ID = "018f2a6c-7b3d-7e4f-8a9b-1c2d3e4f5a6b"


def test_private_conversation_node_and_anchor_round_trip(tmp_path) -> None:
    source = create_conversation_source(
        title="测试会话",
        thread_reference=f"codex://threads/{THREAD_ID}",
        project_root=tmp_path,
    )
    node = create_node(
        title="会话提炼节点",
        body="这条内容仍然需要外部证据确认。",
        node_type="note",
        target_id="cap-example",
        relation_type="extends",
        source_kind="codex_conversation",
        conversation_source_ids=[source.id],
        visibility="private",
        project_root=tmp_path,
    )
    anchor = create_anchor(
        node_id=node.id,
        conversation_source_id=source.id,
        turn_id="turn-1",
        item_id="item-2",
        role="assistant",
        anchor_kind="answer_basis",
        excerpt="Guardrail 是检查位置，不是检测模型。",
        locator_text="Guardrail 是检查位置",
        project_root=tmp_path,
    )

    assert (tmp_path / "knowledge" / "nodes" / "private" / f"{node.id}.yaml").exists()
    assert read_node(node.id, tmp_path).visibility == "private"
    catalog = load_catalog(tmp_path)
    assert catalog.conversation_anchor(anchor.id).item_id == "item-2"
    assert catalog.anchors_for_node(node.id)[0].content_hash

    archived = archive_anchor(anchor.id, tmp_path)
    assert archived.status == "archived"
