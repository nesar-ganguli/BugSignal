from datetime import datetime
from typing import Literal

import json

from pydantic import BaseModel, Field, field_validator


PriorityLabel = Literal["P0 Critical", "P1 High", "P2 Medium", "P3 Low"]
ConfidenceLevel = Literal["Low", "Medium", "High"]


class IssueEvidenceItem(BaseModel):
    claim: str
    source_type: Literal["ticket", "code"]
    source_id: str


class IssueDraftLLMResult(BaseModel):
    title: str
    summary: str
    user_impact: str
    steps_to_reproduce: list[str] = Field(default_factory=list)
    expected_behavior: str
    actual_behavior: str
    suspected_root_cause: str
    evidence: list[IssueEvidenceItem] = Field(default_factory=list)
    relevant_files: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel
    open_questions: list[str] = Field(default_factory=list)
    priority_label: PriorityLabel


class IssueDraftRead(BaseModel):
    id: int
    cluster_id: int
    title: str
    body_markdown: str
    priority_label: str
    confidence_level: str
    status: str
    warnings: list[str] = Field(default_factory=list)
    github_issue_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("warnings", mode="before")
    @classmethod
    def parse_warnings(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return [value] if value else []
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item is not None]
        return []


class IssueDraftResponse(BaseModel):
    draft: IssueDraftRead
    structured: IssueDraftLLMResult
    message: str


class IssueApprovalResponse(BaseModel):
    issue: IssueDraftRead
    github_issue_created: bool
    message: str
