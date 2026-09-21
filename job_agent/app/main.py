"""最小启动入口。"""

from job_agent.config import Settings


def main() -> None:
    """加载配置并输出可审计的启动信息。"""

    settings = Settings.from_env()
    settings.ensure_runtime_directories()
    print(f"job_agent 已启动: env={settings.app_env}, dry_run={settings.browser_dry_run}")

