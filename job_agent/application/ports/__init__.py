"""应用层端口。"""

from job_agent.application.ports.dashboard import DashboardReader
from job_agent.application.ports.jd_parser import JDParser, JDParserError
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
from job_agent.application.ports.unit_of_work import (
    JobApplicationUnitOfWork,
    ProfileUnitOfWork,
)

__all__ = [
    "ApplicationRepository",
    "CandidateRepository",
    "DashboardReader",
    "DuplicateEntityError",
    "EntityNotFoundError",
    "InvalidPaginationError",
    "ImmutableFieldError",
    "JobApplicationUnitOfWork",
    "JDParser",
    "JDParserError",
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
