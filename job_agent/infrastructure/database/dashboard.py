"""Dashboard 数据库聚合查询实现。"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from job_agent.application.contracts import DashboardSummary
from job_agent.domain import ApplicationStatus, EvidenceVerification
from job_agent.infrastructure.database.mappers import (
    application_event_to_domain,
    job_to_domain,
)
from job_agent.infrastructure.database.models import (
    ApplicationEventORM,
    ApplicationORM,
    CandidateORM,
    JobORM,
    ResumeEvidenceORM,
)
from job_agent.infrastructure.database.session import session_scope


_PENDING_SUBMISSION_STATUSES = (
    ApplicationStatus.SHORTLISTED,
    ApplicationStatus.PREPARING,
    ApplicationStatus.READY_TO_APPLY,
)


class SqlAlchemyDashboardReader:
    """使用完整数据库聚合而非首页内存统计。"""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def fetch_summary(
        self,
        candidate_id: str,
        *,
        week_started_at: datetime,
        now: datetime,
        deadline_ends_at: datetime,
        recent_limit: int,
    ) -> DashboardSummary:
        with session_scope(self._session_factory) as session:
            candidate_exists = session.scalar(
                select(func.count())
                .select_from(CandidateORM)
                .where(CandidateORM.id == candidate_id)
            )
            if not candidate_exists:
                return DashboardSummary(
                    jobs_added_this_week=0,
                    evidence_pending_review=0,
                    applications_pending_submission=0,
                    applications_submitted=0,
                    online_assessments=0,
                    interviews=0,
                    offers=0,
                )

            jobs_added = self._count(
                session,
                select(func.count())
                .select_from(JobORM)
                .where(JobORM.discovered_at >= week_started_at),
            )
            evidence_pending = self._count(
                session,
                select(func.count())
                .select_from(ResumeEvidenceORM)
                .where(
                    ResumeEvidenceORM.candidate_id == candidate_id,
                    ResumeEvidenceORM.verification
                    == EvidenceVerification.UNVERIFIED,
                ),
            )
            pending_submission = self._application_count(
                session, candidate_id, _PENDING_SUBMISSION_STATUSES
            )
            submitted = self._application_count(
                session, candidate_id, (ApplicationStatus.SUBMITTED,)
            )
            online_assessments = self._application_count(
                session, candidate_id, (ApplicationStatus.ONLINE_ASSESSMENT,)
            )
            interviews = self._application_count(
                session, candidate_id, (ApplicationStatus.INTERVIEW,)
            )
            offers = self._application_count(
                session, candidate_id, (ApplicationStatus.OFFER,)
            )

            recent_statement = (
                select(ApplicationEventORM)
                .join(
                    ApplicationORM,
                    ApplicationEventORM.application_id == ApplicationORM.id,
                )
                .where(ApplicationORM.candidate_id == candidate_id)
                .order_by(
                    ApplicationEventORM.occurred_at.desc(),
                    ApplicationEventORM.id.desc(),
                )
                .limit(recent_limit)
            )
            recent_events = [
                application_event_to_domain(item)
                for item in session.scalars(recent_statement)
            ]

            upcoming_statement = (
                select(JobORM)
                .where(
                    JobORM.deadline.is_not(None),
                    JobORM.deadline >= now,
                    JobORM.deadline <= deadline_ends_at,
                )
                .order_by(JobORM.deadline.asc(), JobORM.id.asc())
            )
            upcoming_jobs = [
                job_to_domain(item) for item in session.scalars(upcoming_statement)
            ]

            return DashboardSummary(
                jobs_added_this_week=jobs_added,
                evidence_pending_review=evidence_pending,
                applications_pending_submission=pending_submission,
                applications_submitted=submitted,
                online_assessments=online_assessments,
                interviews=interviews,
                offers=offers,
                recent_events=recent_events,
                upcoming_jobs=upcoming_jobs,
            )

    @staticmethod
    def _count(session: Session, statement: object) -> int:
        return int(session.scalar(statement) or 0)

    def _application_count(
        self,
        session: Session,
        candidate_id: str,
        statuses: tuple[ApplicationStatus, ...],
    ) -> int:
        return self._count(
            session,
            select(func.count())
            .select_from(ApplicationORM)
            .where(
                ApplicationORM.candidate_id == candidate_id,
                ApplicationORM.status.in_(statuses),
            ),
        )


__all__ = ["SqlAlchemyDashboardReader"]
