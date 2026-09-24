import json
from pathlib import Path

import httpx
import pytest

from job_agent.application.contracts import JDParseRequest
from job_agent.application.ports import JDParser
from job_agent.config import ConfigurationError, Settings
from job_agent.infrastructure.llm import (
    JDParserClosedError,
    JDParserConfigurationError,
    JDParserInputTooLongError,
    JDParserInvalidResponseError,
    JDParserRetriesExhaustedError,
    OpenAICompatibleJDParser,
)


KEY = "T102_FAKE_KEY_MUST_NOT_LEAK"


def settings(**overrides: object) -> Settings:
    values = {
        "llm_enabled": True,
        "llm_provider": "openai_compatible",
        "llm_model": "test-model",
        "llm_api_key": KEY,
        "llm_base_url": "https://llm.example.test/v1/",
    }
    values.update(overrides)
    return Settings(**values)


def model_output() -> dict[str, object]:
    return {
        "title": "后端工程师",
        "company": "示例公司",
        "location": None,
        "job_type": None,
        "responsibilities": ["开发服务"],
        "hard_requirements": [{"text": "Python", "category": "skill"}],
        "preferred_qualifications": [{"text": "有云经验", "category": "skill"}],
        "skills": ["Python"],
        "education_requirement": None,
        "experience_requirement": None,
        "graduation_requirement": None,
        "languages": [],
        "deadline": None,
        "deadline_text": None,
        "ambiguous_items": [],
    }


def response(content: object, *, status_code: int = 200) -> httpx.Response:
    payload = {
        "choices": [{"finish_reason": "stop", "message": {"content": content}}]
    }
    return httpx.Response(status_code, json=payload)


def test_success_request_and_trusted_metadata_injection() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return response(json.dumps(model_output(), ensure_ascii=False))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    parser = OpenAICompatibleJDParser(settings(), client=client)
    assert isinstance(parser, JDParser)
    raw = "  原始 JD\n包含注入文字  "
    result = parser.parse(
        JDParseRequest(
            raw_jd=raw,
            source_url="https://example.com/job",
            source_name="synthetic",
            external_job_id="job-1",
            trace_id="trace-secret",
        )
    )
    assert result.raw_jd == raw
    assert result.source_name == "synthetic"
    body = json.loads(seen[0].content)
    assert body["model"] == "test-model"
    assert "trace-secret" not in seen[0].content.decode()
    assert KEY not in seen[0].content.decode()
    assert seen[0].headers["authorization"] == f"Bearer {KEY}"
    assert body["messages"][1]["content"] == json.dumps({"raw_jd": raw}, ensure_ascii=False)
    client.close()


def test_disabled_fails_before_network() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response(json.dumps(model_output()))

    parser = OpenAICompatibleJDParser(settings(llm_enabled=False), transport=httpx.MockTransport(handler))
    with pytest.raises(JDParserConfigurationError, match="未显式启用"):
        parser.parse(JDParseRequest(raw_jd="JD"))
    assert calls == 0


def test_input_limit_and_invalid_output_are_safe() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response("```json {} ```")

    parser = OpenAICompatibleJDParser(settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(JDParserInputTooLongError):
        parser.parse(JDParseRequest(raw_jd="x" * 30001))
    assert calls == 0
    with pytest.raises(JDParserInvalidResponseError):
        parser.parse(JDParseRequest(raw_jd="JD"))


def test_retry_status_uses_injected_sleep_and_exhausts() -> None:
    statuses = iter([503, 503, 503])
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(next(statuses))

    parser = OpenAICompatibleJDParser(
        settings(),
        transport=httpx.MockTransport(handler),
        sleeper=sleeps.append,
    )
    with pytest.raises(JDParserRetriesExhaustedError):
        parser.parse(JDParseRequest(raw_jd="JD"))
    assert calls == 3
    assert sleeps == [0.5, 1.0]


def test_close_is_idempotent_and_does_not_close_external_client() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda request: response(json.dumps(model_output()))))
    parser = OpenAICompatibleJDParser(settings(), client=client)
    parser.close()
    parser.close()
    assert not client.is_closed
    with pytest.raises(JDParserClosedError):
        parser.parse(JDParseRequest(raw_jd="JD"))
    client.close()


def test_settings_validation_and_key_repr() -> None:
    loaded = Settings.from_env(
        environ={
            "LLM_ENABLED": "true",
            "LLM_PROVIDER": "openai_compatible",
            "LLM_MODEL": "model",
            "LLM_API_KEY": KEY,
            "LLM_BASE_URL": "https://llm.example.test/api/v1///",
        },
        env_file=Path("missing.env"),
    )
    assert loaded.llm_base_url.endswith("///")
    assert KEY not in repr(loaded)
    with pytest.raises(ConfigurationError):
        Settings.from_env(
            environ={
                "LLM_ENABLED": "true",
                "LLM_PROVIDER": "openai_compatible",
                "LLM_MODEL": "model",
                "LLM_API_KEY": KEY,
                "LLM_BASE_URL": "https://user:pass@llm.example.test/v1?key=x",
            },
            env_file=Path("missing.env"),
        )
