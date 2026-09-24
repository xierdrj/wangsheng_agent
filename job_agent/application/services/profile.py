"""候选人 Profile 与 Evidence 的应用服务。"""

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone

from job_agent.application.contracts.profile import (
    ProfileImportRequest,
    ProfileImportResult,
)
from job_agent.application.ports.repositories import (
    EntityNotFoundError,
    ImmutableFieldError,
    Page,
)
from job_agent.application.ports.unit_of_work import ProfileUnitOfWork
from job_agent.domain import CandidateProfile, EvidenceVerification, ResumeEvidence


Clock = Callable[[], datetime]
UnitOfWorkFactory = Callable[[], ProfileUnitOfWork]


class EvidenceStateError(ValueError):
    """Evidence 状态不允许当前业务操作。"""


def _system_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProfileService:
    """通过 Repository 与事务抽象编排 Profile 业务规则。"""

    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        *,
        clock: Clock = _system_utc_now,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    def create_profile(self, profile: CandidateProfile) -> CandidateProfile:
        """创建 Profile，并由服务端规范化初始时间。"""

        now = self._now()
        normalized = profile.model_copy(update={"created_at": now, "updated_at": now})
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.candidates.add(normalized)

    def get_profile(self, candidate_id: str) -> CandidateProfile | None:
        """按 ID 查询 Profile。"""

        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.candidates.get_by_id(candidate_id)

    def update_profile(
        self, candidate_id: str, profile: CandidateProfile
    ) -> CandidateProfile:
        """完整编辑 Profile，保留身份和创建时间并更新时间。"""

        if profile.id != candidate_id:
            raise ImmutableFieldError("Profile ID 不允许通过编辑修改")
        with self._unit_of_work_factory() as unit_of_work:
            current = unit_of_work.candidates.get_by_id(candidate_id)
            if current is None:
                raise EntityNotFoundError(f"候选人不存在: {candidate_id}")
            normalized = profile.model_copy(
                update={
                    "id": current.id,
                    "created_at": current.created_at,
                    "updated_at": self._next_timestamp(current.updated_at),
                }
            )
            return unit_of_work.candidates.update(normalized)

    def import_structured(
        self, payload: ProfileImportRequest | Mapping[str, object]
    ) -> ProfileImportResult:
        """在单一事务中导入已结构化的 Profile 和 Evidence。"""

        request = ProfileImportRequest.model_validate(payload)
        now = self._now()
        profile = request.profile.model_copy(
            update={"created_at": now, "updated_at": now}
        )
        evidence = [self._new_evidence(item, now) for item in request.evidence]

        with self._unit_of_work_factory() as unit_of_work:
            created_profile = unit_of_work.candidates.add(profile)
            created_evidence = [unit_of_work.evidence.add(item) for item in evidence]
            return ProfileImportResult(
                profile=created_profile,
                evidence=created_evidence,
            )

    def add_evidence(self, evidence: ResumeEvidence) -> ResumeEvidence:
        """新增待验证 Evidence，不允许绕过显式验证流程。"""

        if evidence.verification is not EvidenceVerification.UNVERIFIED:
            raise EvidenceStateError("普通新增 Evidence 必须为 UNVERIFIED")
        with self._unit_of_work_factory() as unit_of_work:
            if unit_of_work.candidates.get_by_id(evidence.candidate_id) is None:
                raise EntityNotFoundError(f"候选人不存在: {evidence.candidate_id}")
            return unit_of_work.evidence.add(self._new_evidence(evidence, self._now()))

    def verify_evidence(self, evidence_id: str) -> ResumeEvidence:
        """显式验证 Evidence；重复验证保持幂等。"""

        with self._unit_of_work_factory() as unit_of_work:
            current = unit_of_work.evidence.get_by_id(evidence_id)
            if current is None:
                raise EntityNotFoundError(f"简历证据不存在: {evidence_id}")
            if current.verification is EvidenceVerification.VERIFIED:
                return current
            if current.verification is not EvidenceVerification.UNVERIFIED:
                raise EvidenceStateError(
                    f"Evidence 状态 {current.verification.value} 不允许验证"
                )
            verified = current.model_copy(
                update={
                    "verification": EvidenceVerification.VERIFIED,
                    "updated_at": self._next_timestamp(current.updated_at),
                }
            )
            return unit_of_work.evidence.update(verified)

    def list_evidence_for_review(
        self, candidate_id: str, *, limit: int = 50, offset: int = 0
    ) -> Page[ResumeEvidence]:
        """分页返回候选人的全部 Evidence 状态，供人工审核。"""

        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.evidence.list_by_candidate(
                candidate_id, limit=limit, offset=offset
            )

    def list_verified_evidence(
        self, candidate_id: str, *, limit: int = 50, offset: int = 0
    ) -> Page[ResumeEvidence]:
        """正式业务查询；调用方无法关闭 VERIFIED 限制。"""

        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.evidence.list_verified_by_candidate(
                candidate_id, limit=limit, offset=offset
            )

    def list_evidence_by_verification(
        self,
        candidate_id: str,
        verification: EvidenceVerification,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[ResumeEvidence]:
        """按核验状态执行数据库级审核查询。"""

        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.evidence.list_by_candidate_and_verification(
                candidate_id,
                verification,
                limit=limit,
                offset=offset,
            )

    def _new_evidence(self, evidence: ResumeEvidence, now: datetime) -> ResumeEvidence:
        return evidence.model_copy(
            update={
                "verification": EvidenceVerification.UNVERIFIED,
                "created_at": now,
                "updated_at": now,
            }
        )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Profile Service Clock 必须返回带时区时间")
        return value.astimezone(timezone.utc)

    def _next_timestamp(self, previous: datetime) -> datetime:
        now = self._now()
        previous_utc = previous.astimezone(timezone.utc)
        if now <= previous_utc:
            return previous_utc + timedelta(microseconds=1)
        return now


__all__ = ["EvidenceStateError", "ProfileService"]
