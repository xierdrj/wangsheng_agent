"""手动结构化岗位的应用服务。"""

from collections.abc import Callable

from job_agent.application.ports import JobApplicationUnitOfWork, Page
from job_agent.domain import JobPosting


UnitOfWorkFactory = Callable[[], JobApplicationUnitOfWork]


class JobService:
    """保存和查询已经结构化的岗位，不生成 fingerprint。"""

    def __init__(self, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def save_manual_job(self, job: JobPosting) -> JobPosting:
        """按调用方提供的 fingerprint 执行幂等 upsert。"""

        if not job.fingerprint.strip():
            raise ValueError("fingerprint 不能为空")
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.jobs.upsert(job)

    def get_job(self, job_id: str) -> JobPosting | None:
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.jobs.get_by_id(job_id)

    def list_jobs(self, *, limit: int = 50, offset: int = 0) -> Page[JobPosting]:
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.jobs.list(limit=limit, offset=offset)


__all__ = ["JobService"]
