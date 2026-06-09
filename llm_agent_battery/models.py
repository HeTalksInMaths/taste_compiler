"""Pydantic data models for the LLM Agent Battery pipeline."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# --- Enumerations ---


class FileCategory(str, Enum):
    AGENT_LOGIC = "AGENT_LOGIC"
    TOOL_DEFINITION = "TOOL_DEFINITION"
    ORCHESTRATION = "ORCHESTRATION"
    STATE_MANAGEMENT = "STATE_MANAGEMENT"
    PROMPT_TEMPLATE = "PROMPT_TEMPLATE"
    CONFIGURATION = "CONFIGURATION"
    TEST = "TEST"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FindingCategory(str, Enum):
    LOGIC_ERROR = "logic_error"
    CORRECTNESS = "correctness"
    EDGE_CASE = "edge_case"
    DATA_INTEGRITY = "data_integrity"
    DESIGN_FLAW = "design_flaw"
    SECURITY = "security"


class ArchitectureStyle(str, Enum):
    SINGLE_AGENT = "single-agent"
    MULTI_AGENT = "multi-agent-orchestrated"
    PIPELINE_SEQUENTIAL = "pipeline-sequential"
    REACTIVE_EVENT_DRIVEN = "reactive-event-driven"


# --- Core Models ---


class ScanConfig(BaseModel):
    include_globs: list[str] = Field(default_factory=lambda: [
        "*.py", "*.ts", "*.js", "*.go", "*.rs", "*.yaml", "*.yml", "*.json"
    ])
    exclude_globs: list[str] = Field(default_factory=lambda: [
        ".git", "__pycache__", "node_modules", ".venv", "venv",
        "dist", "build", "*.egg-info", ".agentbattery"
    ])
    max_file_size_bytes: int = 500 * 1024  # 500KB


class DiscoveredFile(BaseModel):
    path: Path
    relative_path: str
    size_bytes: int


class ScanWarning(BaseModel):
    file_path: str
    reason: str


class ScanResult(BaseModel):
    files: list[DiscoveredFile]
    warnings: list[ScanWarning] = Field(default_factory=list)
    total_count: int
    elapsed_seconds: float


class ClassifiedFile(BaseModel):
    path: Path
    relative_path: str
    size_bytes: int
    primary_category: FileCategory
    secondary_categories: list[FileCategory] = Field(default_factory=list)


class ClassifyConfig(BaseModel):
    use_llm_fallback: bool = True
    fast_mode: bool = False


class CodeChunk(BaseModel):
    file_path: str
    chunk_name: str
    content: str
    functions: list[str] = Field(default_factory=list)
    preamble: str = ""
    is_truncated: bool = False
    start_line: int = 0
    end_line: int = 0


class ChunkConfig(BaseModel):
    max_chunk_chars: int = 12000
    preserve_class_unity: bool = True


class Finding(BaseModel):
    severity: Severity
    category: FindingCategory
    file_path: str
    location: str  # function/class name
    title: str
    description: str
    impact: str
    remediation: str = ""
    source_layer: str = "llm"  # "heuristic" or "llm"
    confirmed_by_heuristic: bool = False


class ReviewProfile(BaseModel):
    name: str
    architecture_style: ArchitectureStyle
    system_prompt_template: str
    focus_areas: list[str]
    anti_patterns: list[str]


class InferenceConfig(BaseModel):
    model_id: str = "us.anthropic.claude-sonnet-4-6"
    max_tokens: int = 4096
    temperature: float = 0.2
    connect_timeout: int = 30
    read_timeout: int = 300


class ConcurrencyConfig(BaseModel):
    max_concurrent: int = 3
    min_delay_seconds: float = 1.0
    max_retries: int = 3
    backoff_base: float = 2.0


class PipelineConfig(BaseModel):
    target_dir: Path
    scan_config: ScanConfig = Field(default_factory=ScanConfig)
    classify_config: ClassifyConfig = Field(default_factory=ClassifyConfig)
    chunk_config: ChunkConfig = Field(default_factory=ChunkConfig)
    inference_config: InferenceConfig = Field(default_factory=InferenceConfig)
    concurrency_config: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    profile: Optional[ReviewProfile] = None
    fast_mode: bool = False
    threshold: Severity = Severity.HIGH
    output_dir: Optional[Path] = None
    ci_mode: bool = False


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class PipelineResult(BaseModel):
    findings: list[Finding]
    scan_result: ScanResult
    classified_files: list[ClassifiedFile]
    chunks_reviewed: int
    token_usage: TokenUsage
    elapsed_seconds: float
