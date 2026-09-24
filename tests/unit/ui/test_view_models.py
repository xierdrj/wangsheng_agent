"""T007 UI ViewModel、错误和 Dashboard 规则测试。"""

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from job_agent.application.contracts import DashboardSummary
from job_agent.application.rules import can_transition
from job_agent.application.services.dashboard import (
    UPCOMING_DEADLINE_DAYS,
    start_of_week,
)
from job_agent.domain import ApplicationStatus, BasicInfo, CandidateProfile, JobPreference
from job_agent.ui.errors import redact_text, to_ui_error
from job_agent.ui.view_models import (
    allowed_target_statuses,
    build_candidate_profile,
    build_job_posting,
    mask_email,
    mask_phone,
    parse_lines,
    parse_optional_datetime,
    reason_is_safe,
    safe_event_details,
    safe_display_url,
    safe_profile_view,
    safe_source_name,
    url_contains_sensitive_data,
)


NOW = datetime(2026, 9, 23, 8, 0, tzinfo=timezone.utc)


def test_profile_form_builds_nested_schema_and_masks_sensitive_fields() -> None:
    profile = build_candidate_profile(
        {
            "candidate_id": "candidate-ui",
            "full_name": "脱敏候选人",
            "email": "candidate@example.com",
            "phone": "13800000000",
            "city": "成都",
            "roles": "Python 工程师\n后端工程师",
            "locations": "成都，上海",
            "industries": "互联网",
            "skills": "Python, SQL",
            "awards": "脱敏奖项",
            "graduation_year": "2027",
            "salary_expectation": "面议",
            "excluded_companies": "示例公司",
            "accepts_travel": True,
            "accepts_relocation": False,
            "education_json": (
                '[{"id":"edu-1","school":"示例大学","degree":"本科",'
                '"major":"计算机"}]'
            ),
            "internships_json": "[]",
            "projects_json": (
                '[{"id":"project-1","organization":"课程项目",'
                '"title":"后端系统","description":"完成脱敏项目"}]'
            ),
        },
        current=None,
        now=NOW,
    )

    assert profile.preferences.roles == ["Python 工程师", "后端工程师"]
    assert profile.preferences.locations == ["成都", "上海"]
    assert profile.education[0].school == "示例大学"
    assert profile.projects[0].id == "project-1"
    assert mask_phone(profile.basic_info.phone) == "138****0000"
    assert mask_email(str(profile.basic_info.email)) == "c***@example.com"
    safe = safe_profile_view(profile)
    assert safe["basic_info"]["phone"] == "138****0000"
    assert "13800000000" not in str(safe)


def test_profile_edit_keeps_sensitive_phone_when_input_is_blank() -> None:
    current = CandidateProfile(
        id="candidate-ui",
        basic_info=BasicInfo(
            full_name="脱敏候选人",
            email="candidate@example.com",
            phone="13800000000",
        ),
        preferences=JobPreference(roles=["Python 工程师"]),
        created_at=NOW,
        updated_at=NOW,
    )
    edited = build_candidate_profile(
        {
            "candidate_id": current.id,
            "full_name": "脱敏候选人（更新）",
            "email": "candidate@example.com",
            "phone": "",
            "roles": "Python 工程师",
            "education_json": "[]",
            "internships_json": "[]",
            "projects_json": "[]",
        },
        current=current,
        now=NOW + timedelta(days=1),
    )
    assert edited.basic_info.phone == current.basic_info.phone
    assert str(edited.basic_info.email) == str(current.basic_info.email)
    assert edited.created_at == current.created_at


@pytest.mark.parametrize(
    "value",
    [
        '{"id":"edu-1"}',
        '[{"id":"edu-1","school":"示例大学","degree":"本科",'
        '"major":"计算机","unknown":"禁止字段"}]',
        '[{"id":"edu-1","school":"示例大学","degree":"本科",'
        '"major":"计算机","start_date":"不是日期"}]',
        '["不是结构化对象"]',
    ],
)
def test_profile_nested_json_rejects_invalid_shapes(value: str) -> None:
    with pytest.raises((ValidationError, ValueError, TypeError)):
        build_candidate_profile(
            {
                "candidate_id": "candidate-ui",
                "full_name": "脱敏候选人",
                "email": "candidate@example.com",
                "phone": "13800000000",
                "roles": "Python 工程师",
                "education_json": value,
                "internships_json": "[]",
                "projects_json": "[]",
            },
            current=None,
            now=NOW,
        )


def test_job_form_parses_lists_and_timezone_datetime() -> None:
    job = build_job_posting(
        {
            "id": "job-ui",
            "company": "脱敏科技",
            "title": "Python 工程师",
            "url": "https://jobs.example.com/job-ui",
            "source": "manual",
            "raw_jd": "负责后端开发",
            "responsibilities": "API 开发\n代码评审",
            "requirements": "Python，SQL",
            "skills": "Python",
            "deadline": "2026-10-01T16:00:00+08:00",
            "fingerprint": "fingerprint-ui",
        },
        now=NOW,
    )
    assert job.responsibilities == ["API 开发", "代码评审"]
    assert job.requirements == ["Python", "SQL"]
    assert job.deadline == datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
    assert job.discovered_at == NOW

    with pytest.raises(ValueError, match="时区"):
        parse_optional_datetime("2026-10-01T16:00:00")


def test_error_and_event_output_are_redacted_and_have_trace_id() -> None:
    raw = "token=secret-value DATABASE_URL=sqlite:///private/path.db"
    redacted = redact_text(raw)
    assert "secret-value" not in redacted
    assert "sqlite:///private/path.db" not in redacted

    error = to_ui_error(RuntimeError(raw))
    assert error.trace_id
    assert error.trace_id != to_ui_error(RuntimeError(raw)).trace_id
    assert "secret-value" not in error.message
    assert "sqlite" not in error.message.lower()

    safe = safe_event_details(
        {
            "nested": {
                "Authorization": "secret-value",
                "items": [{"API-KEY": "another-secret"}],
            },
            "access_token": "secret-value",
            "result": "ok",
        }
    )
    assert safe == {
        "nested": {
            "Authorization": "[已脱敏]",
            "items": [{"API-KEY": "[已脱敏]"}],
        },
        "access_token": "[已脱敏]",
        "result": "ok",
    }
    assert reason_is_safe("状态来自人工更新") is True
    assert reason_is_safe("token=secret-value") is False
    assert url_contains_sensitive_data("https://jobs.example.com/apply?from=campus") is False
    assert (
        safe_display_url("https://user:pass@jobs.example.com/apply?token=x#step")
        == "https://jobs.example.com/apply"
    )
    assert safe_source_name(r"C:\private\resume\candidate.pdf") == "candidate.pdf"
    assert safe_source_name("../../private/candidate.pdf") == "candidate.pdf"


@pytest.mark.parametrize(
    "key",
    ["token", "TOKEN", "api_key", "API-KEY", "password", "Authorization"],
)
def test_sensitive_url_query_key_variants_are_rejected(key: str) -> None:
    assert url_contains_sensitive_data(
        f"https://jobs.example.com/apply?{key}=fake-secret"
    )
    assert url_contains_sensitive_data(f"https://jobs.example.com/apply?{key}")


@pytest.mark.parametrize("status", list(ApplicationStatus))
def test_application_target_options_reuse_t006_rules(status) -> None:
    targets = allowed_target_statuses(status)
    assert status not in targets
    assert targets == [
        target
        for target in ApplicationStatus
        if target is not status and can_transition(status, target)
    ]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            datetime(2026, 9, 21, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 9, 21, 0, 0, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 9, 27, 23, 59, tzinfo=timezone.utc),
            datetime(2026, 9, 21, 0, 0, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 9, 28, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 9, 28, 0, 0, tzinfo=timezone.utc),
        ),
    ],
)
def test_dashboard_week_starts_at_monday_utc(
    value: datetime, expected: datetime
) -> None:
    assert start_of_week(value) == expected


def test_dashboard_window_and_empty_view_model() -> None:
    local = datetime(2026, 9, 23, 16, 0, tzinfo=timezone(timedelta(hours=8)))
    assert start_of_week(local) == datetime(2026, 9, 21, tzinfo=timezone.utc)
    assert UPCOMING_DEADLINE_DAYS == 14
    empty = DashboardSummary(
        jobs_added_this_week=0,
        evidence_pending_review=0,
        applications_pending_submission=0,
        applications_submitted=0,
        online_assessments=0,
        interviews=0,
        offers=0,
    )
    assert empty.recent_events == []
    assert empty.upcoming_jobs == []
    assert parse_lines("\n，,") == []


def test_invalid_profile_and_job_form_data_fail_before_service() -> None:
    with pytest.raises((ValidationError, ValueError)):
        build_candidate_profile(
            {
                "candidate_id": "candidate-ui",
                "full_name": " ",
                "email": "invalid",
                "phone": "",
                "roles": "",
                "education_json": "{}",
                "internships_json": "[]",
                "projects_json": "[]",
            },
            current=None,
            now=NOW,
        )

    with pytest.raises(ValidationError):
        build_job_posting(
            {
                "id": "job-ui",
                "company": "",
                "title": "Python 工程师",
                "url": "not-a-url",
                "source": "manual",
                "raw_jd": "JD",
                "fingerprint": "fingerprint-ui",
            },
            now=NOW,
        )


def test_ui_and_application_query_layers_keep_dependency_boundaries() -> None:
    ui_files = [
        *Path("job_agent/ui/pages").glob("*.py"),
        Path("job_agent/ui/navigation.py"),
        Path("job_agent/ui/view_models.py"),
        Path("job_agent/ui/errors.py"),
    ]
    application_files = [
        Path("job_agent/application/contracts/dashboard.py"),
        Path("job_agent/application/ports/dashboard.py"),
        Path("job_agent/application/services/dashboard.py"),
    ]
    for path in [*ui_files, *application_files]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        imported_modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(module.startswith("sqlalchemy") for module in imported_modules)
        assert not any(
            module.startswith("job_agent.infrastructure")
            for module in imported_modules
        )

    for path in [
        Path("job_agent/application/services/profile.py"),
        Path("job_agent/application/services/job.py"),
        Path("job_agent/application/services/application.py"),
    ]:
        assert "streamlit" not in path.read_text(encoding="utf-8").lower()
