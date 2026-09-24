"""JD Parser 的输入、中间输出和测试 Fixture 契约。"""

from datetime import datetime
from typing import Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from job_agent.domain.schemas._base import (
    DomainModel,
    validate_http_url,
    validate_non_blank,
    validate_optional_aware_datetime,
)


def _optional_text(value: object) -> object:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return value


def _reject_unknown_text(value: str | None) -> str | None:
    if value is not None and value.strip().casefold() == "unknown":
        raise ValueError("缺失信息应使用空值而不是 unknown")
    return value


def _validate_optional_http_url(value: str | None) -> str | None:
    if value is None:
        return None
    return validate_http_url(value)


class JDParseRequest(DomainModel):
    """已验证的原始 JD 和可选调用来源信息。"""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    raw_jd: str = Field(min_length=1)
    source_url: str | None = None
    source_name: str | None = None
    external_job_id: str | None = None
    trace_id: str | None = None

    _raw_jd_not_blank = field_validator("raw_jd")(validate_non_blank)
    _source_url_not_blank = field_validator("source_url", mode="before")(
        _optional_text
    )
    _source_name_normalized = field_validator("source_name", mode="before")(
        _optional_text
    )
    _external_job_id_normalized = field_validator(
        "external_job_id", mode="before"
    )(_optional_text)
    _trace_id_normalized = field_validator("trace_id", mode="before")(
        _optional_text
    )
    _source_url_is_http = field_validator("source_url")(_validate_optional_http_url)


class JDRequirement(DomainModel):
    """从 JD 原文中提取的一项岗位条件。"""

    text: str = Field(min_length=1)
    category: Literal[
        "skill", "education", "experience", "graduation",
        "language", "location", "other",
    ]

    _text_not_blank = field_validator("text")(validate_non_blank)


class ParsedJD(DomainModel):
    """尚未标准化、可保留缺失值和歧义的 JD 中间结果。"""

    raw_jd: str = Field(min_length=1)
    source_url: str | None = None
    source_name: str | None = None
    external_job_id: str | None = None
    title: str | None = None
    company: str | None = None
    location: str | None = None
    job_type: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    hard_requirements: list[JDRequirement] = Field(default_factory=list)
    preferred_qualifications: list[JDRequirement] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education_requirement: str | None = None
    experience_requirement: str | None = None
    graduation_requirement: str | None = None
    languages: list[str] = Field(default_factory=list)
    deadline: datetime | None = None
    deadline_text: str | None = None
    ambiguous_items: list[str] = Field(default_factory=list)

    _deadline_timezone = field_validator("deadline")(
        validate_optional_aware_datetime
    )
    _source_url_is_http = field_validator("source_url")(_validate_optional_http_url)
    _source_url_normalized = field_validator("source_url", mode="before")(
        _optional_text
    )

    @field_validator(
        "title",
        "company",
        "location",
        "job_type",
        "education_requirement",
        "experience_requirement",
        "graduation_requirement",
        "deadline_text",
    )
    @classmethod
    def optional_fields_do_not_encode_unknown(
        cls, value: str | None
    ) -> str | None:
        return _reject_unknown_text(value)

    @field_validator("responsibilities", "skills", "languages", "ambiguous_items")
    @classmethod
    def list_items_are_meaningful(cls, values: list[str]) -> list[str]:
        for value in values:
            validate_non_blank(value)
            _reject_unknown_text(value.strip())
        return values


class JDParserFixture(DomainModel):
    """Fake Parser 使用的单个输入与期望输出样例。"""

    fixture_id: str = Field(min_length=1)
    input: JDParseRequest
    expected: ParsedJD

    _fixture_id_not_blank = field_validator("fixture_id")(validate_non_blank)

    @model_validator(mode="after")
    def output_preserves_source_text(self) -> Self:
        if self.expected.raw_jd != self.input.raw_jd:
            raise ValueError("Fixture expected.raw_jd 必须与 input.raw_jd 一致")
        source_fields = ("source_url", "source_name", "external_job_id")
        if any(
            getattr(self.expected, field) != getattr(self.input, field)
            for field in source_fields
        ):
            raise ValueError("Fixture expected 来源元数据必须与 input 一致")
        return self


__all__ = ["JDParseRequest", "JDParserFixture", "JDRequirement", "ParsedJD"]
