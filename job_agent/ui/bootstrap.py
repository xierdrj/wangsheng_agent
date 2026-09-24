"""Streamlit 运行时依赖装配；只有显式调用才连接或初始化数据库。"""

from job_agent.application.services import (
    ApplicationService,
    DashboardQueryService,
    JobService,
    ProfileService,
)
from job_agent.config import Settings
from job_agent.infrastructure.database import (
    SqlAlchemyDashboardReader,
    SqlAlchemyJobApplicationUnitOfWork,
    SqlAlchemyProfileUnitOfWork,
    create_engine_from_settings,
    create_session_factory,
    initialize_database,
)
from job_agent.ui.types import ServiceBundle


def create_service_bundle(settings: Settings) -> ServiceBundle:
    """显式准备运行目录、数据库表和应用服务。"""

    settings.ensure_runtime_directories()
    engine = create_engine_from_settings(settings)
    initialize_database(engine)
    session_factory = create_session_factory(engine)

    profile_uow_factory = lambda: SqlAlchemyProfileUnitOfWork(session_factory)
    job_application_uow_factory = lambda: SqlAlchemyJobApplicationUnitOfWork(
        session_factory
    )
    dashboard_reader = SqlAlchemyDashboardReader(session_factory)

    return ServiceBundle(
        profile=ProfileService(profile_uow_factory),
        jobs=JobService(job_application_uow_factory),
        applications=ApplicationService(job_application_uow_factory),
        dashboard=DashboardQueryService(dashboard_reader),
        close_callback=engine.dispose,
    )


__all__ = ["create_service_bundle"]
