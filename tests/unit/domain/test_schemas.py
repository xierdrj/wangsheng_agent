"""T002 领域枚举和 Schema 验收测试。"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from job_agent.domain import (
    ApplicationAnswer,
    ApplicationEvent,
    ApplicationRecord,
    ApplicationStatus,
    BasicInfo,
    CandidateProfile,
    Education,
    EvidenceVerification,
    Experience,
    FormField,
    JobPosting,
    JobPreference,
    MatchDimension,
    MatchResult,
    ResumeEvidence,
    ResumeVersion,
    ReviewDecision,
)


NOW = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)


def candidate_profile(**overrides: object) -> CandidateProfile:
    values: dict[str, object] = {
        "id": "candidate-001",
        "basic_info": {
            "full_name": "测试候选人",
            "email": "candidate@example.com",
            "phone": "13800000000",
        },
        "preferences": {"roles": ["算法工程师"]},
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return CandidateProfile(**values)


def test_all_core_schemas_accept_valid_data() -> None:
    profile = candidate_profile()
    assert profile.basic_info.email == "candidate@example.com"

    education = Education(id="edu-1", school="示例大学", degree="本科", major="计算机")
    experience = Experience(
        id="exp-1", organization="示例公司", title="实习生", description="完成数据处理任务"
    )
    assert education.school and experience.organization

    evidence = ResumeEvidence(
        id="evidence-1",
        candidate_id=profile.id,
        category="project",
        content="实现了一个可复现的数据处理流程",
        created_at=NOW,
        updated_at=NOW,
    )
    job = JobPosting(
        id="job-1",
        company="示例科技",
        title="算法工程师",
        url="https://jobs.example.com/job-1",
        source="fixture",
        raw_jd="负责模型训练和评估",
        fingerprint="fingerprint-1",
        discovered_at=NOW,
    )
    match = MatchResult(
        id="match-1",
        candidate_id=profile.id,
        job_id=job.id,
        hard_filter_passed=True,
        overall_score=86.5,
        recommendation="SHORTLIST",
        created_at=NOW,
    )
    resume = ResumeVersion(
        id="resume-1",
        candidate_id=profile.id,
        job_id=job.id,
        base_resume_id="resume-base",
        content={"summary": "基于证据的摘要"},
        content_hash="hash-1",
        created_at=NOW,
    )
    answer = ApplicationAnswer(
        id="answer-1",
        application_id="application-1",
        question="请介绍一个项目",
        question_type="text",
        answer="项目回答",
        created_at=NOW,
    )
    field = FormField(id="field-1", label="姓名", field_type="text")
    application = ApplicationRecord(
        id="application-1",
        candidate_id=profile.id,
        job_id=job.id,
        status=ApplicationStatus.DISCOVERED,
        application_url="https://apply.example.com/job-1",
        last_updated_at=NOW,
    )
    event = ApplicationEvent(
        id="event-1",
        application_id=application.id,
        event_type="created",
        to_status=ApplicationStatus.DISCOVERED,
        source="test",
        occurred_at=NOW,
    )

    assert evidence.verification is EvidenceVerification.UNVERIFIED
    assert match.overall_score == 86.5
    assert resume.content_hash == "hash-1"
    assert answer.is_user_edited is False
    assert field.confidence == 0
    assert event.to_status is ApplicationStatus.DISCOVERED


def test_candidate_profile_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        candidate_profile(unexpected="not allowed")


def test_invalid_email_is_rejected() -> None:
    with pytest.raises(ValidationError):
        candidate_profile(
            basic_info={"full_name": "测试候选人", "email": "not-an-email", "phone": "1"}
        )


def test_job_preference_requires_at_least_one_role() -> None:
    with pytest.raises(ValidationError):
        JobPreference(roles=[])


@pytest.mark.parametrize(
    ("field", "value"),
    [("score", -0.1), ("score", 100.1), ("weight", -0.1), ("weight", 1.1)],
)
def test_match_dimension_rejects_out_of_range_values(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        values = {"name": "skills", "score": 50, "weight": 0.5, field: value}
        MatchDimension(**values)


def test_match_result_rejects_out_of_range_overall_score() -> None:
    with pytest.raises(ValidationError):
        MatchResult(
            id="match-1",
            candidate_id="candidate-1",
            job_id="job-1",
            hard_filter_passed=True,
            overall_score=101,
            recommendation="SHORTLIST",
            created_at=NOW,
        )


def test_form_field_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValidationError):
        FormField(id="field-1", field_type="text", confidence=1.1)


@pytest.mark.parametrize("limit", [0, -1])
def test_application_answer_rejects_non_positive_character_limit(limit: int) -> None:
    with pytest.raises(ValidationError):
        ApplicationAnswer(
            id="answer-1",
            application_id="application-1",
            question="问题",
            question_type="text",
            answer="回答",
            character_limit=limit,
            created_at=NOW,
        )


def test_invalid_enum_value_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ApplicationRecord(
            id="application-1",
            candidate_id="candidate-1",
            job_id="job-1",
            status="UNKNOWN",
            application_url="https://apply.example.com/job-1",
            last_updated_at=NOW,
        )


def test_enum_values_are_serializable_strings() -> None:
    assert ApplicationStatus.SUBMITTED.value == "SUBMITTED"
    assert EvidenceVerification.VERIFIED.value == "VERIFIED"
    assert ReviewDecision.APPROVE.value == "APPROVE"


def test_mutable_defaults_are_independent() -> None:
    first = candidate_profile()
    second = candidate_profile()
    first.skills.append("Python")
    first.preferences.roles.append("数据工程师")

    assert second.skills == []
    assert second.preferences.roles == ["算法工程师"]


def test_naive_datetimes_are_rejected() -> None:
    with pytest.raises(ValidationError):
        candidate_profile(created_at=datetime(2026, 1, 1, 8, 0))

    with pytest.raises(ValidationError):
        ResumeEvidence(
            id="evidence-1",
            candidate_id="candidate-1",
            category="project",
            content="事实内容",
            created_at=datetime(2026, 1, 1, 8, 0),
            updated_at=NOW,
        )
