"""Dashboard 应用查询服务。"""

from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone

from job_agent.application.contracts.dashboard import DashboardSummary
from job_agent.application.ports.dashboard import DashboardReader


Clock = Callable[[], datetime]
UPCOMING_DEADLINE_DAYS = 14
RECENT_EVENT_LIMIT = 10


def _system_utc_now() -> datetime:
    return datetime.now(timezone.utc)


def start_of_week(value: datetime) -> datetime:
    """返回给定 UTC 时间所在周的周一零点。"""

    utc_value = value.astimezone(timezone.utc)
    monday = utc_value.date() - timedelta(days=utc_value.weekday())
    return datetime.combine(monday, time.min, tzinfo=timezone.utc)


class DashboardQueryService:
    """编排 Dashboard 时间窗口，具体统计交给只读端口。"""

    def __init__(
        self,
        reader: DashboardReader,
        *,
        clock: Clock = _system_utc_now,
    ) -> None:
        self._reader = reader
        self._clock = clock

    def get_summary(self, candidate_id: str) -> DashboardSummary:
        now = self._now()
        return self._reader.fetch_summary(
            candidate_id,
            week_started_at=start_of_week(now),
            now=now,
            deadline_ends_at=now + timedelta(days=UPCOMING_DEADLINE_DAYS),
            recent_limit=RECENT_EVENT_LIMIT,
        )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Dashboard Clock 必须返回带时区时间")
        return value.astimezone(timezone.utc)


__all__ = [
    "RECENT_EVENT_LIMIT",
    "UPCOMING_DEADLINE_DAYS",
    "DashboardQueryService",
    "start_of_week",
]
