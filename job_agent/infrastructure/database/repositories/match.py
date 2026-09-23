"""岗位匹配 Repository 的 SQLAlchemy 实现。"""

from sqlalchemy import select

from job_agent.application.ports.repositories import ImmutableFieldError
from job_agent.domain.schemas import MatchResult
from job_agent.infrastructure.database.mappers import match_to_domain, match_to_orm
from job_agent.infrastructure.database.models import JobMatchORM
from job_agent.infrastructure.database.repositories._base import SqlAlchemyRepository


class SqlAlchemyMatchRepository(SqlAlchemyRepository[MatchResult, JobMatchORM]):
    model = JobMatchORM
    entity_name = "匹配结果"

    def _to_domain(self, orm: JobMatchORM) -> MatchResult:
        return match_to_domain(orm)

    def _to_orm(self, domain: MatchResult, orm: JobMatchORM | None = None) -> JobMatchORM:
        if orm is not None:
            if (domain.candidate_id, domain.job_id) != (orm.candidate_id, orm.job_id):
                raise ImmutableFieldError("匹配结果 candidate_id 和 job_id 不允许修改")
            domain = domain.model_copy(
                update={
                    "id": orm.id,
                    "candidate_id": orm.candidate_id,
                    "job_id": orm.job_id,
                    "created_at": orm.created_at,
                }
            )
        return match_to_orm(domain, orm)

    def _ordering(self):
        return (JobMatchORM.created_at.asc(), JobMatchORM.id.asc())

    def upsert(self, entity: MatchResult) -> MatchResult:
        orm = self._scalar(
            select(JobMatchORM).where(
                JobMatchORM.candidate_id == entity.candidate_id,
                JobMatchORM.job_id == entity.job_id,
            ),
            action="按候选人和岗位查询",
        )
        if orm is None:
            return self.add(entity)
        updated = self._write(
            lambda: self._to_orm(entity, orm),
            duplicate_message="匹配结果 upsert 违反唯一约束",
        )
        return self._to_domain(updated)
