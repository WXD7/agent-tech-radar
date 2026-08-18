import shutil

from radar.paths import PROJECT_ROOT
from radar.review import decide_proposal
from radar.store import load_catalog


def test_accepting_proposal_creates_reviewed_overlay(tmp_path) -> None:
    for directory in ("knowledge", "proposals", "inbox", "experiments"):
        shutil.copytree(PROJECT_ROOT / directory, tmp_path / directory)

    reviewed = decide_proposal(
        proposal_id="proposal-pydantic-output",
        decision="accept",
        edited_text="审核者确认：类型化结果存在，但复杂错误恢复仍需要实验。",
        confidence=70,
        reviewer_note="Demo review test",
        project_root=tmp_path,
    )

    assert reviewed.status == "accepted"
    catalog = load_catalog(tmp_path)
    claim = catalog.claim("claim-pydantic-typed-output")
    assert claim is not None
    assert claim.confidence == 70
    assert "审核者确认" in claim.text
    assert len(list((tmp_path / "knowledge" / "reviews").glob("review-*.yaml"))) == 1
