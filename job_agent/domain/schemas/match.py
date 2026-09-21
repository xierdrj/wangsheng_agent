"""岗位匹配结果 Schema。"""

from datetime import datetime

from pydantic import Field, field_validator

from job_agent.domain.schemas._base import DomainModel, validate_aware_datetime


class MatchDimension(DomainModel):
    name: str = Field(min_length=1)
    score: float = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class MatchResult(DomainModel):
    id: str
    candidate_id: str
    job_id: str
    hard_filter_passed: bool
    hard_filter_reasons: list[str] = Field(default_factory=list)
    overall_score: float = Field(ge=0, le=100)
    dimensions: list[MatchDimension] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    recommendation: str = Field(min_length=1)
    created_at: datetime

    _created_at_timezone = field_validator("created_at")(validate_aware_datetime)
