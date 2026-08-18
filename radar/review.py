from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import yaml

from radar.indexing import rebuild_index
from radar.models import Claim, Proposal
from radar.paths import PROJECT_ROOT
from radar.store import load_catalog, normalize_yaml


def _atomic_dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f".{uuid4().hex}.tmp")
    temporary.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    temporary.replace(path)


def _proposal_path(project_root: Path, proposal_id: str) -> Path:
    candidates = sorted((project_root / "proposals").glob("*.yaml"))
    for path in candidates:
        raw = normalize_yaml(yaml.safe_load(path.read_text(encoding="utf-8")))
        items = raw if isinstance(raw, list) else [raw]
        if any(item.get("id") == proposal_id for item in items):
            if isinstance(raw, list):
                raise ValueError("Reviewable proposals must use one record per YAML file.")
            return path
    raise FileNotFoundError(proposal_id)


def decide_proposal(
    proposal_id: str,
    decision: str,
    edited_text: str,
    confidence: int,
    reviewer_note: str,
    project_root: Path = PROJECT_ROOT,
) -> Proposal:
    if decision not in {"accept", "reject"}:
        raise ValueError("decision must be accept or reject")

    proposal_path = _proposal_path(project_root, proposal_id)
    raw = normalize_yaml(yaml.safe_load(proposal_path.read_text(encoding="utf-8")))
    proposal = Proposal.model_validate(raw)
    if proposal.status != "pending":
        raise ValueError("This proposal has already been reviewed.")

    reviewed_at = datetime.now(UTC).isoformat(timespec="seconds")
    if decision == "accept":
        draft = proposal.proposed_claim.model_copy(
            update={"text": edited_text.strip(), "confidence": confidence}
        )
        claim = Claim(
            id=draft.id,
            technology_id=proposal.technology_id,
            capability_id=draft.capability_id,
            text=draft.text,
            status=draft.status,
            confidence=draft.confidence,
            evidence_ids=proposal.evidence_ids,
            experiment_ids=[],
            updated_at=reviewed_at,
        )
        _atomic_dump(
            project_root / "knowledge" / "claims" / f"{claim.id}.yaml",
            claim.model_dump(mode="json"),
        )

    reviewed = proposal.model_copy(
        update={
            "status": "accepted" if decision == "accept" else "rejected",
            "reviewed_at": reviewed_at,
            "reviewer_note": reviewer_note.strip() or None,
            "proposed_claim": proposal.proposed_claim.model_copy(
                update={"text": edited_text.strip(), "confidence": confidence}
            ),
        }
    )
    _atomic_dump(proposal_path, reviewed.model_dump(mode="json"))
    review_record = {
        "id": f"review-{proposal_id}-{uuid4().hex[:8]}",
        "proposal_id": proposal_id,
        "decision": decision,
        "reviewed_at": reviewed_at,
        "reviewer_note": reviewer_note.strip() or None,
        "accepted_text": edited_text.strip() if decision == "accept" else None,
        "confidence": confidence,
    }
    _atomic_dump(
        project_root / "knowledge" / "reviews" / f"{review_record['id']}.yaml",
        review_record,
    )
    rebuild_index(load_catalog(project_root), project_root / ".radar" / "radar.db")
    return reviewed
