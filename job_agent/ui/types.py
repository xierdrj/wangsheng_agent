"""UI 页面使用的应用服务集合。"""

from collections.abc import Callable
from dataclasses import dataclass

from job_agent.application.services import (
    ApplicationService,
    DashboardQueryService,
    JobService,
    ProfileService,
)


@dataclass(frozen=True)
class ServiceBundle:
    """页面只接收应用服务，不接触数据库实现。"""

    profile: ProfileService
    jobs: JobService
    applications: ApplicationService
    dashboard: DashboardQueryService
    close_callback: Callable[[], None] | None = None

    def close(self) -> None:
        if self.close_callback is not None:
            self.close_callback()


__all__ = ["ServiceBundle"]
