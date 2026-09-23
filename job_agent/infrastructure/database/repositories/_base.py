"""SQLAlchemy Repository 共用行为。"""

from collections.abc import Callable, Sequence
from typing import Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from job_agent.application.ports.repositories import (
    DuplicateEntityError,
    EntityNotFoundError,
    InvalidPaginationError,
    Page,
    RepositoryError,
)
from job_agent.infrastructure.database.base import Base


DomainT = TypeVar("DomainT")
OrmT = TypeVar("OrmT", bound=Base)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


def validate_pagination(limit: int, offset: int) -> None:
    """验证所有 Repository 共用的分页边界。"""

    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PAGE_SIZE:
        raise InvalidPaginationError(f"limit 必须是 1 到 {MAX_PAGE_SIZE} 的整数")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise InvalidPaginationError("offset 必须是大于或等于 0 的整数")


class SqlAlchemyRepository(Generic[DomainT, OrmT]):
    """封装一致的 CRUD、分页和异常转换，不管理事务提交。"""

    model: type[OrmT]
    entity_name: str

    def __init__(self, session: Session) -> None:
        self._session = session

    def _to_domain(self, orm: OrmT) -> DomainT:
        raise NotImplementedError

    def _to_orm(self, domain: DomainT, orm: OrmT | None = None) -> OrmT:
        raise NotImplementedError

    def _ordering(self) -> Sequence[object]:
        return (self.model.id.asc(),)

    def _write(self, action: Callable[[], OrmT], *, duplicate_message: str) -> OrmT:
        """使用 SAVEPOINT 隔离约束失败，保持外层事务可控。"""

        try:
            self._ensure_root_transaction()
            with self._session.begin_nested():
                orm = action()
                self._session.flush()
            return orm
        except IntegrityError as exc:
            message = str(exc.orig).lower()
            if "unique constraint" in message or "primary key" in message:
                raise DuplicateEntityError(duplicate_message) from exc
            raise RepositoryError(f"{self.entity_name} 完整性约束校验失败") from exc
        except SQLAlchemyError as exc:
            raise RepositoryError(f"{self.entity_name} 持久化失败") from exc

    def _ensure_root_transaction(self) -> None:
        """在 SAVEPOINT 前建立真实根事务，避免 SQLite 释放首个 SAVEPOINT 即落盘。"""

        if not self._session.in_transaction():
            self._session.begin()
        connection = self._session.connection()
        if connection.dialect.name != "sqlite":
            return
        driver_connection = connection.connection.driver_connection
        if not driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN")

    def add(self, entity: DomainT) -> DomainT:
        def action() -> OrmT:
            orm = self._to_orm(entity)
            self._session.add(orm)
            return orm

        orm = self._write(action, duplicate_message=f"{self.entity_name} 已存在")
        return self._to_domain(orm)

    def get_by_id(self, entity_id: str) -> DomainT | None:
        try:
            orm = self._session.get(self.model, entity_id)
            return None if orm is None else self._to_domain(orm)
        except SQLAlchemyError as exc:
            raise RepositoryError(f"查询 {self.entity_name} 失败") from exc

    def list(self, *, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0) -> Page[DomainT]:
        validate_pagination(limit, offset)
        try:
            total = self._session.scalar(select(func.count()).select_from(self.model)) or 0
            statement: Select[tuple[OrmT]] = (
                select(self.model).order_by(*self._ordering()).limit(limit).offset(offset)
            )
            items = [self._to_domain(item) for item in self._session.scalars(statement)]
            return Page(items=items, total=total, limit=limit, offset=offset)
        except SQLAlchemyError as exc:
            raise RepositoryError(f"分页查询 {self.entity_name} 失败") from exc

    def _existing_for_update(self, entity_id: str) -> OrmT:
        try:
            orm = self._session.get(self.model, entity_id)
        except SQLAlchemyError as exc:
            raise RepositoryError(f"查询待更新 {self.entity_name} 失败") from exc
        if orm is None:
            raise EntityNotFoundError(f"{self.entity_name} 不存在: {entity_id}")
        return orm

    def update(self, entity: DomainT) -> DomainT:
        entity_id = getattr(entity, "id")
        orm = self._existing_for_update(entity_id)
        updated = self._write(
            lambda: self._to_orm(entity, orm),
            duplicate_message=f"更新 {self.entity_name} 违反唯一约束",
        )
        return self._to_domain(updated)

    def delete(self, entity_id: str) -> bool:
        try:
            orm = self._session.get(self.model, entity_id)
            if orm is None:
                return False

            def action() -> OrmT:
                self._session.delete(orm)
                return orm

            self._write(action, duplicate_message=f"删除 {self.entity_name} 违反约束")
            return True
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            raise RepositoryError(f"删除 {self.entity_name} 失败") from exc

    def _scalar(self, statement: Select[tuple[OrmT]], *, action: str) -> OrmT | None:
        try:
            return self._session.scalar(statement)
        except SQLAlchemyError as exc:
            raise RepositoryError(f"{action} {self.entity_name} 失败") from exc
