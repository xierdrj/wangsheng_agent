"""最小启动入口。"""

import sys

from job_agent.config import Settings


def main() -> None:
    """加载配置并输出可审计的启动信息。"""

    settings = Settings.from_env()
    settings.ensure_runtime_directories()
    # Windows 默认代码页可能不是 UTF-8；入口显式使用 UTF-8，避免中文被替换成乱码。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    print(f"job_agent 已启动: env={settings.app_env}, dry_run={settings.browser_dry_run}")
