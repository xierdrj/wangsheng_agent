"""Dashboard 查询返回契约。"""

from pydantic import Field

from job_agent.domain import ApplicationEvent, JobPosting
from job_agent.domain.schemas._base import DomainModel


class DashboardSummary(DomainModel):
    """仅包含数据库可真实计算的 Dashboard 数据。"""

    jobs_added_this_week: int = Field(ge=0)
    evidence_pending_review: int = Field(ge=0)
    applications_pending_submission: int = Field(ge=0)
    applications_submitted: int = Field(ge=0)
    online_assessments: int = Field(ge=0)
    interviews: int = Field(ge=0)
    offers: int = Field(ge=0)
    recent_events: list[ApplicationEvent] = Field(default_factory=list)
    upcoming_jobs: list[JobPosting] = Field(default_factory=list)


__all__ = ["DashboardSummary"]
