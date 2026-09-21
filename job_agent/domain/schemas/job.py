"""岗位发布 Schema。"""

from datetime import datetime

from pydantic import Field, field_validator

from job_agent.domain.schemas._base import (
    DomainModel,
    validate_aware_datetime,
    validate_http_url,
    validate_optional_aware_datetime,
)


class JobPosting(DomainModel):
    id: str
    external_job_id: str | None = None
    company: str = Field(min_length=1)
    title: str = Field(min_length=1)
    location: str | None = None
    url: str = Field(min_length=1)
    source: str = Field(min_length=1)
    raw_jd: str = Field(min_length=1)
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    preferred_qualifications: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education_requirement: str | None = None
    graduation_requirement: str | None = None
    experience_requirement: str | None = None
    deadline: datetime | None = None
    fingerprint: str = Field(min_length=1)
    discovered_at: datetime

    _url_is_http = field_validator("url")(validate_http_url)
    _deadline_timezone = field_validator("deadline")(validate_optional_aware_datetime)
    _discovered_at_timezone = field_validator("discovered_at")(validate_aware_datetime)
