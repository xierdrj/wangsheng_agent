"""简历证据 Repository 的 SQLAlchemy 实现。"""

from job_agent.domain.schemas import ResumeEvidence
from job_agent.application.ports.repositories import ImmutableFieldError
from job_agent.infrastructure.database.mappers import evidence_to_domain, evidence_to_orm
from job_agent.infrastructure.database.models import ResumeEvidenceORM
from job_agent.infrastructure.database.repositories._base import SqlAlchemyRepository


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
