"""T006 Job 与 Application Service 集成验收测试。"""

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from job_agent.application.contracts import (
    AddToApplicationPoolRequest,
    ApplicationTransitionRequest,
)
from job_agent.application.ports import (
    DuplicateEntityError,
    EntityNotFoundError,
)
from job_agent.application.services import (
    APPLICATION_CREATED,
    STATUS_CHANGED,
    ApplicationConflictError,
    ApplicationService,
    InvalidApplicationTransitionError,
    JobService,
)
from job_agent.domain import (
    ApplicationEvent,
    ApplicationRecord,
    ApplicationStatus,
    BasicInfo,
    CandidateProfile,
    JobPosting,
    JobPreference,
    ResumeVersion,
)
from job_agent.infrastructure.database import (
    SqlAlchemyJobApplicationUnitOfWork,
    create_engine_from_url,
    create_session_factory,
    initialize_database,
)
from job_agent.infrastructure.database.models import ApplicationORM, JobORM


UTC_PLUS_8 = timezone(timedelta(hours=8))
CALLER_TIME = datetime(2026, 1, 1, 8, 0, tzinfo=UTC_PLUS_8)
NOW = datetime(2026, 11, 1, 2, 0, tzinfo=timezone.utc)


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return self.value


class SequentialEventIds:
    def __init__(self) -> None:
        self._index = 0

    def __call__(self) -> str:
        self._index += 1
        return f"event-{self._index:03d}"


@pytest.fixture()
def session_factory(tmp_path):
    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'job-application.sqlite3'}")
    initialize_database(engine)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture()
def service_context(session_factory):
    clock = MutableClock(NOW)
    event_ids = SequentialEventIds()
    unit_of_work_factory = lambda: SqlAlchemyJobApplicationUnitOfWork(session_factory)
    return (
        JobService(unit_of_work_factory),
        ApplicationService(
            unit_of_work_factory,
            clock=clock,
            event_id_factory=event_ids,
        ),
        clock,
        unit_of_work_factory,
    )


def candidate(candidate_id: str = "candidate-1") -> CandidateProfile:
    return CandidateProfile(
        id=candidate_id,
        basic_info=BasicInfo(
            full_name=f"脱敏候选人-{candidate_id}",
            email=f"{candidate_id}@example.com",
            phone="13800000000",
        ),
        preferences=JobPreference(roles=["Python 工程师"]),
        created_at=CALLER_TIME,
        updated_at=CALLER_TIME,
    )


def job(
    job_id: str = "job-1",
    *,
    fingerprint: str = "fingerprint-1",
) -> JobPosting:
    return JobPosting(
        id=job_id,
        company="脱敏科技",
        title="Python 工程师",
        url=f"https://jobs.example.com/{job_id}",
        source="manual",
        raw_jd="负责后端服务开发",
        requirements=["Python"],
        fingerprint=fingerprint,
        discovered_at=CALLER_TIME,
    )


def pool_request(
    application_id: str = "application-1",
    *,
    candidate_id: str = "candidate-1",
    job_id: str = "job-1",
    resume_version_id: str | None = None,
    source: str = "manual_test",
) -> AddToApplicationPoolRequest:
    return AddToApplicationPoolRequest(
        application_id=application_id,
        candidate_id=candidate_id,
        job_id=job_id,
        application_url=f"https://apply.example.com/{job_id}",
        resume_version_id=resume_version_id,
        source=source,
    )


def seed_candidate(unit_of_work_factory, candidate_id: str = "candidate-1") -> None:
    with unit_of_work_factory() as unit_of_work:
        unit_of_work.candidates.add(candidate(candidate_id))


def test_job_service_upserts_by_fingerprint_and_preserves_immutable_fields(
    service_context,
) -> None:
    job_service, _, _, _ = service_context
    original = job_service.save_manual_job(job())
    incoming = job("incoming-id", fingerprint=original.fingerprint).model_copy(
        update={
            "title": "高级 Python 工程师",
            "raw_jd": "更新后的结构化 JD",
            "discovered_at": CALLER_TIME + timedelta(days=10),
        }
    )

    updated = job_service.save_manual_job(incoming)
    page = job_service.list_jobs(limit=10, offset=0)

    assert isinstance(updated, JobPosting)
    assert updated.id == original.id
    assert updated.fingerprint == original.fingerprint
    assert updated.discovered_at == original.discovered_at.astimezone(timezone.utc)
    assert updated.title == "高级 Python 工程师"
    assert job_service.get_job(original.id) == updated
    assert job_service.get_job("missing") is None
    assert (page.total, page.limit, page.offset) == (1, 10, 0)
    assert not isinstance(updated, JobORM)

    with pytest.raises(ValueError, match="fingerprint"):
        job_service.save_manual_job(job("blank").model_copy(update={"fingerprint": "   "}))


def test_add_to_pool_creates_shortlisted_application_event_and_is_idempotent(
    service_context,
) -> None:
    job_service, application_service, _, unit_of_work_factory = service_context
    seed_candidate(unit_of_work_factory)
    job_service.save_manual_job(job())
    request = pool_request()

    created = application_service.add_to_application_pool(request)
    repeated = application_service.add_to_application_pool(request)
    page = application_service.list_applications("candidate-1", limit=10, offset=0)
    timeline = application_service.list_application_events(created.id)

    assert isinstance(created, ApplicationRecord)
    assert created == repeated
    assert created.status is ApplicationStatus.SHORTLISTED
    assert created.submitted_at is None
    assert created.last_updated_at == NOW
    assert created.last_updated_at.tzinfo is timezone.utc
    assert application_service.get_application(created.id) == created
    assert application_service.get_application("missing") is None
    assert (page.items, page.total) == ([created], 1)
    assert timeline.total == 1
    assert timeline.items[0].event_type == APPLICATION_CREATED
    assert timeline.items[0].from_status is None
    assert timeline.items[0].to_status is ApplicationStatus.SHORTLISTED
    assert timeline.items[0].source == request.source
    assert timeline.items[0].occurred_at == created.last_updated_at
    assert not isinstance(created, ApplicationORM)

    with pytest.raises(ApplicationConflictError):
        application_service.add_to_application_pool(
            request.model_copy(update={"application_url": "https://apply.example.com/changed"})
        )
    assert application_service.list_application_events(created.id).total == 1

    advanced = application_service.transition_status(
        ApplicationTransitionRequest(
            application_id=created.id,
            to_status=ApplicationStatus.PREPARING,
            source="user",
        )
    )
    assert application_service.add_to_application_pool(request) == advanced
    assert application_service.list_application_events(created.id).total == 2


def test_pool_creation_validates_candidate_job_url_and_resume_ownership(
    service_context,
) -> None:
    job_service, application_service, _, unit_of_work_factory = service_context
    seed_candidate(unit_of_work_factory, "candidate-1")
    seed_candidate(unit_of_work_factory, "candidate-2")
    job_service.save_manual_job(job())

    with pytest.raises(EntityNotFoundError, match="候选人"):
        application_service.add_to_application_pool(
            pool_request("missing-candidate", candidate_id="missing")
        )
    with pytest.raises(EntityNotFoundError, match="岗位"):
        application_service.add_to_application_pool(
            pool_request("missing-job", job_id="missing")
        )
    with pytest.raises(ValidationError):
        application_service.add_to_application_pool(
            {
                **pool_request("bad-url").model_dump(mode="python"),
                "application_url": "not-a-url",
            }
        )

    with unit_of_work_factory() as unit_of_work:
        unit_of_work.resume_versions.add(
            ResumeVersion(
                id="resume-version-1",
                candidate_id="candidate-1",
                job_id="job-1",
                base_resume_id="resume-base",
                content={"summary": "脱敏摘要"},
                content_hash="resume-version-hash",
                created_at=CALLER_TIME,
            )
        )

    with pytest.raises(EntityNotFoundError, match="简历版本"):
        application_service.add_to_application_pool(
            pool_request("missing-resume", resume_version_id="missing")
        )
    with pytest.raises(ApplicationConflictError, match="不属于"):
        application_service.add_to_application_pool(
            pool_request(
                "wrong-owner",
                candidate_id="candidate-2",
                resume_version_id="resume-version-1",
            )
        )

    created = application_service.add_to_application_pool(
        pool_request("with-resume", resume_version_id="resume-version-1")
    )
    assert created.resume_version_id == "resume-version-1"


def test_status_transition_appends_event_and_rejects_illegal_or_idempotent_changes(
    service_context,
) -> None:
    job_service, application_service, clock, unit_of_work_factory = service_context
    seed_candidate(unit_of_work_factory)
    job_service.save_manual_job(job())
    created = application_service.add_to_application_pool(pool_request())

    clock.value = NOW
    preparing = application_service.transition_status(
        ApplicationTransitionRequest(
            application_id=created.id,
            to_status=ApplicationStatus.PREPARING,
            source="user",
            details={"reason": "开始准备材料"},
        )
    )
    assert preparing.status is ApplicationStatus.PREPARING
    assert preparing.last_updated_at == NOW + timedelta(microseconds=1)
    assert preparing.submitted_at is None

    clock.value = NOW + timedelta(hours=1)
    clock_calls_before_retry = clock.calls
    repeated = application_service.transition_status(
        ApplicationTransitionRequest(
            application_id=created.id,
            to_status=ApplicationStatus.PREPARING,
            source="retry",
        )
    )
    assert repeated == preparing
    assert clock.calls == clock_calls_before_retry
    assert application_service.list_application_events(created.id).total == 2

    with pytest.raises(InvalidApplicationTransitionError):
        application_service.transition_status(
            ApplicationTransitionRequest(
                application_id=created.id,
                to_status=ApplicationStatus.SHORTLISTED,
                source="user",
            )
        )
    assert application_service.get_application(created.id) == preparing
    assert application_service.list_application_events(created.id).total == 2

    rejected = application_service.transition_status(
        ApplicationTransitionRequest(
            application_id=created.id,
            to_status=ApplicationStatus.REJECTED,
            source="user",
        )
    )
    assert rejected.status is ApplicationStatus.REJECTED
    with pytest.raises(InvalidApplicationTransitionError):
        application_service.transition_status(
            ApplicationTransitionRequest(
                application_id=created.id,
                to_status=ApplicationStatus.INTERVIEW,
                source="user",
            )
        )

    timeline = application_service.list_application_events(created.id)
    assert [item.event_type for item in timeline.items] == [
        APPLICATION_CREATED,
        STATUS_CHANGED,
        STATUS_CHANGED,
    ]
    assert timeline.items[1].details == {"reason": "开始准备材料"}
    assert timeline.items[1].from_status is ApplicationStatus.SHORTLISTED
    assert timeline.items[1].to_status is ApplicationStatus.PREPARING
    assert timeline.items[1].occurred_at == preparing.last_updated_at
    assert timeline.items[1].occurred_at < timeline.items[2].occurred_at


def test_status_transition_rejects_missing_application(service_context) -> None:
    _, application_service, _, _ = service_context

    with pytest.raises(EntityNotFoundError, match="投递记录"):
        application_service.transition_status(
            ApplicationTransitionRequest(
                application_id="missing",
                to_status=ApplicationStatus.PREPARING,
                source="user",
            )
        )


def test_clock_is_normalized_to_utc_and_rejects_naive_datetime(
    session_factory,
) -> None:
    unit_of_work_factory = lambda: SqlAlchemyJobApplicationUnitOfWork(session_factory)
    job_service = JobService(unit_of_work_factory)
    seed_candidate(unit_of_work_factory)
    job_service.save_manual_job(job())

    service = ApplicationService(
        unit_of_work_factory,
        clock=lambda: CALLER_TIME,
        event_id_factory=lambda: "timezone-event",
    )
    created = service.add_to_application_pool(pool_request())
    assert created.last_updated_at == CALLER_TIME.astimezone(timezone.utc)
    assert created.last_updated_at.tzinfo is timezone.utc

    job_service.save_manual_job(job("job-2", fingerprint="fingerprint-2"))
    naive_service = ApplicationService(
        unit_of_work_factory,
        clock=lambda: datetime(2026, 1, 1, 0, 0),
        event_id_factory=lambda: "naive-event",
    )
    with pytest.raises(ValueError, match="带时区"):
        naive_service.add_to_application_pool(
            pool_request("application-2", job_id="job-2")
        )
    assert naive_service.get_application("application-2") is None


def test_submitted_at_is_set_once_for_direct_and_later_transitions(service_context) -> None:
    job_service, application_service, clock, unit_of_work_factory = service_context
    seed_candidate(unit_of_work_factory)
    for index in range(1, 4):
        job_service.save_manual_job(job(f"job-{index}", fingerprint=f"fingerprint-{index}"))
        application_service.add_to_application_pool(
            pool_request(f"application-{index}", job_id=f"job-{index}")
        )

    clock.value = NOW + timedelta(hours=1)
    submitted = application_service.transition_status(
        ApplicationTransitionRequest(
            application_id="application-1",
            to_status=ApplicationStatus.SUBMITTED,
            source="user",
        )
    )
    clock.value = NOW + timedelta(hours=2)
    interview = application_service.transition_status(
        ApplicationTransitionRequest(
            application_id="application-1",
            to_status=ApplicationStatus.INTERVIEW,
            source="user",
        )
    )
    direct_interview = application_service.transition_status(
        ApplicationTransitionRequest(
            application_id="application-2",
            to_status=ApplicationStatus.INTERVIEW,
            source="user",
        )
    )
    withdrawn = application_service.transition_status(
        ApplicationTransitionRequest(
            application_id="application-3",
            to_status=ApplicationStatus.WITHDRAWN,
            source="user",
        )
    )

    assert submitted.submitted_at == NOW + timedelta(hours=1)
    assert interview.submitted_at == submitted.submitted_at
    assert direct_interview.submitted_at == NOW + timedelta(hours=2)
    assert withdrawn.submitted_at is None

    clock.value = NOW + timedelta(hours=3)
    closed = application_service.transition_status(
        ApplicationTransitionRequest(
            application_id="application-1",
            to_status=ApplicationStatus.CLOSED,
            source="user",
        )
    )
    assert closed.submitted_at == submitted.submitted_at


def test_timeline_has_stable_time_then_id_order(service_context) -> None:
    job_service, application_service, _, unit_of_work_factory = service_context
    seed_candidate(unit_of_work_factory)
    job_service.save_manual_job(job())
    created = application_service.add_to_application_pool(pool_request())
    same_time = created.last_updated_at + timedelta(hours=1)

    with unit_of_work_factory() as unit_of_work:
        for event_id in ["timeline-b", "timeline-a"]:
            unit_of_work.applications.append_event(
                ApplicationEvent(
                    id=event_id,
                    application_id=created.id,
                    event_type=STATUS_CHANGED,
                    from_status=ApplicationStatus.SHORTLISTED,
                    to_status=ApplicationStatus.PREPARING,
                    source="fixture",
                    occurred_at=same_time,
                )
            )

    timeline = application_service.list_application_events(created.id)
    assert [item.id for item in timeline.items] == [
        "event-001",
        "timeline-a",
        "timeline-b",
    ]


def test_event_failure_rolls_back_initial_creation_and_status_update(
    session_factory,
) -> None:
    unit_of_work_factory = lambda: SqlAlchemyJobApplicationUnitOfWork(session_factory)
    job_service = JobService(unit_of_work_factory)
    service = ApplicationService(
        unit_of_work_factory,
        clock=lambda: NOW,
        event_id_factory=lambda: "shared-event-id",
    )
    seed_candidate(unit_of_work_factory, "candidate-1")
    seed_candidate(unit_of_work_factory, "candidate-2")
    job_service.save_manual_job(job())
    first = service.add_to_application_pool(pool_request())

    with pytest.raises(ApplicationConflictError) as captured:
        service.add_to_application_pool(
            pool_request("application-2", candidate_id="candidate-2")
        )
    assert captured.value.__cause__ is not None
    assert service.get_application("application-2") is None
    assert service.list_applications("candidate-2").items == []

    with pytest.raises(DuplicateEntityError):
        service.transition_status(
            ApplicationTransitionRequest(
                application_id=first.id,
                to_status=ApplicationStatus.PREPARING,
                source="user",
            )
        )
    unchanged = service.get_application(first.id)
    assert unchanged == first
    assert service.list_application_events(first.id).total == 1


def test_job_application_uow_shares_session_recovers_and_commits_once(
    session_factory,
) -> None:
    commit_calls: list[Session] = []

    class CountingSession(Session):
        def commit(self) -> None:
            commit_calls.append(self)
            super().commit()

    engine = session_factory.kw["bind"]
    counting_factory = sessionmaker(
        bind=engine,
        class_=CountingSession,
        autoflush=False,
        expire_on_commit=False,
    )
    unit_of_work = SqlAlchemyJobApplicationUnitOfWork(counting_factory)

    with pytest.raises(RuntimeError, match="触发回滚"):
        with unit_of_work as entered:
            sessions = {
                id(entered.candidates._session),
                id(entered.jobs._session),
                id(entered.applications._session),
                id(entered.resume_versions._session),
            }
            assert len(sessions) == 1
            entered.jobs.add(job("rolled-back-job", fingerprint="rolled-back"))
            raise RuntimeError("触发回滚")

    assert unit_of_work._scope is None
    with unit_of_work as entered:
        assert entered.jobs.get_by_id("rolled-back-job") is None

    commit_calls.clear()
    result = JobService(
        lambda: SqlAlchemyJobApplicationUnitOfWork(counting_factory)
    ).save_manual_job(job("committed-job", fingerprint="committed"))
    assert result.id == "committed-job"
    assert len(commit_calls) == 1

    with unit_of_work as entered:
        assert entered.jobs.get_by_id("committed-job") == result


def test_contract_and_service_architecture_rejects_sensitive_event_details() -> None:
    for details in [
        {"nested": {"cookie": "not-allowed"}},
        {"nested": [{"Authorization": "not-allowed"}]},
        {"API-KEY": "not-allowed"},
    ]:
        with pytest.raises(ValidationError):
            ApplicationTransitionRequest(
                application_id="application-1",
                to_status=ApplicationStatus.PREPARING,
                source="user",
                details=details,
            )

    for contract, payload in [
        (
            AddToApplicationPoolRequest,
            {**pool_request().model_dump(), "source": "   "},
        ),
        (
            ApplicationTransitionRequest,
            {
                "application_id": "application-1",
                "to_status": ApplicationStatus.PREPARING,
                "source": "   ",
            },
        ),
    ]:
        with pytest.raises(ValidationError):
            contract.model_validate(payload)

    with pytest.raises(ValidationError):
        ApplicationTransitionRequest.model_validate(
            {
                "application_id": "application-1",
                "to_status": ApplicationStatus.PREPARING,
                "source": "user",
                "details": ["not-a-dictionary"],
            }
        )

    application_root = Path("job_agent/application")
    paths = [
        path
        for directory in ["services", "contracts", "rules", "ports"]
        for path in (application_root / directory).glob("*.py")
    ]
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(name == "sqlalchemy" or name.startswith("sqlalchemy.") for name in modules)
        assert ".commit(" not in source
        assert ".rollback(" not in source

    for path in Path("job_agent/infrastructure/database/repositories").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert ".commit(" not in source
