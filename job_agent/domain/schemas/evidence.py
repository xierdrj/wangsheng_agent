"""简历证据 Schema。"""

from pydantic import Field, field_validator

from job_agent.domain.enums import EvidenceVerification
from job_agent.domain.schemas._base import TimestampedModel, validate_non_blank


class ResumeEvidence(TimestampedModel):
    id: str
    candidate_id: str
    experience_id: str | None = None
    category: str = Field(min_length=1)
    content: str = Field(min_length=1)
    skills: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    source_resume_id: str | None = None
    verification: EvidenceVerification = EvidenceVerification.UNVERIFIED

    _content_not_blank = field_validator("content")(validate_non_blank)
