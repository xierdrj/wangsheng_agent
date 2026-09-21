"""投递记录和事件 Schema。"""

from datetime import datetime

from pydantic import Field, field_validator

from job_agent.domain.enums import ApplicationStatus
from job_agent.domain.schemas._base import (
    DomainModel,
    validate_aware_datetime,
    validate_http_url,
    validate_optional_aware_datetime,
)


class ApplicationRecord(DomainModel):
    id: str
    candidate_id: str
    job_id: str
    status: ApplicationStatus
    application_url: str = Field(min_length=1)
    resume_version_id: str | None = None
    submitted_at: datetime | None = None
    last_updated_at: datetime

    _url_is_http = field_validator("application_url")(validate_http_url)
    _submitted_at_timezone = field_validator("submitted_at")(validate_optional_aware_datetime)
    _last_updated_at_timezone = field_validator("last_updated_at")(validate_aware_datetime)


class ApplicationAnswer(DomainModel):
    id: str
    application_id: str
    question: str = Field(min_length=1)
    question_type: str = Field(min_length=1)
    answer: str
    character_limit: int | None = Field(default=None, gt=0)
    source_evidence_ids: list[str] = Field(default_factory=list)
    is_user_edited: bool = False
    created_at: datetime

    _created_at_timezone = field_validator("created_at")(validate_aware_datetime)


class ApplicationEvent(DomainModel):
    id: str
    application_id: str
    event_type: str = Field(min_length=1)
    from_status: ApplicationStatus | None = None
    to_status: ApplicationStatus | None = None
    source: str = Field(min_length=1)
    details: dict[str, object] = Field(default_factory=dict)
    occurred_at: datetime

    _occurred_at_timezone = field_validator("occurred_at")(validate_aware_datetime)
