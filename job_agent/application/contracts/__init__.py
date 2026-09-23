"""应用层与领域层之间的持久化契约。"""

from job_agent.application.contracts.profile import (
    ProfileImportRequest,
    ProfileImportResult,
)
from job_agent.application.contracts.resume import ResumeRecord

__all__ = ["ProfileImportRequest", "ProfileImportResult", "ResumeRecord"]
