"""岗位 Repository 的 SQLAlchemy 实现。"""

from sqlalchemy import select

from job_agent.application.ports.repositories import ImmutableFieldError
from job_agent.domain.schemas import JobPosting
from job_agent.infrastructure.database.mappers import job_to_domain, job_to_orm
from job_agent.infrastructure.database.models import JobORM
from job_agent.infrastructure.database.repositories._base import SqlAlchemyRepository


class SqlAlchemyJobRepository(SqlAlchemyRepository[JobPosting, JobORM]):
    model = JobORM
    entity_name = "岗位"

    def _to_domain(self, orm: JobORM) -> JobPosting:
        return job_to_domain(orm)

    def _to_orm(self, domain: JobPosting, orm: JobORM | None = None) -> JobORM:
        if orm is not None:
            if domain.fingerprint != orm.fingerprint:
                raise ImmutableFieldError("岗位 fingerprint 不允许修改")
            domain = domain.model_copy(
                update={
                    "id": orm.id,
                    "fingerprint": orm.fingerprint,
                    "discovered_at": orm.discovered_at,
                }
            )
        return job_to_orm(domain, orm)

    def _ordering(self):
        return (JobORM.discovered_at.asc(), JobORM.id.asc())

    def get_by_fingerprint(self, fingerprint: str) -> JobPosting | None:
        orm = self._scalar(
            select(JobORM).where(JobORM.fingerprint == fingerprint),
            action="按 fingerprint 查询",
        )
        return None if orm is None else self._to_domain(orm)

    def upsert(self, entity: JobPosting) -> JobPosting:
        orm = self._scalar(
            select(JobORM).where(JobORM.fingerprint == entity.fingerprint),
            action="按 fingerprint 查询",
        )
        if orm is None:
            return self.add(entity)
        updated = self._write(
            lambda: self._to_orm(entity, orm),
            duplicate_message="岗位 upsert 违反唯一约束",
        )
        return self._to_domain(updated)
