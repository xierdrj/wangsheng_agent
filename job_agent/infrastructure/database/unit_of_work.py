"""Profile Service 的 SQLAlchemy 事务适配器。"""

from contextlib import AbstractContextManager
from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from job_agent.infrastructure.database.repositories import (
    SqlAlchemyApplicationRepository,
    SqlAlchemyCandidateRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyResumeEvidenceRepository,
    SqlAlchemyResumeVersionRepository,
)
from job_agent.infrastructure.database.session import session_scope


class SqlAlchemyProfileUnitOfWork:
    """复用 T004 Session 生命周期，让两个 Repository 共享事务。"""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._scope: AbstractContextManager[Session] | None = None
        self.candidates: SqlAlchemyCandidateRepository
        self.evidence: SqlAlchemyResumeEvidenceRepository

    def __enter__(self) -> "SqlAlchemyProfileUnitOfWork":
        if self._scope is not None:
            raise RuntimeError("Unit of Work 不可重复进入")
        self._scope = session_scope(self._session_factory)
        session = self._scope.__enter__()
        self.candidates = SqlAlchemyCandidateRepository(session)
        self.evidence = SqlAlchemyResumeEvidenceRepository(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._scope is None:
            raise RuntimeError("Unit of Work 尚未进入")
        scope = self._scope
        self._scope = None
        return scope.__exit__(exc_type, exc_value, traceback)


class SqlAlchemyJobApplicationUnitOfWork:
    """让岗位、投递、事件和简历版本 Repository 共享同一事务。"""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._scope: AbstractContextManager[Session] | None = None
        self.candidates: SqlAlchemyCandidateRepository
        self.jobs: SqlAlchemyJobRepository
        self.applications: SqlAlchemyApplicationRepository
        self.resume_versions: SqlAlchemyResumeVersionRepository

    def __enter__(self) -> "SqlAlchemyJobApplicationUnitOfWork":
        if self._scope is not None:
            raise RuntimeError("Unit of Work 不可重复进入")
        self._scope = session_scope(self._session_factory)
        session = self._scope.__enter__()
        self.candidates = SqlAlchemyCandidateRepository(session)
        self.jobs = SqlAlchemyJobRepository(session)
        self.applications = SqlAlchemyApplicationRepository(session)
        self.resume_versions = SqlAlchemyResumeVersionRepository(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._scope is None:
            raise RuntimeError("Unit of Work 尚未进入")
        scope = self._scope
        self._scope = None
        return scope.__exit__(exc_type, exc_value, traceback)


__all__ = ["SqlAlchemyJobApplicationUnitOfWork", "SqlAlchemyProfileUnitOfWork"]
