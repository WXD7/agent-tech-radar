from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Technology(StrictModel):
    id: str
    name: str
    kind: str
    description: str
    homepage: HttpUrl
    repository: HttpUrl
    package: str | None = None
    status: Literal["watch", "assess", "trial", "adopt", "hold"] = "watch"
    capability_ids: list[str] = Field(default_factory=list)
    discovery_category_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    last_reviewed: str | None = None


class PopularitySignal(StrictModel):
    id: str
    technology_id: str
    github_stars: int = Field(ge=0)
    github_forks: int = Field(ge=0)
    last_activity_at: str
    observed_at: str
    source_url: HttpUrl


class DiscoveryCategory(StrictModel):
    id: str
    name: str
    description: str
    priority: Literal["core", "adjacent"] = "core"


class DiscoverySource(StrictModel):
    id: str
    name: str
    source_type: Literal[
        "repository_search",
        "official_org_watch",
        "package_registry",
        "paper_index",
        "curated_landscape",
    ]
    role: Literal["discovery", "verification", "both"]
    status: Literal["active", "planned"]
    cadence: str
    description: str


class DiscoveryQuery(StrictModel):
    id: str
    name: str
    query: str
    category_ids: list[str] = Field(default_factory=list)
    ecosystem_focus: str
    cadence: str


class DiscoveryCandidate(StrictModel):
    id: str
    name: str
    repository: HttpUrl
    homepage: HttpUrl | None = None
    description: str
    category_ids: list[str] = Field(default_factory=list)
    ecosystem: str
    status: Literal["discovered", "triaged", "excluded", "promoted"]
    relevance: Literal["unreviewed", "high", "medium", "low"]
    review_note: str | None = None
    source_query_ids: list[str] = Field(default_factory=list)
    github_stars: int = Field(ge=0)
    github_forks: int = Field(ge=0)
    last_activity_at: str
    observed_at: str
    license: str | None = None
    archived: bool = False


class DiscoveryRun(StrictModel):
    id: str
    started_at: str
    completed_at: str
    query_count: int = Field(ge=0)
    fetched_result_count: int = Field(ge=0)
    unique_result_count: int = Field(ge=0)
    known_result_count: int = Field(ge=0)
    new_candidate_count: int = Field(ge=0)
    duplicate_hit_count: int = Field(ge=0)
    new_unique_rate: float = Field(ge=0, le=1)
    incomplete_query_ids: list[str] = Field(default_factory=list)
    query_total_counts: dict[str, int] = Field(default_factory=dict)


class Capability(StrictModel):
    id: str
    name: str
    group: str
    description: str
    priority: Literal["core", "important", "optional"] = "important"


class Claim(StrictModel):
    id: str
    technology_id: str
    capability_id: str
    text: str
    status: Literal["hypothesis", "supported", "contested", "rejected"]
    confidence: int = Field(ge=0, le=100)
    evidence_ids: list[str] = Field(default_factory=list)
    experiment_ids: list[str] = Field(default_factory=list)
    updated_at: str


class Evidence(StrictModel):
    id: str
    title: str
    url: HttpUrl
    source_type: Literal[
        "official_repository",
        "official_docs",
        "release",
        "package_registry",
        "paper",
        "experiment",
    ]
    publisher: str
    retrieved_at: str
    content_hash: str | None = None
    summary: str
    supports_claim_ids: list[str] = Field(default_factory=list)
    contradicts_claim_ids: list[str] = Field(default_factory=list)


class ClaimDraft(StrictModel):
    id: str
    capability_id: str
    text: str
    status: Literal["hypothesis", "supported", "contested", "rejected"]
    confidence: int = Field(ge=0, le=100)


class Proposal(StrictModel):
    id: str
    title: str
    action: Literal["create_claim", "update_claim"]
    technology_id: str
    target_claim_id: str | None = None
    proposed_claim: ClaimDraft
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["pending", "accepted", "rejected"] = "pending"
    created_at: str
    reviewed_at: str | None = None
    reviewer_note: str | None = None


class Change(StrictModel):
    id: str
    source_id: str
    technology_id: str | None = None
    source_kind: str
    title: str
    url: HttpUrl
    detected_at: str
    content_hash: str
    importance: Literal["high", "medium", "low"]
    status: Literal["new", "triaged", "ignored"] = "new"
    summary: str


class Experiment(StrictModel):
    id: str
    name: str
    status: Literal["planned", "running", "completed", "failed"]
    hypothesis: str
    technology_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    method: str
    result_summary: str | None = None
    reproducibility: str
    last_run_at: str | None = None


class KnowledgeNode(StrictModel):
    id: str
    title: str = Field(min_length=2, max_length=120)
    body: str = Field(min_length=2, max_length=4000)
    node_type: Literal["concept", "question", "challenge", "answer", "note"]
    status: Literal["open", "active", "resolved", "archived"]
    target_id: str
    relation_type: Literal[
        "relates_to",
        "questions",
        "challenges",
        "answers",
        "extends",
        "corrects",
    ]
    parent_id: str | None = None
    created_at: str
    updated_at: str
    archived_from: Literal["open", "active", "resolved"] | None = None
    source_kind: Literal[
        "manual", "codex_conversation", "automated_research"
    ] = "manual"
    conversation_source_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    verification_status: Literal[
        "unverified",
        "researching",
        "partially_verified",
        "verified",
        "contested",
    ] = "unverified"
    visibility: Literal["private", "shared"] = "shared"


class ConversationSource(StrictModel):
    id: str
    title: str = Field(min_length=2, max_length=160)
    thread_id: str
    thread_url: str
    status: Literal["pending", "synced", "stale", "unavailable"] = "pending"
    summary: str | None = None
    note_ids: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    imported_at: str
    updated_at: str
    last_synced_at: str | None = None
    last_synced_turn_id: str | None = None
    visibility: Literal["private"] = "private"


class ConversationAnchor(StrictModel):
    id: str
    node_id: str
    conversation_source_id: str
    turn_id: str
    item_id: str
    role: Literal["user", "assistant"]
    anchor_kind: Literal[
        "question_context",
        "answer_basis",
        "correction",
        "decision_context",
    ]
    excerpt: str = Field(min_length=2, max_length=4000)
    locator_text: str = Field(min_length=2, max_length=240)
    content_hash: str = Field(min_length=64, max_length=64)
    captured_at: str
    status: Literal["active", "archived"] = "active"


class ResearchDocument(StrictModel):
    id: str
    title: str = Field(min_length=2, max_length=200)
    summary: str = Field(min_length=2, max_length=1200)
    content_path: str = Field(min_length=3, max_length=500)
    document_kind: Literal[
        "research_note",
        "architecture_note",
        "decision_record",
    ] = "research_note"
    status: Literal["draft", "active", "archived"] = "active"
    visibility: Literal["private", "shared"] = "shared"
    verification_status: Literal[
        "unverified",
        "researching",
        "partially_verified",
        "verified",
        "contested",
        "mixed",
    ] = "mixed"
    conversation_source_ids: list[str] = Field(default_factory=list)
    technology_ids: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)
    featured_section_anchors: list[str] = Field(default_factory=list)
    section_context_ids: dict[str, list[str]] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class KnowledgeMap(StrictModel):
    id: str
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=2, max_length=600)
    visibility: Literal["private", "shared"] = "shared"
    selection_mode: Literal["overview", "topic"]
    status: Literal["active", "archived"] = "active"
    conversation_source_ids: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    node_ids: list[str] = Field(default_factory=list)
    context_ids: list[str] = Field(default_factory=list)
    include_evidence: bool = True
    created_at: str
    updated_at: str


class Catalog(StrictModel):
    technologies: list[Technology] = Field(default_factory=list)
    capabilities: list[Capability] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    proposals: list[Proposal] = Field(default_factory=list)
    changes: list[Change] = Field(default_factory=list)
    experiments: list[Experiment] = Field(default_factory=list)
    popularity_signals: list[PopularitySignal] = Field(default_factory=list)
    knowledge_nodes: list[KnowledgeNode] = Field(default_factory=list)
    discovery_categories: list[DiscoveryCategory] = Field(default_factory=list)
    discovery_sources: list[DiscoverySource] = Field(default_factory=list)
    discovery_queries: list[DiscoveryQuery] = Field(default_factory=list)
    discovery_candidates: list[DiscoveryCandidate] = Field(default_factory=list)
    discovery_runs: list[DiscoveryRun] = Field(default_factory=list)
    conversation_sources: list[ConversationSource] = Field(default_factory=list)
    conversation_anchors: list[ConversationAnchor] = Field(default_factory=list)
    research_documents: list[ResearchDocument] = Field(default_factory=list)
    knowledge_maps: list[KnowledgeMap] = Field(default_factory=list)

    def technology(self, technology_id: str) -> Technology | None:
        return next((item for item in self.technologies if item.id == technology_id), None)

    def capability(self, capability_id: str) -> Capability | None:
        return next((item for item in self.capabilities if item.id == capability_id), None)

    def claim(self, claim_id: str) -> Claim | None:
        return next((item for item in self.claims if item.id == claim_id), None)

    def evidence_item(self, evidence_id: str) -> Evidence | None:
        return next((item for item in self.evidence if item.id == evidence_id), None)

    def proposal(self, proposal_id: str) -> Proposal | None:
        return next((item for item in self.proposals if item.id == proposal_id), None)

    def knowledge_node(self, node_id: str) -> KnowledgeNode | None:
        return next((item for item in self.knowledge_nodes if item.id == node_id), None)

    def conversation_source(self, source_id: str) -> ConversationSource | None:
        return next(
            (item for item in self.conversation_sources if item.id == source_id),
            None,
        )

    def conversation_anchor(self, anchor_id: str) -> ConversationAnchor | None:
        return next(
            (item for item in self.conversation_anchors if item.id == anchor_id),
            None,
        )

    def anchors_for_node(self, node_id: str) -> list[ConversationAnchor]:
        return [
            item for item in self.conversation_anchors if item.node_id == node_id
        ]

    def anchors_for_conversation(self, source_id: str) -> list[ConversationAnchor]:
        return [
            item
            for item in self.conversation_anchors
            if item.conversation_source_id == source_id
        ]

    def knowledge_map(self, map_id: str) -> KnowledgeMap | None:
        return next((item for item in self.knowledge_maps if item.id == map_id), None)

    def research_document(self, document_id: str) -> ResearchDocument | None:
        return next(
            (item for item in self.research_documents if item.id == document_id),
            None,
        )

    def popularity(self, technology_id: str) -> PopularitySignal | None:
        return next(
            (item for item in self.popularity_signals if item.technology_id == technology_id),
            None,
        )

    def discovery_category(self, category_id: str) -> DiscoveryCategory | None:
        return next(
            (item for item in self.discovery_categories if item.id == category_id),
            None,
        )
