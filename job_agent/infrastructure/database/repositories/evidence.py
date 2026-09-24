"""简历证据 Repository 的 SQLAlchemy 实现。"""

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from job_agent.application.ports.repositories import (
    ImmutableFieldError,
    Page,
    RepositoryError,
)
from job_agent.domain import EvidenceVerification
from job_agent.domain.schemas import ResumeEvidence
from job_agent.infrastructure.database.mappers import evidence_to_domain, evidence_to_orm
from job_agent.infrastructure.database.models import ResumeEvidenceORM
from job_agent.infrastructure.database.repositories._base import (
    SqlAlchemyRepository,
    validate_pagination,
)


class SqlAlchemyResumeEvidenceRepository(
    SqlAlchemyRepository[ResumeEvidence, ResumeEvidenceORM]
):
    model = ResumeEvidenceORM
    entity_name = "简历证据"

    def _to_domain(self, orm: ResumeEvidenceORM) -> ResumeEvidence:
        return evidence_to_domain(orm)

    def _to_orm(
        self, domain: ResumeEvidence, orm: ResumeEvidenceORM | None = None
    ) -> ResumeEvidenceORM:
        if orm is not None:
            if domain.candidate_id != orm.candidate_id:
                raise ImmutableFieldError("简历证据 candidate_id 不允许修改")
            domain = domain.model_copy(update={"created_at": orm.created_at})
        return evidence_to_orm(domain, orm)

    def _ordering(self):
        return (ResumeEvidenceORM.created_at.asc(), ResumeEvidenceORM.id.asc())

    def list_by_candidate(
        self, candidate_id: str, *, limit: int = 50, offset: int = 0
    ) -> Page[ResumeEvidence]:
        """分页返回候选人的全部 Evidence，供审核流程使用。"""

        return self._list_by_candidate(
            candidate_id,
            verification=None,
            limit=limit,
            offset=offset,
        )

    def list_verified_by_candidate(
        self, candidate_id: str, *, limit: int = 50, offset: int = 0
    ) -> Page[ResumeEvidence]:
        """在数据库分页前固定筛选 VERIFIED Evidence。"""

        return self._list_by_candidate(
            candidate_id,
            verification=EvidenceVerification.VERIFIED,
            limit=limit,
            offset=offset,
        )

    def list_by_candidate_and_verification(
        self,
        candidate_id: str,
        verification: EvidenceVerification,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[ResumeEvidence]:
        """按指定核验状态在数据库分页前筛选审核数据。"""

        return self._list_by_candidate(
            candidate_id,
            verification=verification,
            limit=limit,
            offset=offset,
        )

    def _list_by_candidate(
        self,
        candidate_id: str,
        *,
        verification: EvidenceVerification | None,
        limit: int,
        offset: int,
    ) -> Page[ResumeEvidence]:
        validate_pagination(limit, offset)
        conditions = [ResumeEvidenceORM.candidate_id == candidate_id]
        if verification is not None:
            conditions.append(ResumeEvidenceORM.verification == verification)
        try:
            total = self._session.scalar(
                select(func.count())
                .select_from(ResumeEvidenceORM)
                .where(*conditions)
            ) or 0
            statement = (
                select(ResumeEvidenceORM)
                .where(*conditions)
                .order_by(*self._ordering())
                .limit(limit)
                .offset(offset)
            )
            items = [
                self._to_domain(item) for item in self._session.scalars(statement)
            ]
            return Page(items=items, total=total, limit=limit, offset=offset)
        except SQLAlchemyError as exc:
            raise RepositoryError("按候选人分页查询简历证据失败") from exc
