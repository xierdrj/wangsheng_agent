"""显式数据库初始化入口。"""

from sqlalchemy import Engine

from job_agent.infrastructure.database.base import Base
from job_agent.infrastructure.database.models import *  # noqa: F401,F403


def initialize_database(engine: Engine) -> None:
    """创建当前 metadata 定义的表；导入模块不会自动调用。"""

    Base.metadata.create_all(engine)
