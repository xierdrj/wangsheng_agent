"""候选人 Profile 相关 Schema。"""

from datetime import date

from pydantic import EmailStr, Field, field_validator

from job_agent.domain.schemas._base import DomainModel, TimestampedModel, validate_non_blank


class BasicInfo(DomainModel):
    full_name: str = Field(min_length=1)
    email: EmailStr
    phone: str = Field(min_length=1)
    city: str | None = None
    sensitive_profile_id: str | None = None

    _full_name_not_blank = field_validator("full_name")(validate_non_blank)


class Education(DomainModel):
    id: str
    school: str = Field(min_length=1)
    degree: str = Field(min_length=1)
    major: str = Field(min_length=1)
    start_date: date | None = None
    end_date: date | None = None
    gpa: str | None = None


class Experience(DomainModel):
    id: str
    organization: str = Field(min_length=1)
    title: str = Field(min_length=1)
    start_date: date | None = None
    end_date: date | None = None
    description: str = Field(min_length=1)


class JobPreference(DomainModel):
    roles: list[str] = Field(default_factory=list, min_length=1)
    locations: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    graduation_year: int | None = None
    salary_expectation: str | None = None
    excluded_companies: list[str] = Field(default_factory=list)
    accepts_travel: bool | None = None
    accepts_relocation: bool | None = None


class CandidateProfile(TimestampedModel):
    id: str
    basic_info: BasicInfo
    education: list[Education] = Field(default_factory=list)
    internships: list[Experience] = Field(default_factory=list)
    projects: list[Experience] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    awards: list[str] = Field(default_factory=list)
    preferences: JobPreference
