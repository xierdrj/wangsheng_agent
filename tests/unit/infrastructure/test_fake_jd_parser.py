"""JD Parser Fake 与脱敏 Fixture 行为测试。"""

import ast
import hashlib
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from job_agent.application.contracts import JDParseRequest, JDParserFixture, ParsedJD
from job_agent.application.ports import JDParser, JDParserError
from job_agent.infrastructure.fakes import (
    FakeJDParser,
    FakeJDParserNotConfiguredError,
    load_jd_parser_fixture,
)


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "jd_parser"
FIXTURE_NAMES = (
    "complete_cn.json",
    "missing_fields_cn.json",
    "hard_preferred_cn.json",
)


def load_fixtures() -> list[JDParserFixture]:
    return [load_jd_parser_fixture(FIXTURE_DIR / name) for name in FIXTURE_NAMES]


def test_all_synthetic_fixtures_load_as_validated_contracts() -> None:
    fixtures = load_fixtures()

    assert [fixture.fixture_id for fixture in fixtures] == [
        "complete-cn",
        "missing-fields-cn",
        "hard-preferred-cn",
    ]
    assert all(isinstance(item.input, JDParseRequest) for item in fixtures)
    assert all(isinstance(item.expected, ParsedJD) for item in fixtures)
    assert "虚构科技有限公司" == fixtures[0].expected.company
    assert fixtures[1].expected.company is None
    assert fixtures[1].expected.location is None
    assert fixtures[1].expected.deadline is None
    assert fixtures[2].expected.hard_requirements[0].text == "必须掌握 Go"
    assert fixtures[2].expected.preferred_qualifications[0].text == "具备 Kubernetes 经验"


def test_fake_satisfies_port_and_returns_parsed_jd_not_dict_or_job_posting() -> None:
    fake = FakeJDParser(load_fixtures())
    request = load_fixtures()[0].input

    assert isinstance(fake, JDParser)
    parsed = fake.parse(request)
    assert isinstance(parsed, ParsedJD)
    assert parsed.raw_jd == request.raw_jd
    assert parsed.title == "算法工程师"
    assert parsed.company == "虚构科技有限公司"
    assert not hasattr(parsed, "fingerprint")


def test_external_job_id_matches_exactly_and_request_metadata_is_preserved() -> None:
    fake = FakeJDParser(load_fixtures())
    original = load_fixtures()[0].input
    request = original.model_copy(
        update={"source_url": "https://jobs.example.com/another-source"}
    )

    parsed = fake.parse(request)
    assert parsed.raw_jd == request.raw_jd
    assert parsed.external_job_id == request.external_job_id
    assert parsed.source_url == request.source_url


def test_external_id_hit_with_conflicting_raw_text_fails_without_fallback() -> None:
    fake = FakeJDParser(load_fixtures())
    original = load_fixtures()[0].input
    conflicting = original.model_copy(update={"raw_jd": "另一份不匹配的 JD"})

    with pytest.raises(JDParserError, match="原文与请求不一致") as exc_info:
        fake.parse(conflicting)
    assert conflicting.raw_jd not in str(exc_info.value)


def test_external_and_sha256_key_namespaces_are_isolated() -> None:
    raw_jd = "命名空间隔离测试 JD"
    digest = hashlib.sha256(raw_jd.encode("utf-8")).hexdigest()
    raw_fixture = JDParserFixture(
        fixture_id="raw-key",
        input=JDParseRequest(raw_jd=raw_jd),
        expected=ParsedJD(raw_jd=raw_jd, title="原文摘要岗位"),
    )
    external_fixture = JDParserFixture(
        fixture_id="external-key",
        input=JDParseRequest(raw_jd="另一个原文", external_job_id=digest),
        expected=ParsedJD(
            raw_jd="另一个原文",
            external_job_id=digest,
            title="外部 ID 岗位",
        ),
    )
    fake = FakeJDParser([raw_fixture, external_fixture])

    assert fake.parse(raw_fixture.input).title == "原文摘要岗位"
    assert fake.parse(external_fixture.input).title == "外部 ID 岗位"


def test_duplicate_external_id_fails_at_construction() -> None:
    first = load_fixtures()[0]
    duplicate = first.model_copy(deep=True, update={"fixture_id": "duplicate"})

    with pytest.raises(JDParserError, match="重复匹配键"):
        FakeJDParser([first, duplicate])


def test_duplicate_raw_jd_digest_fails_at_construction() -> None:
    first = load_fixtures()[1]
    duplicate = first.model_copy(deep=True, update={"fixture_id": "duplicate"})

    with pytest.raises(JDParserError, match="重复匹配键"):
        FakeJDParser([first, duplicate])


def test_fixture_source_metadata_must_match_expected_output() -> None:
    with pytest.raises(ValidationError):
        JDParserFixture(
            fixture_id="metadata-mismatch",
            input=JDParseRequest(
                raw_jd="原文",
                source_url="https://jobs.example.com/input",
                source_name="input-source",
                external_job_id="input-id",
            ),
            expected=ParsedJD(
                raw_jd="原文",
                source_url="https://jobs.example.com/expected",
                source_name="expected-source",
                external_job_id="expected-id",
            ),
        )


def test_raw_jd_sha256_exact_match_is_used_without_external_id() -> None:
    raw_jd = "\n  原文摘要键测试  \r\n正文  \n"
    fixture = JDParserFixture(
        fixture_id="raw-formatting",
        input=JDParseRequest(raw_jd=raw_jd),
        expected=ParsedJD(raw_jd=raw_jd, title="原文格式岗位"),
    )
    fake = FakeJDParser([fixture])
    parsed = fake.parse(fixture.input)

    expected_digest = hashlib.sha256(raw_jd.encode("utf-8")).hexdigest()
    assert parsed.raw_jd == raw_jd
    assert parsed.title == "原文格式岗位"
    assert f"sha256:{expected_digest}" in fake._fixtures


def test_hash_key_uses_complete_utf8_raw_text_without_normalization() -> None:
    raw_jd = "标题\n正文：中文、é、🙂"
    fixture = JDParserFixture(
        fixture_id="utf8-raw",
        input=JDParseRequest(raw_jd=raw_jd),
        expected=ParsedJD(raw_jd=raw_jd),
    )
    fake = FakeJDParser([fixture])

    assert fake.parse(JDParseRequest(raw_jd=raw_jd)).raw_jd == raw_jd
    with pytest.raises(FakeJDParserNotConfiguredError):
        fake.parse(JDParseRequest(raw_jd=raw_jd + " "))


def test_raw_jd_hash_match_does_not_accept_modified_text() -> None:
    fixture = load_fixtures()[1]
    fake = FakeJDParser([fixture])
    modified = fixture.input.model_copy(update={"raw_jd": fixture.input.raw_jd + " "})

    with pytest.raises(FakeJDParserNotConfiguredError):
        fake.parse(modified)


def test_unknown_external_id_does_not_fall_back_to_matching_raw_text() -> None:
    fixture = load_fixtures()[0]
    fake = FakeJDParser([fixture])
    unknown_id = fixture.input.model_copy(update={"external_job_id": "other-id"})

    with pytest.raises(FakeJDParserNotConfiguredError):
        fake.parse(unknown_id)


def test_fake_miss_does_not_include_full_text_or_fixture_path() -> None:
    fake = FakeJDParser(load_fixtures())
    private_text = "synthetic-unmatched-jd-full-text"

    with pytest.raises(FakeJDParserNotConfiguredError) as exc_info:
        fake.parse(JDParseRequest(raw_jd=private_text))

    assert private_text not in str(exc_info.value)
    assert str(FIXTURE_DIR) not in str(exc_info.value)


def test_parse_is_deterministic_and_returns_independent_deep_copies() -> None:
    fake = FakeJDParser(load_fixtures())
    request = load_fixtures()[2].input
    first = fake.parse(request)
    second = fake.parse(request)

    assert first == second
    assert first is not second
    assert first.responsibilities is not second.responsibilities
    assert first.skills is not second.skills
    assert first.hard_requirements is not second.hard_requirements
    assert first.preferred_qualifications is not second.preferred_qualifications
    assert first.ambiguous_items is not second.ambiguous_items
    assert first.hard_requirements[0] is not second.hard_requirements[0]
    assert first.preferred_qualifications[0] is not second.preferred_qualifications[0]

    first.responsibilities.append("污染职责")
    first.skills.append("PollutingSkill")
    first.hard_requirements[0].text = "污染输出"
    first.preferred_qualifications[0].text = "污染优先项"
    first.ambiguous_items.append("污染歧义项")
    third = fake.parse(request)
    assert "污染职责" not in third.responsibilities
    assert "PollutingSkill" not in third.skills
    assert third.hard_requirements[0].text == "必须掌握 Go"
    assert third.preferred_qualifications[0].text == "具备 Kubernetes 经验"
    assert "污染歧义项" not in third.ambiguous_items


def test_invalid_fixture_is_reported_without_path_or_raw_content(tmp_path: Path) -> None:
    private_text = "fixture-private-raw-text"
    invalid_path = tmp_path / "private-fixture.json"
    invalid_path.write_text(
        '{"fixture_id":"bad","input":{"raw_jd":"'
        + private_text
        + '"},"expected":{"raw_jd":"different"}}',
        encoding="utf-8",
    )

    with pytest.raises(JDParserError) as exc_info:
        load_jd_parser_fixture(invalid_path)

    assert private_text not in str(exc_info.value)
    assert str(tmp_path) not in str(exc_info.value)
    assert exc_info.value.__cause__ is not None


def test_fixture_loader_rejects_malformed_json_safely(tmp_path: Path) -> None:
    invalid_path = tmp_path / "broken.json"
    invalid_path.write_text("{", encoding="utf-8")

    with pytest.raises(JDParserError) as exc_info:
        load_jd_parser_fixture(invalid_path)

    assert str(tmp_path) not in str(exc_info.value)
    assert exc_info.value.__cause__ is not None


def test_contracts_and_ports_have_no_forbidden_architecture_imports() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    targets = [repo_root / "job_agent" / "application" / "contracts", repo_root / "job_agent" / "application" / "ports"]
    forbidden_roots = {
        "sqlalchemy", "alembic", "streamlit", "playwright", "langgraph",
        "openai", "anthropic", "litellm",
    }

    for directory in targets:
        for source_path in directory.glob("*.py"):
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported = {alias.name.split(".")[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported = {node.module.split(".")[0]}
                else:
                    continue
                assert not imported & forbidden_roots, source_path.name

    domain_root = repo_root / "job_agent" / "domain"
    domain_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in domain_root.rglob("*.py")
    )
    assert "job_agent.application.ports.jd_parser" not in domain_text
    assert "job_agent.infrastructure.fakes" not in domain_text


def test_fixtures_are_synthetic_and_free_of_sensitive_literals() -> None:
    sensitive_tokens = (
        "authorization", "cookie", "password", "token", "api_key",
        "手机号", "身份证", "@gmail.com", "@qq.com",
    )
    for path in FIXTURE_DIR.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "[https://" not in text
        assert "example.com" in text
        assert not any(token.casefold() in text.casefold() for token in sensitive_tokens)


def test_fake_does_not_read_env_or_use_network_and_import_has_no_runtime_side_effects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "FAKE-SECRET-MUST-NOT-BE-READ")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: pytest.fail("network used"))
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))

    from job_agent.infrastructure.fakes.jd_parser import FakeJDParser as ImportedFake

    module_path = Path(__import__(ImportedFake.__module__, fromlist=["__file__"]).__file__)
    fake_tree = ast.parse(module_path.read_text(encoding="utf-8"))
    forbidden_roots = {
        "os", "dotenv", "requests", "httpx", "urllib", "socket",
        "sqlalchemy", "job_agent.config",
    }
    imported_roots: set[str] = set()
    for node in ast.walk(fake_tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
            if node.module.startswith("job_agent.config"):
                imported_roots.add("job_agent.config")
    assert not imported_roots & forbidden_roots

    fake = ImportedFake(load_fixtures())
    fixture = load_fixtures()[0]
    result = fake.parse(fixture.input)

    assert result.title == "算法工程师"
    assert "FAKE-SECRET-MUST-NOT-BE-READ" not in repr(result)
    assert not (tmp_path / "data" / "job_agent.db").exists()
    assert not (tmp_path / ".env").exists()


def test_importing_fake_module_does_not_load_fixture_or_create_files(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = (
        "from pathlib import Path\n"
        "_read_text = Path.read_text\n"
        "def _guarded_read_text(path, *args, **kwargs):\n"
        "    if path.suffix.lower() == '.json':\n"
        "        raise AssertionError('JSON fixture read during import')\n"
        "    return _read_text(path, *args, **kwargs)\n"
        "Path.read_text = _guarded_read_text\n"
        "import job_agent.application.contracts.jd_parser\n"
        "import job_agent.application.ports.jd_parser\n"
        "import job_agent.infrastructure.fakes.jd_parser\n"
        "assert not Path('data/job_agent.db').exists()\n"
    )
    env = {**os.environ, "PYTHONPATH": str(repo_root)}
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
