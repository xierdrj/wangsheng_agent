"""领域层枚举与 Schema。"""

from job_agent.domain.enums import ApplicationStatus, EvidenceVerification, ReviewDecision
from job_agent.domain.schemas import (
    ApplicationAnswer,
    ApplicationEvent,
    ApplicationRecord,
    BasicInfo,
    CandidateProfile,
    Education,
    Experience,
    FormField,
    JobPosting,
    JobPreference,
    MatchDimension,
    MatchResult,
    ResumeEvidence,
    ResumeVersion,
)

__all__ = [
    "ApplicationStatus",
    "EvidenceVerification",
    "ReviewDecision",
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
