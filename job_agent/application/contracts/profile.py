"""Profile Service 的结构化导入契约。"""

from typing import Self

from pydantic import Field, model_validator

from job_agent.domain import CandidateProfile, EvidenceVerification, ResumeEvidence
from job_agent.domain.schemas._base import DomainModel


class ProfileImportRequest(DomainModel):
    """已经结构化并可由 Pydantic 完整校验的候选人资料。"""

    profile: CandidateProfile
    evidence: list[ResumeEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        evidence_ids: set[str] = set()
        for item in self.evidence:
            if item.candidate_id != self.profile.id:
                raise ValueError("导入 Evidence 必须属于同一 Candidate")
            if item.id in evidence_ids:
                raise ValueError(f"导入数据包含重复 Evidence ID: {item.id}")
            if item.verification is not EvidenceVerification.UNVERIFIED:
                raise ValueError("导入 Evidence 必须保持 UNVERIFIED")
            evidence_ids.add(item.id)
        return self


class ProfileImportResult(DomainModel):
    """结构化资料原子导入的结果。"""

    profile: CandidateProfile
    evidence: list[ResumeEvidence] = Field(default_factory=list)


__all__ = ["ProfileImportRequest", "ProfileImportResult"]
