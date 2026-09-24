"""T007 Dashboard 数据库聚合查询测试。"""

from datetime import datetime, timedelta, timezone

import pytest

from job_agent.application.contracts import (
    AddToApplicationPoolRequest,
    ApplicationTransitionRequest,
)
from job_agent.application.services import (
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


NOW = datetime(2026, 9, 23, 8, 0, tzinfo=timezone.utc)


class EventIds:
    def __init__(self) -> None:
        self.index = 0

    def __call__(self) -> str:
        self.index += 1
        return f"dashboard-event-{self.index:03d}"


@pytest.fixture()
def services(tmp_path):
    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'dashboard.sqlite3'}")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    profile_uow = lambda: SqlAlchemyProfileUnitOfWork(session_factory)
    job_uow = lambda: SqlAlchemyJobApplicationUnitOfWork(session_factory)
    try:
        yield (
            ProfileService(profile_uow, clock=lambda: NOW),
            JobService(job_uow),
            ApplicationService(
                job_uow,
                clock=lambda: NOW,
                event_id_factory=EventIds(),
            ),
            DashboardQueryService(
                SqlAlchemyDashboardReader(session_factory), clock=lambda: NOW
            ),
        )
    finally:
        engine.dispose()


def _profile() -> CandidateProfile:
    return CandidateProfile(
        id="candidate-dashboard",
        basic_info=BasicInfo(
            full_name="脱敏候选人",
            email="dashboard@example.com",
            phone="13800000000",
        ),
        preferences=JobPreference(roles=["Python 工程师"]),
        created_at=NOW,
        updated_at=NOW,
    )


def _job(
    index: int,
    *,
    discovered_at: datetime = NOW,
    deadline: datetime | None = None,
) -> JobPosting:
    return JobPosting(
        id=f"job-dashboard-{index}",
        company="脱敏科技",
        title=f"Python 工程师 {index}",
        url=f"https://jobs.example.com/dashboard-{index}",
        source="manual",
        raw_jd="负责后端服务开发",
        fingerprint=f"dashboard-fingerprint-{index}",
        discovered_at=discovered_at,
        deadline=deadline,
    )


def test_dashboard_counts_full_database_and_stable_recent_data(services) -> None:
    profile_service, job_service, application_service, dashboard_service = services
    profile_service.create_profile(_profile())
    for index in range(2):
        profile_service.add_evidence(
            ResumeEvidence(
                id=f"dashboard-evidence-{index}",
                candidate_id="candidate-dashboard",
                category="project",
                content=f"脱敏事实 {index}",
                verification=EvidenceVerification.UNVERIFIED,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    profile_service.verify_evidence("dashboard-evidence-1")
    unverified_page = profile_service.list_evidence_by_verification(
        "candidate-dashboard",
        EvidenceVerification.UNVERIFIED,
        limit=1,
    )
    verified_page = profile_service.list_evidence_by_verification(
        "candidate-dashboard",
        EvidenceVerification.VERIFIED,
        limit=1,
    )
    assert (unverified_page.total, [item.id for item in unverified_page.items]) == (
        1,
        ["dashboard-evidence-0"],
    )
    assert (verified_page.total, [item.id for item in verified_page.items]) == (
        1,
        ["dashboard-evidence-1"],
    )

    jobs = [
        _job(1, deadline=NOW + timedelta(days=2)),
        _job(2, deadline=NOW + timedelta(days=30)),
        _job(3, discovered_at=NOW - timedelta(days=30)),
        _job(
            4,
            discovered_at=NOW - timedelta(days=30),
            deadline=NOW - timedelta(microseconds=1),
        ),
        _job(
            5,
            discovered_at=NOW - timedelta(days=30),
            deadline=NOW + timedelta(days=14),
        ),
    ]
    for job in jobs:
        job_service.save_manual_job(job)
    for job in jobs[:3]:
        application_service.add_to_application_pool(
            AddToApplicationPoolRequest(
                application_id=f"application-dashboard-{job.id}",
                candidate_id="candidate-dashboard",
                job_id=job.id,
                application_url=job.url,
                source="test",
            )
        )

    application_service.transition_status(
        ApplicationTransitionRequest(
            application_id="application-dashboard-job-dashboard-2",
            to_status=ApplicationStatus.SUBMITTED,
            source="test",
        )
    )
    application_service.transition_status(
        ApplicationTransitionRequest(
            application_id="application-dashboard-job-dashboard-3",
            to_status=ApplicationStatus.ONLINE_ASSESSMENT,
            source="test",
        )
    )

    summary = dashboard_service.get_summary("candidate-dashboard")

    assert summary.jobs_added_this_week == 2
    assert summary.evidence_pending_review == 1
    assert summary.applications_pending_submission == 1
    assert summary.applications_submitted == 1
    assert summary.online_assessments == 1
    assert summary.interviews == 0
    assert summary.offers == 0
    assert [job.id for job in summary.upcoming_jobs] == [
        "job-dashboard-1",
        "job-dashboard-5",
    ]
    assert len(summary.recent_events) == 5
    ordering = [(item.occurred_at, item.id) for item in summary.recent_events]
    assert ordering == sorted(ordering, reverse=True)


def test_dashboard_empty_database_returns_zeroes(services) -> None:
    summary = services[3].get_summary("missing")
    assert summary.jobs_added_this_week == 0
    assert summary.evidence_pending_review == 0
    assert summary.applications_pending_submission == 0
    assert summary.recent_events == []
    assert summary.upcoming_jobs == []


def test_dashboard_missing_candidate_returns_zeroes_even_when_jobs_exist(services) -> None:
    _, job_service, _, dashboard_service = services
    job_service.save_manual_job(_job(1, deadline=NOW + timedelta(days=2)))

    summary = dashboard_service.get_summary("missing")

    assert summary.jobs_added_this_week == 0
    assert summary.evidence_pending_review == 0
    assert summary.applications_pending_submission == 0
    assert summary.applications_submitted == 0
    assert summary.online_assessments == 0
    assert summary.interviews == 0
    assert summary.offers == 0
    assert summary.recent_events == []
    assert summary.upcoming_jobs == []


def test_dashboard_status_groups_cover_all_displayed_states(services) -> None:
    profile_service, job_service, application_service, dashboard_service = services
    profile_service.create_profile(_profile())
    target_statuses = [
        ApplicationStatus.SHORTLISTED,
        ApplicationStatus.PREPARING,
        ApplicationStatus.READY_TO_APPLY,
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.ONLINE_ASSESSMENT,
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.OFFER,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.CLOSED,
    ]
    for index, status in enumerate(target_statuses, start=10):
        job = job_service.save_manual_job(_job(index))
        application_id = f"application-dashboard-{index}"
        application_service.add_to_application_pool(
            AddToApplicationPoolRequest(
                application_id=application_id,
                candidate_id="candidate-dashboard",
                job_id=job.id,
                application_url=job.url,
                source="test",
            )
        )
        if status is not ApplicationStatus.SHORTLISTED:
            application_service.transition_status(
                ApplicationTransitionRequest(
                    application_id=application_id,
                    to_status=status,
                    source="test",
                )
            )

    summary = dashboard_service.get_summary("candidate-dashboard")

    assert summary.applications_pending_submission == 3
    assert summary.applications_submitted == 1
    assert summary.online_assessments == 1
    assert summary.interviews == 1
    assert summary.offers == 1
