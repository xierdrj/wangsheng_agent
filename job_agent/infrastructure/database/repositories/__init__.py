"""SQLAlchemy Repository 实现的稳定导出。"""

from job_agent.infrastructure.database.repositories.application import (
    SqlAlchemyApplicationRepository,
)
from job_agent.infrastructure.database.repositories.candidate import (
    SqlAlchemyCandidateRepository,
)
from job_agent.infrastructure.database.repositories.evidence import (
    SqlAlchemyResumeEvidenceRepository,
)
from job_agent.infrastructure.database.repositories.job import SqlAlchemyJobRepository
from job_agent.infrastructure.database.repositories.match import SqlAlchemyMatchRepository
from job_agent.infrastructure.database.repositories.resume import (
    SqlAlchemyResumeRepository,
    SqlAlchemyResumeVersionRepository,
)

__all__ = [
    "SqlAlchemyApplicationRepository",
    "SqlAlchemyCandidateRepository",
    "SqlAlchemyJobRepository",
    "SqlAlchemyMatchRepository",
    "SqlAlchemyResumeEvidenceRepository",
    "SqlAlchemyResumeRepository",
    "SqlAlchemyResumeVersionRepository",
]
