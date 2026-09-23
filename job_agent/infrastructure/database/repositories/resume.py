"""原始简历与简历版本 Repository 的 SQLAlchemy 实现。"""

from sqlalchemy import select

from job_agent.application.ports.repositories import ImmutableFieldError, ResumeRecord
from job_agent.domain.schemas import ResumeVersion
from job_agent.infrastructure.database.mappers import (
    resume_to_domain,
    resume_to_orm,
    resume_version_to_domain,
    resume_version_to_orm,
)
from job_agent.infrastructure.database.models import ResumeORM, ResumeVersionORM
from job_agent.infrastructure.database.repositories._base import SqlAlchemyRepository


class SqlAlchemyResumeRepository(SqlAlchemyRepository[ResumeRecord, ResumeORM]):
    model = ResumeORM
    entity_name = "原始简历"

    def _to_domain(self, orm: ResumeORM) -> ResumeRecord:
        return resume_to_domain(orm)

    def _to_orm(self, domain: ResumeRecord, orm: ResumeORM | None = None) -> ResumeORM:
        if orm is not None:
            if (domain.candidate_id, domain.content_hash) != (
                orm.candidate_id,
                orm.content_hash,
            ):
                raise ImmutableFieldError("原始简历 candidate_id 和 content_hash 不允许修改")
            domain = domain.model_copy(
                update={
                    "id": orm.id,
                    "candidate_id": orm.candidate_id,
                    "content_hash": orm.content_hash,
                }
            )
        return resume_to_orm(domain, orm)

    def upsert(self, entity: ResumeRecord) -> ResumeRecord:
        orm = self._scalar(
            select(ResumeORM).where(
                ResumeORM.candidate_id == entity.candidate_id,
                ResumeORM.content_hash == entity.content_hash,
            ),
            action="按候选人和内容哈希查询",
        )
        if orm is None:
            return self.add(entity)
        updated = self._write(
            lambda: self._to_orm(entity, orm),
            duplicate_message="原始简历 upsert 违反唯一约束",
        )
        return self._to_domain(updated)


class SqlAlchemyResumeVersionRepository(
    SqlAlchemyRepository[ResumeVersion, ResumeVersionORM]
):
    model = ResumeVersionORM
    entity_name = "简历版本"

    def _to_domain(self, orm: ResumeVersionORM) -> ResumeVersion:
        return resume_version_to_domain(orm)

    def _to_orm(
        self, domain: ResumeVersion, orm: ResumeVersionORM | None = None
    ) -> ResumeVersionORM:
        if orm is not None:
            if (domain.candidate_id, domain.job_id, domain.base_resume_id) != (
                orm.candidate_id,
                orm.job_id,
                orm.base_resume_id,
            ):
                raise ImmutableFieldError(
                    "简历版本 candidate_id、job_id 和 base_resume_id 不允许修改"
                )
            domain = domain.model_copy(
                update={
                    "id": orm.id,
                    "candidate_id": orm.candidate_id,
                    "job_id": orm.job_id,
                    "base_resume_id": orm.base_resume_id,
                    "created_at": orm.created_at,
                }
            )
        return resume_version_to_orm(domain, orm)

    def _ordering(self):
        return (ResumeVersionORM.created_at.asc(), ResumeVersionORM.id.asc())
