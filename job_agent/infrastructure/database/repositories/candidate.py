"""候选人 Repository 的 SQLAlchemy 实现。"""

from job_agent.domain.schemas import CandidateProfile
from job_agent.infrastructure.database.mappers import candidate_to_domain, candidate_to_orm
from job_agent.infrastructure.database.models import CandidateORM
from job_agent.infrastructure.database.repositories._base import SqlAlchemyRepository


class SqlAlchemyCandidateRepository(SqlAlchemyRepository[CandidateProfile, CandidateORM]):
    model = CandidateORM
    entity_name = "候选人"

    def _to_domain(self, orm: CandidateORM) -> CandidateProfile:
        return candidate_to_domain(orm)

    def _to_orm(
        self, domain: CandidateProfile, orm: CandidateORM | None = None
    ) -> CandidateORM:
        if orm is not None:
            domain = domain.model_copy(update={"created_at": orm.created_at})
        return candidate_to_orm(domain, orm)

    def _ordering(self):
        return (CandidateORM.created_at.asc(), CandidateORM.id.asc())
