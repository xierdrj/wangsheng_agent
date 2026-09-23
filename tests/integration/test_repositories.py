"""T004 Repository、upsert、分页和事务验收测试。"""

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select

from job_agent.application.contracts import ResumeRecord as ContractResumeRecord
from job_agent.application.ports import (
    DuplicateEntityError,
    EntityNotFoundError,
    ImmutableFieldError,
    InvalidPaginationError,
    RepositoryError,
    ResumeRecord,
)
from job_agent.domain import (
    ApplicationAnswer,
    ApplicationEvent,
    ApplicationRecord,
    ApplicationStatus,
    BasicInfo,
    CandidateProfile,
    EvidenceVerification,
    JobPosting,
    JobPreference,
    MatchDimension,
    MatchResult,
    ResumeEvidence,
    ResumeVersion,
)
from job_agent.infrastructure.database import create_engine_from_url, initialize_database
from job_agent.infrastructure.database.models import (
    ApplicationORM,
    CandidateORM,
    JobMatchORM,
    JobORM,
    ResumeORM,
)
from job_agent.infrastructure.database.repositories import (
    SqlAlchemyApplicationRepository,
    SqlAlchemyCandidateRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyMatchRepository,
    SqlAlchemyResumeEvidenceRepository,
    SqlAlchemyResumeRepository,
    SqlAlchemyResumeVersionRepository,
)
from job_agent.infrastructure.database.session import create_session_factory, session_scope


UTC_PLUS_8 = timezone(timedelta(hours=8))
NOW = datetime(2026, 9, 23, 10, 0, tzinfo=UTC_PLUS_8)


@pytest.fixture()
def session_factory(tmp_path):
    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'repositories.sqlite3'}")
    initialize_database(engine)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        engine.dispose()


def candidate(entity_id: str = "candidate-1", *, minutes: int = 0) -> CandidateProfile:
    timestamp = NOW + timedelta(minutes=minutes)
    return CandidateProfile(
        id=entity_id,
        basic_info=BasicInfo(
            full_name=f"脱敏候选人-{entity_id}",
            email=f"{entity_id}@example.com",
            phone="13800000000",
        ),
        preferences=JobPreference(roles=["算法工程师"]),
        skills=["Python"],
        created_at=timestamp,
        updated_at=timestamp,
    )


def job(
    entity_id: str = "job-1", *, fingerprint: str = "fingerprint-1", minutes: int = 0
) -> JobPosting:
    return JobPosting(
        id=entity_id,
        company="脱敏科技",
        title="算法工程师",
        url=f"https://jobs.example.com/{entity_id}",
        source="fixture",
        raw_jd="负责模型训练",
        responsibilities=["模型训练"],
        requirements=["Python"],
        fingerprint=fingerprint,
        discovered_at=NOW + timedelta(minutes=minutes),
    )


def application(entity_id: str = "application-1", *, status=ApplicationStatus.DISCOVERED):
    return ApplicationRecord(
        id=entity_id,
        candidate_id="candidate-1",
        job_id="job-1",
        status=status,
        application_url="https://apply.example.com/job-1",
        last_updated_at=NOW,
    )


def seed_candidate_and_job(session) -> None:
    SqlAlchemyCandidateRepository(session).add(candidate())
    SqlAlchemyJobRepository(session).add(job())


def test_candidate_crud_returns_domain_models(session_factory) -> None:
    with session_scope(session_factory) as session:
        repository = SqlAlchemyCandidateRepository(session)
        created = repository.add(candidate())
        assert isinstance(created, CandidateProfile)
        assert repository.get_by_id(created.id) == created

        updated_input = created.model_copy(
            update={
                "skills": ["Python", "SQL"],
                "created_at": NOW + timedelta(days=10),
                "updated_at": NOW + timedelta(hours=1),
            }
        )
        updated = repository.update(updated_input)
        assert updated.skills == ["Python", "SQL"]
        assert updated.created_at == created.created_at
        assert repository.delete(created.id) is True
        assert repository.delete(created.id) is False
        assert repository.get_by_id(created.id) is None

        with pytest.raises(EntityNotFoundError):
            repository.update(updated_input)


def test_evidence_and_resume_version_crud(session_factory) -> None:
    with session_scope(session_factory) as session:
        seed_candidate_and_job(session)
        evidence_repository = SqlAlchemyResumeEvidenceRepository(session)
        evidence = ResumeEvidence(
            id="evidence-1",
            candidate_id="candidate-1",
            category="project",
            content="完成脱敏项目",
            verification=EvidenceVerification.VERIFIED,
            created_at=NOW,
            updated_at=NOW,
        )
        assert evidence_repository.add(evidence) == evidence
        assert evidence_repository.get_by_id(evidence.id) == evidence
        changed = evidence.model_copy(update={"content": "完成脱敏项目并验证", "updated_at": NOW})
        assert evidence_repository.update(changed).content.endswith("验证")
        evidence_page = evidence_repository.list(limit=10, offset=0)
        assert isinstance(evidence_page.items[0], ResumeEvidence)
        assert (evidence_page.total, evidence_page.limit, evidence_page.offset) == (1, 10, 0)

        version_repository = SqlAlchemyResumeVersionRepository(session)
        version = ResumeVersion(
            id="version-1",
            candidate_id="candidate-1",
            job_id="job-1",
            base_resume_id="resume-base",
            content={"summary": "脱敏摘要"},
            source_evidence_ids=["evidence-1"],
            content_hash="version-hash",
            created_at=NOW,
        )
        assert version_repository.add(version) == version
        assert version_repository.get_by_id(version.id) == version
        changed_version = version.model_copy(update={"content": {"summary": "更新后的摘要"}})
        assert version_repository.update(changed_version).content["summary"] == "更新后的摘要"
        version_page = version_repository.list(limit=10, offset=0)
        assert isinstance(version_page.items[0], ResumeVersion)
        assert (version_page.total, version_page.limit, version_page.offset) == (1, 10, 0)
        assert version_repository.delete(version.id) is True
        assert version_repository.delete(version.id) is False
        assert version_repository.get_by_id(version.id) is None
        with pytest.raises(EntityNotFoundError):
            version_repository.update(changed_version)

        assert evidence_repository.delete(evidence.id) is True
        assert evidence_repository.delete(evidence.id) is False
        assert evidence_repository.get_by_id(evidence.id) is None
        with pytest.raises(EntityNotFoundError):
            evidence_repository.update(changed)


def test_job_crud_upsert_preserves_business_key_and_id(session_factory) -> None:
    with session_scope(session_factory) as session:
        repository = SqlAlchemyJobRepository(session)
        original = repository.add(job())
        assert repository.get_by_id(original.id) == original
        changed = original.model_copy(update={"title": "中级算法工程师"})
        assert repository.update(changed).title == "中级算法工程师"
        incoming = job("different-id", fingerprint=original.fingerprint).model_copy(
            update={
                "title": "高级算法工程师",
                "raw_jd": "更新后的 JD",
                "discovered_at": NOW + timedelta(days=1),
            }
        )
        updated = repository.upsert(incoming)

        assert updated.id == original.id
        assert updated.fingerprint == original.fingerprint
        assert updated.discovered_at == original.discovered_at
        assert updated.title == "高级算法工程师"
        job_page = repository.list(limit=10, offset=0)
        assert isinstance(job_page.items[0], JobPosting)
        assert (job_page.total, job_page.limit, job_page.offset) == (1, 10, 0)
        assert repository.get_by_fingerprint(original.fingerprint) == updated

        with pytest.raises(ImmutableFieldError):
            repository.update(updated.model_copy(update={"fingerprint": "new-key"}))
        assert repository.delete(updated.id) is True
        assert repository.delete(updated.id) is False
        assert repository.get_by_id(updated.id) is None
        with pytest.raises(EntityNotFoundError):
            repository.update(updated)


def test_resume_and_match_upsert_are_idempotent(session_factory) -> None:
    with session_scope(session_factory) as session:
        seed_candidate_and_job(session)
        resume_repository = SqlAlchemyResumeRepository(session)
        original_resume = ResumeRecord(
            id="resume-1",
            candidate_id="candidate-1",
            name="初始简历",
            source_file_path="fixtures/resume.pdf",
            content_hash="resume-hash",
        )
        resume_repository.add(original_resume)
        assert resume_repository.get_by_id(original_resume.id) == original_resume
        changed_resume = original_resume.model_copy(update={"source_file_path": "fixtures/v2.pdf"})
        assert resume_repository.update(changed_resume).source_file_path.endswith("v2.pdf")
        updated_resume = resume_repository.upsert(
            original_resume.model_copy(update={"id": "ignored-id", "name": "更新简历"})
        )
        assert updated_resume.id == "resume-1"
        assert (updated_resume.candidate_id, updated_resume.content_hash) == (
            original_resume.candidate_id,
            original_resume.content_hash,
        )
        assert updated_resume.name == "更新简历"
        resume_page = resume_repository.list(limit=10, offset=0)
        assert isinstance(resume_page.items[0], ResumeRecord)
        assert (resume_page.total, resume_page.limit, resume_page.offset) == (1, 10, 0)

        match_repository = SqlAlchemyMatchRepository(session)
        original_match = MatchResult(
            id="match-1",
            candidate_id="candidate-1",
            job_id="job-1",
            hard_filter_passed=True,
            overall_score=70,
            recommendation="REVIEW",
            created_at=NOW,
        )
        match_repository.add(original_match)
        assert match_repository.get_by_id(original_match.id) == original_match
        changed_match = original_match.model_copy(update={"overall_score": 75})
        assert match_repository.update(changed_match).overall_score == 75
        updated_match = match_repository.upsert(
            original_match.model_copy(
                update={
                    "id": "ignored-match-id",
                    "overall_score": 90,
                    "dimensions": [MatchDimension(name="skills", score=90, weight=1)],
                    "created_at": NOW + timedelta(days=1),
                }
            )
        )
        assert updated_match.id == "match-1"
        assert (updated_match.candidate_id, updated_match.job_id) == (
            original_match.candidate_id,
            original_match.job_id,
        )
        assert updated_match.overall_score == 90
        assert updated_match.created_at == original_match.created_at
        match_page = match_repository.list(limit=10, offset=0)
        assert isinstance(match_page.items[0], MatchResult)
        assert (match_page.total, match_page.limit, match_page.offset) == (1, 10, 0)

        assert match_repository.delete(updated_match.id) is True
        assert match_repository.delete(updated_match.id) is False
        assert match_repository.get_by_id(updated_match.id) is None
        with pytest.raises(EntityNotFoundError):
            match_repository.update(updated_match)

        assert resume_repository.delete(updated_resume.id) is True
        assert resume_repository.delete(updated_resume.id) is False
        assert resume_repository.get_by_id(updated_resume.id) is None
        with pytest.raises(EntityNotFoundError):
            resume_repository.update(updated_resume)


def test_application_upsert_and_aggregate_children(session_factory) -> None:
    with session_scope(session_factory) as session:
        seed_candidate_and_job(session)
        repository = SqlAlchemyApplicationRepository(session)
        original = repository.add(application())
        assert repository.get_by_id(original.id) == original
        changed = original.model_copy(update={"application_url": "https://apply.example.com/v2"})
        assert repository.update(changed).application_url.endswith("/v2")
        updated = repository.upsert(
            application("ignored-id", status=ApplicationStatus.PREPARING).model_copy(
                update={"application_url": "https://apply.example.com/updated"}
            )
        )
        assert updated.id == original.id
        assert (updated.candidate_id, updated.job_id) == (original.candidate_id, original.job_id)
        assert updated.status is ApplicationStatus.PREPARING
        application_page = repository.list(limit=10, offset=0)
        assert isinstance(application_page.items[0], ApplicationRecord)
        assert (application_page.total, application_page.limit, application_page.offset) == (
            1,
            10,
            0,
        )

        answer = ApplicationAnswer(
            id="answer-1",
            application_id=original.id,
            question="请介绍项目",
            question_type="text",
            answer="脱敏回答",
            created_at=NOW,
        )
        event = ApplicationEvent(
            id="event-1",
            application_id=original.id,
            event_type="status_changed",
            from_status=ApplicationStatus.DISCOVERED,
            to_status=ApplicationStatus.PREPARING,
            source="test",
            occurred_at=NOW,
        )
        assert isinstance(repository.add_answer(answer), ApplicationAnswer)
        assert isinstance(repository.append_event(event), ApplicationEvent)
        earlier_id_answer = answer.model_copy(update={"id": "answer-0", "question": "请介绍技能"})
        earlier_id_event = event.model_copy(update={"id": "event-0", "event_type": "prepared"})
        repository.add_answer(earlier_id_answer)
        repository.append_event(earlier_id_event)

        first_answers = repository.list_answers(original.id, limit=1, offset=0)
        second_answers = repository.list_answers(original.id, limit=1, offset=1)
        first_events = repository.list_events(original.id, limit=1, offset=0)
        second_events = repository.list_events(original.id, limit=1, offset=1)
        assert [item.id for item in first_answers.items] == ["answer-0"]
        assert [item.id for item in second_answers.items] == ["answer-1"]
        assert (first_answers.total, first_answers.limit, first_answers.offset) == (2, 1, 0)
        assert [item.id for item in first_events.items] == ["event-0"]
        assert [item.id for item in second_events.items] == ["event-1"]
        assert (first_events.total, first_events.limit, first_events.offset) == (2, 1, 0)

        assert repository.delete(updated.id) is True
        assert repository.delete(updated.id) is False
        assert repository.get_by_id(updated.id) is None
        assert repository.list_answers(updated.id).items == []
        assert repository.list_events(updated.id).items == []
        with pytest.raises(EntityNotFoundError):
            repository.update(updated)


def test_pagination_validation_total_and_stable_order(session_factory) -> None:
    with session_scope(session_factory) as session:
        repository = SqlAlchemyCandidateRepository(session)
        repository.add(candidate("candidate-c", minutes=1))
        repository.add(candidate("candidate-b", minutes=0))
        repository.add(candidate("candidate-a", minutes=0))

        first = repository.list(limit=2, offset=0)
        second = repository.list(limit=2, offset=2)
        repeated = repository.list(limit=2, offset=0)

        assert first.total == 3
        assert (first.limit, first.offset) == (2, 0)
        assert [item.id for item in first.items] == ["candidate-a", "candidate-b"]
        assert [item.id for item in repeated.items] == ["candidate-a", "candidate-b"]
        assert [item.id for item in second.items] == ["candidate-c"]
        assert not ({item.id for item in first.items} & {item.id for item in second.items})
        assert repository.list(limit=10, offset=100).items == []

        for limit, offset in [(0, 0), (101, 0), (True, 0), (1, -1), (1, True)]:
            with pytest.raises(InvalidPaginationError):
                repository.list(limit=limit, offset=offset)


def test_resume_record_is_application_contract_and_matches_persistence_fields() -> None:
    contract_source = Path("job_agent/application/contracts/resume.py").read_text(encoding="utf-8")
    assert ResumeRecord is ContractResumeRecord
    expected_fields = {
        "id",
        "candidate_id",
        "name",
        "source_file_path",
        "content_hash",
        "parsed_content",
    }
    orm_fields = {
        column.name.removesuffix("_json") for column in ResumeORM.__table__.columns
    }
    assert set(ResumeRecord.model_fields) == expected_fields == orm_fields
    imported_modules = {
        node.module.split(".", 1)[0]
        for node in ast.walk(ast.parse(contract_source))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imported_modules.update(
        alias.name.split(".", 1)[0]
        for node in ast.walk(ast.parse(contract_source))
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert "sqlalchemy" not in imported_modules


def test_duplicate_error_preserves_session_and_repository_never_commits(session_factory) -> None:
    session = session_factory()
    try:
        session.commit = Mock(side_effect=AssertionError("Repository 不得提交事务"))
        repository = SqlAlchemyCandidateRepository(session)
        repository.add(candidate())
        with pytest.raises(DuplicateEntityError) as captured:
            repository.add(candidate())
        assert captured.value.__cause__ is not None

        repository.add(candidate("candidate-2"))
        assert repository.list().total == 2
        session.commit.assert_not_called()
        session.rollback()
    finally:
        session.close()

    with session_scope(session_factory) as verification_session:
        assert SqlAlchemyCandidateRepository(verification_session).list().total == 0


def test_foreign_key_error_is_converted_and_keeps_exception_chain(session_factory) -> None:
    with session_scope(session_factory) as session:
        repository = SqlAlchemyResumeEvidenceRepository(session)
        orphan = ResumeEvidence(
            id="orphan",
            candidate_id="missing",
            category="project",
            content="无父记录",
            created_at=NOW,
            updated_at=NOW,
        )
        with pytest.raises(RepositoryError) as captured:
            repository.add(orphan)
        assert not isinstance(captured.value, DuplicateEntityError)
        assert captured.value.__cause__ is not None
        SqlAlchemyCandidateRepository(session).add(candidate())


def test_multiple_repositories_share_transaction_and_roll_back_together(session_factory) -> None:
    with pytest.raises(RuntimeError):
        with session_scope(session_factory) as session:
            SqlAlchemyCandidateRepository(session).add(candidate())
            SqlAlchemyJobRepository(session).add(job())
            SqlAlchemyApplicationRepository(session).add(application())
            raise RuntimeError("模拟跨 Repository 失败")

    with session_scope(session_factory) as session:
        assert session.scalar(select(func.count()).select_from(CandidateORM)) == 0
        assert session.scalar(select(func.count()).select_from(JobORM)) == 0
        assert session.scalar(select(func.count()).select_from(ApplicationORM)) == 0
        assert session.scalar(select(func.count()).select_from(ResumeORM)) == 0
        assert session.scalar(select(func.count()).select_from(JobMatchORM)) == 0
