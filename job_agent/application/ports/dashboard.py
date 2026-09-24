"""Dashboard 只读查询端口。"""

from datetime import datetime
from typing import Protocol

from job_agent.application.contracts.dashboard import DashboardSummary


class DashboardReader(Protocol):
    """由基础设施层实现的数据库聚合查询。"""

    def fetch_summary(
        self,
        candidate_id: str,
        *,
        week_started_at: datetime,
        now: datetime,
        deadline_ends_at: datetime,
        recent_limit: int,
    ) -> DashboardSummary: ...


__all__ = ["DashboardReader"]
