"""Engine 创建工厂和 SQLite 安全设置。"""

from collections.abc import Mapping

from sqlalchemy import Engine, create_engine, event, text

from job_agent.config import Settings


class DatabaseConfigurationError(ValueError):
    """数据库地址缺失或不受支持。"""


def _validate_database_url(database_url: str) -> None:
    if not database_url or "://" not in database_url:
        raise DatabaseConfigurationError(
            "DATABASE_URL 必须是包含协议的 SQLAlchemy 数据库地址"
        )


def create_engine_from_url(
    database_url: str,
    *,
    connect_args: Mapping[str, object] | None = None,
    echo: bool = False,
) -> Engine:
    """根据显式 URL 创建 Engine；本函数不连接数据库。"""

    _validate_database_url(database_url)
    options: dict[str, object] = {"echo": echo, "future": True}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False, **(connect_args or {})}
    elif connect_args:
        options["connect_args"] = dict(connect_args)

    engine = create_engine(database_url, **options)
    if engine.url.get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

    return engine


def create_engine_from_settings(settings: Settings | None = None, *, echo: bool = False) -> Engine:
    """从现有配置对象创建 Engine。"""

    resolved_settings = settings or Settings.from_env()
    return create_engine_from_url(resolved_settings.database_url, echo=echo)


def sqlite_foreign_keys_enabled(engine: Engine) -> bool:
    """读取 SQLite 外键开关，供测试和诊断使用。"""

    if engine.url.get_backend_name() != "sqlite":
        return True
    with engine.connect() as connection:
        return bool(connection.execute(text("PRAGMA foreign_keys")).scalar())
