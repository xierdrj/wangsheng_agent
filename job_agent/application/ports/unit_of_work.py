"""不依赖数据库实现的事务工作单元契约。"""

from types import TracebackType
from typing import Protocol, Self

from job_agent.application.ports.repositories import (
    CandidateRepository,
    ResumeEvidenceRepository,
)


class ProfileUnitOfWork(Protocol):
    """协调 Profile 与 Evidence Repository 的同一事务。"""

    candidates: CandidateRepository
    evidence: ResumeEvidenceRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


__all__ = ["ProfileUnitOfWork"]
