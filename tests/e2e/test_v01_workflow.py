"""使用真实 Service 和临时 SQLite 验收 V0.1 核心闭环。"""

from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path

from job_agent.application.contracts import (
    AddToApplicationPoolRequest,
    ApplicationTransitionRequest,
)
from job_agent.application.rules import can_transition
from job_agent.application.services import (
    APPLICATION_CREATED,
    STATUS_CHANGED,
    ApplicationService,
    DashboardQueryService,
    JobService,
    ProfileService,
)
from job_agent.domain import (
    ApplicationStatus,
    BasicInfo,
    CandidateProfile,
    EvidenceVerification,
    JobPosting,
    JobPreference,
    ResumeEvidence,
)
from job_agent.infrastructure.database import (
    SqlAlchemyDashboardReader,
    SqlAlchemyJobApplicationUnitOfWork,
    SqlAlchemyProfileUnitOfWork,
    create_engine_from_url,
    create_session_factory,
    initialize_database,
)
from job_agent.ui.types import ServiceBundle


NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
CANDIDATE_ID = "candidate-e2e"
EVIDENCE_ID = "evidence-e2e"
JOB_ID = "job-e2e"
APPLICATION_ID = "application-e2e"
FINGERPRINT = "fingerprint-e2e-001"


def _build_real_bundle(database_url: str) -> ServiceBundle:
    """为本测试装配真实基础设施，并固定应用时钟和 Event ID。"""

    engine = create_engine_from_url(database_url)
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    profile_uow_factory = lambda: SqlAlchemyProfileUnitOfWork(session_factory)
    application_uow_factory = lambda: SqlAlchemyJobApplicationUnitOfWork(
        session_factory
    )
    event_ids = count(1)

    return ServiceBundle(
        profile=ProfileService(profile_uow_factory, clock=lambda: NOW),
        jobs=JobService(application_uow_factory),
        applications=ApplicationService(
            application_uow_factory,
            clock=lambda: NOW,
            event_id_factory=lambda: f"event-e2e-{next(event_ids):04d}",
        ),
        dashboard=DashboardQueryService(
            SqlAlchemyDashboardReader(session_factory), clock=lambda: NOW
        ),
        close_callback=engine.dispose,
    )


def _create_profile_and_evidence(bundle: ServiceBundle) -> None:
    profile = bundle.profile.create_profile(
        CandidateProfile(
            id=CANDIDATE_ID,
            basic_info=BasicInfo(
                full_name="虚构验收候选人",
                email="candidate-e2e@example.com",
                phone="13800000000",
                city="杭州",
            ),
            preferences=JobPreference(roles=["Python 工程师"]),
            skills=["Python", "SQL"],
            created_at=NOW,
            updated_at=NOW,
        )
    )

    assert isinstance(profile, CandidateProfile)
    assert profile.id == CANDIDATE_ID
    assert profile.basic_info.full_name == "虚构验收候选人"
    assert bundle.profile.get_profile(CANDIDATE_ID) == profile

    evidence = bundle.profile.add_evidence(
        ResumeEvidence(
            id=EVIDENCE_ID,
            candidate_id=CANDIDATE_ID,
            category="project",
            content="完成虚构的服务集成验收项目",
            skills=["Python", "SQL"],
            created_at=NOW,
            updated_at=NOW,
        )
    )
    assert evidence.verification is EvidenceVerification.UNVERIFIED
    assert bundle.profile.get_profile(CANDIDATE_ID) is not None
    assert bundle.profile.list_verified_evidence(CANDIDATE_ID).total == 0

    verified = bundle.profile.verify_evidence(EVIDENCE_ID)
    formal_evidence = bundle.profile.list_verified_evidence(CANDIDATE_ID)
    assert verified.verification is EvidenceVerification.VERIFIED
    assert formal_evidence.total == 1
    assert [item.id for item in formal_evidence.items] == [EVIDENCE_ID]
    assert all(
        item.verification is EvidenceVerification.VERIFIED
        for item in formal_evidence.items
    )


def _save_job(bundle: ServiceBundle) -> None:
    original = bundle.jobs.save_manual_job(
        JobPosting(
            id=JOB_ID,
            company="虚构示例科技",
            title="Python 工程师",
            location="杭州",
            url="https://jobs.example.com/e2e",
            source="manual-test",
            raw_jd="虚构岗位描述，用于本地集成验收。",
            responsibilities=["维护服务"],
            requirements=["熟悉 Python"],
            skills=["Python"],
            deadline=NOW + timedelta(days=5),
            fingerprint=FINGERPRINT,
            discovered_at=NOW,
        )
    )
    assert isinstance(original, JobPosting)
    assert original.id == JOB_ID

    duplicate = bundle.jobs.save_manual_job(
        JobPosting(
            id="job-e2e-different-input-id",
            company="虚构示例科技",
            title="高级 Python 工程师",
            location="杭州",
            url="https://jobs.example.com/e2e",
            source="manual-test",
            raw_jd="更新后的虚构岗位描述。",
            responsibilities=["维护服务", "改进测试"],
            requirements=["熟悉 Python"],
            skills=["Python", "SQL"],
            deadline=NOW + timedelta(days=5),
            fingerprint=FINGERPRINT,
            discovered_at=NOW + timedelta(days=1),
        )
    )
    jobs = bundle.jobs.list_jobs(limit=10)

    assert duplicate.id == JOB_ID
    assert duplicate.fingerprint == FINGERPRINT
    assert duplicate.discovered_at == NOW
    assert duplicate.title == "高级 Python 工程师"
    assert jobs.total == 1
    assert [item.id for item in jobs.items] == [JOB_ID]


def _create_and_advance_application(bundle: ServiceBundle) -> None:
    request = AddToApplicationPoolRequest(
        application_id=APPLICATION_ID,
        candidate_id=CANDIDATE_ID,
        job_id=JOB_ID,
        application_url="https://jobs.example.com/e2e/apply",
        source="e2e-acceptance",
    )
    created = bundle.applications.add_to_application_pool(request)

    assert created.status is ApplicationStatus.SHORTLISTED
    assert created.submitted_at is None
    assert created.last_updated_at == NOW

    previous_status = ApplicationStatus.SHORTLISTED
    changed_records = []
    for target_status in (
        ApplicationStatus.PREPARING,
        ApplicationStatus.READY_TO_APPLY,
    ):
        assert can_transition(previous_status, target_status)
        changed = bundle.applications.transition_status(
            ApplicationTransitionRequest(
                application_id=APPLICATION_ID,
                to_status=target_status,
                source="e2e-acceptance",
                details={"step": target_status.value},
            )
        )
        changed_records.append(changed)
        previous_status = target_status

    assert changed_records[0].status is ApplicationStatus.PREPARING
    assert changed_records[1].status is ApplicationStatus.READY_TO_APPLY
    assert changed_records[0].last_updated_at == NOW + timedelta(microseconds=1)
    assert changed_records[1].last_updated_at == NOW + timedelta(microseconds=2)
    assert changed_records[0].last_updated_at < changed_records[1].last_updated_at
    assert changed_records[1].submitted_at is None

    repeated = bundle.applications.add_to_application_pool(request)
    applications = bundle.applications.list_applications(CANDIDATE_ID)
    timeline = bundle.applications.list_application_events(APPLICATION_ID)

    assert repeated.id == APPLICATION_ID
    assert repeated.status is ApplicationStatus.READY_TO_APPLY
    assert applications.total == 1
    assert timeline.total == 3
    assert [event.event_type for event in timeline.items] == [
        APPLICATION_CREATED,
        STATUS_CHANGED,
        STATUS_CHANGED,
    ]
    assert timeline.items[0].from_status is None
    assert timeline.items[0].to_status is ApplicationStatus.SHORTLISTED
    assert timeline.items[0].source == request.source
    assert timeline.items[0].occurred_at == NOW
    assert timeline.items[1].from_status is ApplicationStatus.SHORTLISTED
    assert timeline.items[1].to_status is ApplicationStatus.PREPARING
    assert timeline.items[1].occurred_at == changed_records[0].last_updated_at
    assert timeline.items[2].from_status is ApplicationStatus.PREPARING
    assert timeline.items[2].to_status is ApplicationStatus.READY_TO_APPLY
    assert timeline.items[2].occurred_at == changed_records[1].last_updated_at
    assert [
        (event.occurred_at, event.id) for event in timeline.items
    ] == sorted((event.occurred_at, event.id) for event in timeline.items)


def _assert_dashboard(bundle: ServiceBundle) -> None:
    summary = bundle.dashboard.get_summary(CANDIDATE_ID)

    assert summary.jobs_added_this_week == 1
    assert summary.evidence_pending_review == 0
    assert summary.applications_pending_submission == 1
    assert summary.applications_submitted == 0
    assert summary.online_assessments == 0
    assert summary.interviews == 0
    assert summary.offers == 0
    assert {event.application_id for event in summary.recent_events} == {
        APPLICATION_ID
    }
    assert [job.id for job in summary.upcoming_jobs] == [JOB_ID]


def test_v01_workflow_persists_across_real_service_bundle_rebuild(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v01-workflow.sqlite3"
    assert not database_path.exists()
    database_url = f"sqlite:///{database_path}"

    first_bundle = _build_real_bundle(database_url)
    try:
        assert first_bundle.profile.get_profile(CANDIDATE_ID) is None
        assert first_bundle.profile.list_evidence_for_review(CANDIDATE_ID).total == 0
        assert first_bundle.jobs.list_jobs().total == 0
        assert first_bundle.applications.list_applications(CANDIDATE_ID).total == 0
        assert first_bundle.applications.list_application_events(APPLICATION_ID).total == 0

        _create_profile_and_evidence(first_bundle)
        _save_job(first_bundle)
        _create_and_advance_application(first_bundle)
        _assert_dashboard(first_bundle)
    finally:
        first_bundle.close()
    del first_bundle

    second_bundle = _build_real_bundle(database_url)
    try:
        profile = second_bundle.profile.get_profile(CANDIDATE_ID)
        assert profile is not None
        assert profile.id == CANDIDATE_ID
        assert profile.basic_info.full_name == "虚构验收候选人"

        evidence = second_bundle.profile.list_verified_evidence(CANDIDATE_ID)
        assert evidence.total == 1
        assert evidence.items[0].id == EVIDENCE_ID
        assert evidence.items[0].verification is EvidenceVerification.VERIFIED

        jobs = second_bundle.jobs.list_jobs()
        assert jobs.total == 1
        assert jobs.items[0].id == JOB_ID
        assert jobs.items[0].fingerprint == FINGERPRINT
        assert jobs.items[0].discovered_at == NOW

        application = second_bundle.applications.get_application(APPLICATION_ID)
        assert application is not None
        assert application.status is ApplicationStatus.READY_TO_APPLY
        assert application.submitted_at is None
        assert application.last_updated_at == NOW + timedelta(microseconds=2)

        timeline = second_bundle.applications.list_application_events(APPLICATION_ID)
        assert timeline.total == 3
        assert [event.event_type for event in timeline.items] == [
            APPLICATION_CREATED,
            STATUS_CHANGED,
            STATUS_CHANGED,
        ]
        assert [event.to_status for event in timeline.items] == [
            ApplicationStatus.SHORTLISTED,
            ApplicationStatus.PREPARING,
            ApplicationStatus.READY_TO_APPLY,
        ]
        assert [
            (event.occurred_at, event.id) for event in timeline.items
        ] == sorted((event.occurred_at, event.id) for event in timeline.items)

        _assert_dashboard(second_bundle)
    finally:
        second_bundle.close()
