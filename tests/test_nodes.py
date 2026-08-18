import re
import shutil

from fastapi.testclient import TestClient

import app.main as main
from radar.nodes import archive_node, create_node, restore_node, update_node
from radar.paths import PROJECT_ROOT
from radar.store import load_catalog


def _copy_catalog(tmp_path) -> None:
    for directory in ("knowledge", "proposals", "inbox", "experiments"):
        shutil.copytree(PROJECT_ROOT / directory, tmp_path / directory)


def test_node_service_create_update_archive_restore(tmp_path) -> None:
    node = create_node(
        title="要验证的问题",
        body="这是一条需要通过实验回答的问题。",
        node_type="question",
        target_id="claim-example",
        relation_type="questions",
        project_root=tmp_path,
    )
    assert node.status == "open"

    updated = update_node(
        node.id,
        title="已修正的问题",
        body="更完整地记录质疑依据与待验证边界。",
        node_type="challenge",
        target_id="claim-example",
        relation_type="challenges",
        parent_id=None,
        status="active",
        project_root=tmp_path,
    )
    assert updated.title == "已修正的问题"

    archived = archive_node(node.id, tmp_path)
    assert archived.status == "archived"
    restored = restore_node(node.id, tmp_path)
    assert restored.status == "active"


def test_node_routes_full_lifecycle(tmp_path, monkeypatch) -> None:
    _copy_catalog(tmp_path)
    monkeypatch.setattr(main, "APP_PROJECT_ROOT", tmp_path)

    with TestClient(main.app) as client:
        form = client.get("/nodes/new?target_id=tech-pydantic-ai&node_type=question")
        assert form.status_code == 200
        token = re.search(r'name="csrf_token" value="([^"]+)"', form.text).group(1)
        created = client.post(
            "/nodes",
            data={
                "csrf_token": token,
                "title": "这个框架的重试是否可控？",
                "body": "需要通过实验区分框架重试与模型自行修正。",
                "node_type": "question",
                "status": "open",
                "target_id": "tech-pydantic-ai",
                "relation_type": "questions",
                "parent_id": "",
            },
            follow_redirects=False,
        )
        assert created.status_code == 303, created.text
        node_id = created.headers["location"].split("/")[2].split("?")[0]

        detail = client.get(f"/nodes/{node_id}")
        assert detail.status_code == 200
        token = re.search(r'name="csrf_token" value="([^"]+)"', detail.text).group(1)
        archived = client.post(
            f"/nodes/{node_id}/archive",
            data={"csrf_token": token},
            follow_redirects=False,
        )
        assert archived.status_code == 303
        assert load_catalog(tmp_path).knowledge_node(node_id).status == "archived"

        detail = client.get(f"/nodes/{node_id}")
        token = re.search(r'name="csrf_token" value="([^"]+)"', detail.text).group(1)
        restored = client.post(
            f"/nodes/{node_id}/restore",
            data={"csrf_token": token},
            follow_redirects=False,
        )
        assert restored.status_code == 303
        assert load_catalog(tmp_path).knowledge_node(node_id).status == "open"
