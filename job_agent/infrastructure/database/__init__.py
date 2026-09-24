"""数据库基础设施的稳定导出。"""

from job_agent.infrastructure.database.engine import (
    DatabaseConfigurationError,
    create_engine_from_settings,
    create_engine_from_url,
    sqlite_foreign_keys_enabled,
)
from job_agent.infrastructure.database.base import Base
from job_agent.infrastructure.database.init import initialize_database
from job_agent.infrastructure.database.session import create_session_factory, session_scope
from job_agent.infrastructure.database.unit_of_work import (
    SqlAlchemyJobApplicationUnitOfWork,
    SqlAlchemyProfileUnitOfWork,
)
from job_agent.infrastructure.database.dashboard import SqlAlchemyDashboardReader

__all__ = [
    "Base",
    "DatabaseConfigurationError",
    "SqlAlchemyJobApplicationUnitOfWork",
    "SqlAlchemyProfileUnitOfWork",
    "SqlAlchemyDashboardReader",
    "create_engine_from_settings",
    "create_engine_from_url",
    "create_session_factory",
    "initialize_database",
    "session_scope",
    "sqlite_foreign_keys_enabled",
]
