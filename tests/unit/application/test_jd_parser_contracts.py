"""JD Parser 应用契约校验测试。"""

from datetime import datetime
import inspect

import pytest
from pydantic import ValidationError

from job_agent.application.contracts import (
    JDParseRequest,
    JDParserFixture,
    JDRequirement,
    ParsedJD,
)
from job_agent.application.ports import JDParser


def test_request_accepts_valid_input_and_normalizes_blank_optional_text() -> None:
    request = JDParseRequest(
        raw_jd=" 虚构岗位描述 ",
        source_url="  ",
        source_name="  ",
        external_job_id="  ",
        trace_id=" trace-123 ",
    )

    assert request.raw_jd == " 虚构岗位描述 "
    assert request.source_url is None
    assert request.source_name is None
    assert request.external_job_id is None
    assert request.trace_id == "trace-123"


@pytest.mark.parametrize("raw_jd", ["", "   ", "\t\r\n"])
def test_request_rejects_empty_or_whitespace_jd(raw_jd: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        JDParseRequest(raw_jd=raw_jd)

    assert "raw_jd" in str(exc_info.value)
    assert "input_value" not in str(exc_info.value)


def test_invalid_request_error_does_not_echo_full_jd() -> None:
    raw_jd = "SENSITIVE SYNTHETIC JD BODY"

    with pytest.raises(ValidationError) as exc_info:
        JDParseRequest(raw_jd=raw_jd, source_url="file:///not-allowed")

    assert raw_jd not in str(exc_info.value)


@pytest.mark.parametrize("source_url", ["file:///tmp/job", "javascript:alert(1)", "https:///missing-host"])
def test_request_rejects_non_http_or_hostless_url(source_url: str) -> None:
    with pytest.raises(ValidationError):
        JDParseRequest(raw_jd="虚构岗位", source_url=source_url)


def test_request_accepts_http_and_https_urls() -> None:
    assert JDParseRequest(
        raw_jd="岗位 A", source_url="http://jobs.example.com/a"
    ).source_url == "http://jobs.example.com/a"
    assert JDParseRequest(
        raw_jd="岗位 B", source_url="https://jobs.example.com/b"
    ).source_url == "https://jobs.example.com/b"


def test_request_and_output_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        JDParseRequest(raw_jd="JD", unexpected="value")
    with pytest.raises(ValidationError):
        ParsedJD(raw_jd="JD", unexpected="value")
    with pytest.raises(ValidationError):
        JDRequirement(text="Go", category="skill", confidence=0.9)


def test_core_parser_models_forbid_extra_fields() -> None:
    for model, payload in (
        (JDParseRequest, {"raw_jd": "JD"}),
        (JDRequirement, {"text": "Go", "category": "skill"}),
        (ParsedJD, {"raw_jd": "JD"}),
        (
            JDParserFixture,
            {
                "fixture_id": "fixture",
                "input": {"raw_jd": "JD"},
                "expected": {"raw_jd": "JD"},
            },
        ),
    ):
        assert model.model_config["extra"] == "forbid"
        with pytest.raises(ValidationError):
            model.model_validate({**payload, "unexpected": "value"})


def test_parsed_jd_defaults_are_independent_and_excludes_lifecycle_fields() -> None:
    first = ParsedJD(raw_jd="岗位文本")
    second = ParsedJD(raw_jd="岗位文本")
    first.skills.append("Python")
    first.hard_requirements.append(JDRequirement(text="熟悉 Go", category="skill"))

    assert second.skills == []
    assert second.hard_requirements == []
    assert not {"id", "fingerprint", "discovered_at"} & set(ParsedJD.model_fields)


def test_parsed_jd_requires_timezone_aware_deadline() -> None:
    with pytest.raises(ValidationError):
        ParsedJD(raw_jd="岗位文本", deadline=datetime(2026, 9, 1, 12, 0))


def test_missing_information_uses_none_empty_lists_and_ambiguity() -> None:
    parsed = ParsedJD(raw_jd="只包含少量信息", ambiguous_items=["公司名称未提供"])

    assert parsed.company is None
    assert parsed.location is None
    assert parsed.deadline is None
    assert parsed.languages == []
    assert parsed.ambiguous_items == ["公司名称未提供"]
    with pytest.raises(ValidationError):
        ParsedJD(raw_jd="岗位文本", company="unknown")


def test_hard_and_preferred_requirements_are_independent() -> None:
    parsed = ParsedJD(
        raw_jd="要求 Go，熟悉 Kubernetes 者优先",
        hard_requirements=[JDRequirement(text="掌握 Go", category="skill")],
        preferred_qualifications=[
            JDRequirement(text="熟悉 Kubernetes", category="skill")
        ],
    )

    assert [item.text for item in parsed.hard_requirements] == ["掌握 Go"]
    assert [item.text for item in parsed.preferred_qualifications] == [
        "熟悉 Kubernetes"
    ]


def test_trace_id_is_only_an_input_correlation_field() -> None:
    request = JDParseRequest(raw_jd="岗位文本", trace_id="trace-abc")
    parsed = ParsedJD(raw_jd=request.raw_jd)

    assert request.trace_id == "trace-abc"
    assert "trace_id" not in ParsedJD.model_fields


def test_raw_jd_formatting_is_preserved_exactly() -> None:
    raw_jd = "\n  标题\r\n正文，保留前后空格  \n"
    request = JDParseRequest(raw_jd=raw_jd)
    parsed = ParsedJD(raw_jd=request.raw_jd)

    assert request.raw_jd == raw_jd
    assert parsed.raw_jd == raw_jd


def test_fixture_requires_expected_raw_jd_to_match_request() -> None:
    with pytest.raises(ValidationError):
        JDParserFixture(
            fixture_id="mismatch",
            input=JDParseRequest(raw_jd="输入原文"),
            expected=ParsedJD(raw_jd="不同原文"),
        )


def test_parser_protocol_has_one_synchronous_parse_method() -> None:
    public_callables = {
        name
        for name, value in JDParser.__dict__.items()
        if not name.startswith("_") and callable(value)
    }

    assert public_callables == {"parse"}
    assert not inspect.iscoroutinefunction(JDParser.parse)
