"""OpenAI-compatible Provider 的严格语义输出 Schema。"""

from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from job_agent.application.contracts import JDRequirement
from job_agent.domain.schemas._base import DomainModel, validate_non_blank, validate_optional_aware_datetime


class JDParserModelOutput(DomainModel):
    """只允许模型填写岗位语义，不包含调用方可信元数据。"""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    title: str | None
    company: str | None
    location: str | None
    job_type: str | None
    responsibilities: list[str]
    hard_requirements: list[JDRequirement]
    preferred_qualifications: list[JDRequirement]
    skills: list[str]
    education_requirement: str | None
    experience_requirement: str | None
    graduation_requirement: str | None
    languages: list[str]
    deadline: datetime | None
    deadline_text: str | None
    ambiguous_items: list[str]

    @field_validator(
        "title", "company", "location", "job_type", "education_requirement",
        "experience_requirement", "graduation_requirement", "deadline_text",
    )
    @classmethod
    def optional_text_is_not_unknown(cls, value: str | None) -> str | None:
        if value is not None:
            value = validate_non_blank(value)
            if value.casefold() == "unknown":
                raise ValueError("缺失信息必须使用 null")
        return value

    @field_validator("responsibilities", "skills", "languages", "ambiguous_items")
    @classmethod
    def list_text_is_meaningful(cls, values: list[str]) -> list[str]:
        for value in values:
            validate_non_blank(value)
            if value.strip().casefold() == "unknown":
                raise ValueError("缺失信息必须使用空列表")
        return values

    _deadline_timezone = field_validator("deadline")(validate_optional_aware_datetime)


__all__ = ["JDParserModelOutput"]
