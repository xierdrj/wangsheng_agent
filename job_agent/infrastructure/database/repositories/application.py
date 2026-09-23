"""投递聚合 Repository 的 SQLAlchemy 实现。"""

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from job_agent.application.ports.repositories import ImmutableFieldError, Page, RepositoryError
from job_agent.domain.schemas import ApplicationAnswer, ApplicationEvent, ApplicationRecord
from job_agent.infrastructure.database.mappers import (
    application_answer_to_domain,
    application_answer_to_orm,
    application_event_to_domain,
    application_event_to_orm,
    application_to_domain,
    application_to_orm,
)
from job_agent.infrastructure.database.models import (
    ApplicationAnswerORM,
    ApplicationEventORM,
    ApplicationORM,
)
from job_agent.infrastructure.database.repositories._base import (
    SqlAlchemyRepository,
    validate_pagination,
)


class SqlAlchemyApplicationRepository(
    SqlAlchemyRepository[ApplicationRecord, ApplicationORM]
):
    model = ApplicationORM
    entity_name = "投递记录"

    def _to_domain(self, orm: ApplicationORM) -> ApplicationRecord:
        return application_to_domain(orm)

    def _to_orm(
        self, domain: ApplicationRecord, orm: ApplicationORM | None = None
    ) -> ApplicationORM:
        if orm is not None:
            if (domain.candidate_id, domain.job_id) != (orm.candidate_id, orm.job_id):
                raise ImmutableFieldError("投递记录 candidate_id 和 job_id 不允许修改")
            domain = domain.model_copy(
                update={"id": orm.id, "candidate_id": orm.candidate_id, "job_id": orm.job_id}
            )
        return application_to_orm(domain, orm)

    def _ordering(self):
        return (ApplicationORM.last_updated_at.asc(), ApplicationORM.id.asc())

    def upsert(self, entity: ApplicationRecord) -> ApplicationRecord:
        orm = self._scalar(
            select(ApplicationORM).where(
                ApplicationORM.candidate_id == entity.candidate_id,
                ApplicationORM.job_id == entity.job_id,
            ),
            action="按候选人和岗位查询",
        )
        if orm is None:
            return self.add(entity)
        updated = self._write(
            lambda: self._to_orm(entity, orm),
            duplicate_message="投递记录 upsert 违反唯一约束",
        )
        return self._to_domain(updated)

    def add_answer(self, entity: ApplicationAnswer) -> ApplicationAnswer:
        def action() -> ApplicationAnswerORM:
            orm = application_answer_to_orm(entity)
            self._session.add(orm)
            return orm

        orm = self._write(action, duplicate_message="网申答案已存在")
        return application_answer_to_domain(orm)

    def list_answers(
        self, application_id: str, *, limit: int = 50, offset: int = 0
    ) -> Page[ApplicationAnswer]:
        validate_pagination(limit, offset)
        try:
            total = self._session.scalar(
                select(func.count())
                .select_from(ApplicationAnswerORM)
                .where(ApplicationAnswerORM.application_id == application_id)
            ) or 0
            statement = (
                select(ApplicationAnswerORM)
                .where(ApplicationAnswerORM.application_id == application_id)
                .order_by(ApplicationAnswerORM.created_at.asc(), ApplicationAnswerORM.id.asc())
                .limit(limit)
                .offset(offset)
            )
            items = [
                application_answer_to_domain(item) for item in self._session.scalars(statement)
            ]
            return Page(items=items, total=total, limit=limit, offset=offset)
        except SQLAlchemyError as exc:
            raise RepositoryError("查询网申答案失败") from exc

    def append_event(self, entity: ApplicationEvent) -> ApplicationEvent:
        def action() -> ApplicationEventORM:
            orm = application_event_to_orm(entity)
            self._session.add(orm)
            return orm

        orm = self._write(action, duplicate_message="投递事件已存在")
        return application_event_to_domain(orm)

    def list_events(
        self, application_id: str, *, limit: int = 50, offset: int = 0
    ) -> Page[ApplicationEvent]:
        validate_pagination(limit, offset)
        try:
            total = self._session.scalar(
                select(func.count())
                .select_from(ApplicationEventORM)
                .where(ApplicationEventORM.application_id == application_id)
            ) or 0
            statement = (
                select(ApplicationEventORM)
                .where(ApplicationEventORM.application_id == application_id)
                .order_by(ApplicationEventORM.occurred_at.asc(), ApplicationEventORM.id.asc())
                .limit(limit)
                .offset(offset)
            )
            items = [application_event_to_domain(item) for item in self._session.scalars(statement)]
            return Page(items=items, total=total, limit=limit, offset=offset)
        except SQLAlchemyError as exc:
            raise RepositoryError("查询投递事件失败") from exc
