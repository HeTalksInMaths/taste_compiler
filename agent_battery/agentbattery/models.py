"""Data models for agentbattery - all Pydantic v2 models and enumerations."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


# --- Enumerations ---


class FileCategory(str, Enum):
    """Categories for discovered files, in priority order."""

    TRACE = "TRACE"
    TOOL_SCHEMA = "TOOL_SCHEMA"
    TOOL_SOURCE = "TOOL_SOURCE"
    PROMPT = "PROMPT"
    POLICY = "POLICY"
    EVAL = "EVAL"
    CONFIG = "CONFIG"
    DOC = "DOC"
    UNKNOWN = "UNKNOWN"


class SideEffectLevel(str, Enum):
    """Side-effect risk classification for tools."""

    DESTRUCTIVE = "DESTRUCTIVE"
    EXTERNAL_WRITE = "EXTERNAL_WRITE"
    WEAK = "WEAK"
    NONE = "NONE"


class RiskLevel(str, Enum):
    """Severity level for findings."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ObligationType(str, Enum):
    """Types of obligations extracted from prompts and tool metadata."""

    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    LOOKUP_REQUIRED = "LOOKUP_REQUIRED"
    POLICY_CHECK_REQUIRED = "POLICY_CHECK_REQUIRED"
    ERROR_REPORTING_REQUIRED = "ERROR_REPORTING_REQUIRED"
    RETRIEVAL_INJECTION_GUARD = "RETRIEVAL_INJECTION_GUARD"
    FINAL_STATE_CONSISTENCY = "FINAL_STATE_CONSISTENCY"


class GapType(str, Enum):
    """Classification of findings into gap categories."""

    POLICY_GAP = "POLICY_GAP"
    ENFORCEMENT_GAP = "ENFORCEMENT_GAP"
    COVERAGE_GAP = "COVERAGE_GAP"
    TRACE_VIOLATION = "TRACE_VIOLATION"


class TraceStepType(str, Enum):
    """Types of steps in an agent execution trace."""

    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    AGENT_MESSAGE = "AGENT_MESSAGE"
    USER_MESSAGE = "USER_MESSAGE"


class CoverageStatus(str, Enum):
    """Coverage status for an obligation."""

    COVERED = "COVERED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"


class RecommendedRepairType(str, Enum):
    """Recommended repair actions for CI/CD integration."""

    ADD_TEST = "ADD_TEST"
    ADD_TOOL_PRECONDITION = "ADD_TOOL_PRECONDITION"
    TIGHTEN_SCHEMA = "TIGHTEN_SCHEMA"
    ADD_FINAL_STATE_VERIFIER = "ADD_FINAL_STATE_VERIFIER"
    ADD_HITL_GATE = "ADD_HITL_GATE"
    ADD_RETRY_OR_FALLBACK = "ADD_RETRY_OR_FALLBACK"
    UPDATE_ARCHITECTURE_DOC = "UPDATE_ARCHITECTURE_DOC"


# --- Core Models ---


class DiscoveredFile(BaseModel):
    """A file discovered during repository scanning."""

    path: Path
    relative_path: str
    size_bytes: int


class ClassifiedFile(BaseModel):
    """A discovered file with assigned category."""

    path: Path
    relative_path: str
    size_bytes: int
    primary_category: FileCategory
    secondary_categories: list[FileCategory] = Field(default_factory=list)


class ToolParameter(BaseModel):
    """A parameter for a tool artifact."""

    name: str
    type: str
    required: bool = True
    description: str = ""
    constraints: dict = Field(default_factory=dict)


class ToolArtifact(BaseModel):
    """A tool definition extracted from source code or schema."""

    name: str
    description: str
    parameters: list[ToolParameter] = Field(default_factory=list)
    return_type: str = "Any"
    source_path: str
    side_effect_level: SideEffectLevel = SideEffectLevel.NONE
    preconditions: list[str] = Field(default_factory=list)


class PromptArtifact(BaseModel):
    """A prompt artifact extracted from a classified file."""

    source_path: str
    text: str
    metadata: dict = Field(default_factory=dict)


class Obligation(BaseModel):
    """A requirement extracted from prompt text or tool metadata."""

    id: str
    obligation_type: ObligationType
    source_text: str
    source_path: str
    linked_tool_names: list[str] = Field(default_factory=list)


class ForbiddenTransition(BaseModel):
    """An ordering constraint between tools/steps."""

    predecessor: str  # tool or step that must come first
    successor: str  # tool that must not be called without predecessor
    obligation_id: str
    description: str


class Evidence(BaseModel):
    """Evidence supporting a finding."""

    source: str
    location: str = ""
    detail: str


class Finding(BaseModel):
    """A detected issue with type, severity, and evidence."""

    finding_type: str
    severity: RiskLevel
    gap_type: GapType
    title: str
    description: str
    evidence: list[Evidence] = Field(default_factory=list)
    remediation: str = ""
    transparency: str = ""  # why this finding was raised


class ObligationCoverage(BaseModel):
    """Coverage status for a single obligation."""

    obligation_id: str
    status: CoverageStatus
    matching_files: list[str] = Field(default_factory=list)
    score: float = 0.0


class CoverageResult(BaseModel):
    """Aggregated coverage analysis results."""

    obligations: list[ObligationCoverage]
    covered_count: int = 0
    partial_count: int = 0
    missing_count: int = 0


class TraceStep(BaseModel):
    """A single step in an agent execution trace."""

    type: TraceStepType
    tool_name: str = ""
    arguments: dict = Field(default_factory=dict)
    result: str = ""
    index: int = 0


class AgentTrace(BaseModel):
    """An agent execution trace parsed from a file."""

    source_path: str
    steps: list[TraceStep]


class GeneratedTest(BaseModel):
    """A test definition generated from a finding."""

    id: str
    title: str
    description: str
    finding_id: str = ""
    test_type: str
    setup: dict = Field(default_factory=dict)
    assertions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ScanResult(BaseModel):
    """Result of a repository scan."""

    files: list[DiscoveredFile]
    total_count: int
    elapsed_seconds: float


# --- Hackathon Agent Architecture Models ---


class AgentNode(BaseModel):
    """A single agent in a multi-agent system."""

    name: str
    role: str
    tools: list[str] = Field(default_factory=list)
    delegation_targets: list[str] = Field(default_factory=list)
    scope_limits: str | None = None


class AgentProfile(BaseModel):
    """A discovered agent's identity, purpose, and capabilities."""

    name: str
    purpose: str
    capabilities: list[str] = Field(default_factory=list)
    source_evidence: list[str] = Field(default_factory=list)


class DecisionPolicy(BaseModel):
    """How the agent decides what to do next."""

    strategy: str  # e.g., "goal-decomposition", "reactive", "plan-then-execute"
    stop_conditions: list[str] = Field(default_factory=list)
    tool_selection_logic: str | None = None
    source_evidence: list[str] = Field(default_factory=list)


class HumanInLoopPolicy(BaseModel):
    """Where and how human approval, review, or override is required."""

    approval_required_tools: list[str] = Field(default_factory=list)
    review_triggers: list[str] = Field(default_factory=list)
    override_mechanism: str | None = None
    source_evidence: list[str] = Field(default_factory=list)


class FailurePolicy(BaseModel):
    """How the agent handles errors, partial completion, and recovery."""

    retry_strategy: str | None = None
    timeout_seconds: int | None = None
    fallback_behavior: str | None = None
    partial_completion_handling: str | None = None
    recovery_mechanism: str | None = None
    source_evidence: list[str] = Field(default_factory=list)


class OrchestrationPolicy(BaseModel):
    """How multiple agents coordinate in a multi-agent system."""

    agents: list[AgentNode] = Field(default_factory=list)
    delegation_bounds: str | None = None
    shared_state_mechanism: str | None = None
    communication_pattern: str | None = None
    source_evidence: list[str] = Field(default_factory=list)


class AgentContract(BaseModel):
    """The unified contract linking all extracted artifacts."""

    prompts: list[PromptArtifact]
    tools: list[ToolArtifact]
    obligations: list[Obligation]
    forbidden_transitions: list[ForbiddenTransition] = Field(default_factory=list)
    risk_map: dict[str, SideEffectLevel] = Field(default_factory=dict)
    agent_profiles: list[AgentProfile] = Field(default_factory=list)
    decision_policy: DecisionPolicy | None = None
    human_in_loop_policy: HumanInLoopPolicy | None = None
    failure_policy: FailurePolicy | None = None
    orchestration_policy: OrchestrationPolicy | None = None


# --- CI/CD Readiness Models (Phase 2 interface) ---


class RepairFinding(BaseModel):
    """A finding mapped with repair metadata for CI/CD integration."""

    finding_id: str
    severity: RiskLevel
    gap_type: GapType
    linked_tools: list[str] = Field(default_factory=list)
    linked_obligations: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    generated_test_ids: list[str] = Field(default_factory=list)
    recommended_repair_type: RecommendedRepairType


class RepairInput(BaseModel):
    """Machine-readable repair input for CI/CD integration."""

    repo_root: str
    generated_at: str
    findings: list[RepairFinding] = Field(default_factory=list)
