"""领域 Schema 的稳定导出路径。"""

from job_agent.domain.schemas.application import ApplicationAnswer, ApplicationEvent, ApplicationRecord
from job_agent.domain.schemas.browser import FormField
from job_agent.domain.schemas.candidate import (
    BasicInfo,
    CandidateProfile,
    Education,
    Experience,
    JobPreference,
)
from job_agent.domain.schemas.evidence import ResumeEvidence
from job_agent.domain.schemas.job import JobPosting
from job_agent.domain.schemas.match import MatchDimension, MatchResult
from job_agent.domain.schemas.resume import ResumeVersion

__all__ = [
    "ApplicationAnswer",
    "ApplicationEvent",
    "ApplicationRecord",
    "BasicInfo",
    "CandidateProfile",
    "Education",
    "Experience",
    "FormField",
    "JobPosting",
    "JobPreference",
    "MatchDimension",
    "MatchResult",
    "ResumeEvidence",
    "ResumeVersion",
]
