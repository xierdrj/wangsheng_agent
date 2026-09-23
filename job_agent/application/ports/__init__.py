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
    "RepositoryError",
    "ResumeEvidenceRepository",
    "ResumeRepository",
    "ResumeRecord",
    "ResumeVersionRepository",
]
