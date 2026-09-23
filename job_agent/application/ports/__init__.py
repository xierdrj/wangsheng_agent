"""应用层端口。"""

from job_agent.application.ports.repositories import (
    ApplicationRepository,
    CandidateRepository,
    DuplicateEntityError,
    EntityNotFoundError,
    InvalidPaginationError,
    ImmutableFieldError,
    JobRepository,
    MatchRepository,
    Page,
    RepositoryError,
    ResumeEvidenceRepository,
    ResumeRepository,
    ResumeRecord,
    ResumeVersionRepository,
)
from job_agent.application.ports.unit_of_work import ProfileUnitOfWork

__all__ = [
    "ApplicationRepository",
    "CandidateRepository",
    "DuplicateEntityError",
    "EntityNotFoundError",
    "InvalidPaginationError",
    "ImmutableFieldError",
    "JobRepository",
    "MatchRepository",
    "Page",
    "ProfileUnitOfWork",
    "RepositoryError",
    "ResumeEvidenceRepository",
    "ResumeRepository",
    "ResumeRecord",
    "ResumeVersionRepository",
]
