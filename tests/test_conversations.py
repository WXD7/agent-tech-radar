import re
import shutil

import pytest
from fastapi.testclient import TestClient

import app.main as main
from radar.conversations import (
    create_conversation_source,
    parse_thread_id,
    read_conversation_source,
    update_conversation_source,
)
from radar.paths import PROJECT_ROOT
from radar.store import load_catalog


THREAD_ID = "123e4567-e89b-42d3-a456-426614174000"
THREAD_V7_ID = "018f2a6c-7b3d-7e4f-8a9b-1c2d3e4f5a6b"


@pytest.mark.parametrize(
    "reference",
    [
        THREAD_ID,
        f"codex://threads/{THREAD_ID}",
        f"https://chatgpt.com/codex/tasks/{THREAD_ID}",
        f"codex://threads/{THREAD_V7_ID}",
    ],
)
def test_parse_thread_reference(reference: str) -> None:
    assert parse_thread_id(reference) in {THREAD_ID, THREAD_V7_ID}


@pytest.mark.parametrize("reference", ["", "not-a-thread", "codex://threads/nope"])
def test_parse_thread_reference_rejects_invalid_values(reference: str) -> None:
    with pytest.raises(ValueError):
        parse_thread_id(reference)


def test_conversation_source_create_and_update(tmp_path) -> None:
    source = create_conversation_source(
        title="Pydantic AI 学习会话",
        thread_reference=f"codex://threads/{THREAD_ID}",
        project_root=tmp_path,
    )
    assert source.status == "pending"
    assert source.thread_url == f"codex://threads/{THREAD_ID}"
    assert THREAD_ID not in source.id
    assert source.visibility == "private"

    updated = update_conversation_source(
        source.id,
        summary="总结了重试边界与待验证假设。",
        note_ids=["node-example"],
        mark_synced=True,
        project_root=tmp_path,
    )
    assert updated.status == "synced"
    assert updated.last_synced_at
    assert read_conversation_source(source.id, tmp_path).note_ids == ["node-example"]
    assert load_catalog(tmp_path).conversation_source(source.id) is not None


def test_conversation_import_route_and_deep_link(tmp_path, monkeypatch) -> None:
    for directory in ("knowledge", "proposals", "inbox", "experiments", "discovery"):
        shutil.copytree(PROJECT_ROOT / directory, tmp_path / directory)
    monkeypatch.setattr(main, "APP_PROJECT_ROOT", tmp_path)

    with TestClient(main.app) as client:
        form = client.get("/conversations/import")
        token = re.search(r'name="csrf_token" value="([^"]+)"', form.text).group(1)
        created = client.post(
            "/conversations/import",
            data={
                "csrf_token": token,
                "title": "我的 Agent 框架学习会话",
                "thread_reference": f"https://chatgpt.com/codex/tasks/{THREAD_ID}",
            },
            follow_redirects=False,
        )
        assert created.status_code == 303
        detail = client.get(created.headers["location"])
        assert detail.status_code == 200
        assert "codex://threads/" in detail.text
        assert "打开 Codex 继续沉淀" in detail.text
        assert "从本会话形成的研究文档" in detail.text
