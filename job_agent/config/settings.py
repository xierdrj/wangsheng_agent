"""应用集中配置及其环境变量加载逻辑。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse


class ConfigurationError(ValueError):
    """配置缺失或配置值不合法。"""


def _read_env_file(path: Path) -> dict[str, str]:
    """读取简单的 KEY=VALUE 文件，不覆盖已有环境变量。"""

    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ConfigurationError(f"配置文件 {path} 第 {line_number} 行缺少 '='")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ConfigurationError(f"配置文件 {path} 第 {line_number} 行的键为空")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def _as_bool(value: str, key: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"配置 {key} 必须是布尔值，收到: {value!r}")


def _as_positive_int(value: str, key: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigurationError(f"配置 {key} 必须是整数，收到: {value!r}") from exc
    if parsed < 1:
        raise ConfigurationError(f"配置 {key} 必须大于 0，收到: {parsed}")
    return parsed


def _validate_llm_base_url(value: str) -> None:
    """校验兼容接口根地址，不回显可能含敏感信息的原始值。"""

    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
    except ValueError as exc:
        raise ConfigurationError("配置 LLM_BASE_URL 必须是绝对 HTTP(S) 地址") from exc
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise ConfigurationError("配置 LLM_BASE_URL 必须是绝对 HTTP(S) 地址")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigurationError("配置 LLM_BASE_URL 不得包含用户信息、查询参数或片段")
    path = parsed.path.rstrip("/")
    if "//" in path:
        raise ConfigurationError("配置 LLM_BASE_URL 路径不得包含双斜线")
    if "chat/completions" in path.casefold():
        raise ConfigurationError("配置 LLM_BASE_URL 必须是 API 根地址")


@dataclass(frozen=True)
class Settings:
    """应用运行配置，值来源优先级为进程环境变量、``.env``、安全默认值。"""

    app_env: str = "development"
    database_url: str = "sqlite:///./data/job_agent.db"
    llm_provider: str = "fake"
    llm_model: str = "unset"
    llm_api_key: str | None = field(default=None, repr=False)
    data_dir: Path = Path("data")
    snapshot_dir: Path = Path("data/snapshots")
    playwright_auth_dir: Path = Path("data/playwright")
    browser_headless: bool = True
    browser_dry_run: bool = True
    log_level: str = "INFO"
    max_daily_submissions: int = 10
    llm_enabled: bool = False
    llm_base_url: str | None = None

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        env_file: str | Path = ".env",
    ) -> "Settings":
        """从配置文件和环境变量构造配置，并在值不合法时给出明确错误。"""

        process_env = dict(os.environ if environ is None else environ)
        file_values = _read_env_file(Path(env_file))

        def get(key: str, default: str | None = None) -> str | None:
            return process_env.get(key, file_values.get(key, default))

        provider = (get("LLM_PROVIDER", "fake") or "fake").strip()
        enabled = _as_bool(get("LLM_ENABLED", "false") or "false", "LLM_ENABLED")
        api_key = (get("LLM_API_KEY") or "").strip() or None
        if provider != "fake" and not api_key:
            raise ConfigurationError(
                "配置 LLM_API_KEY 缺失：非 Fake Provider 必须提供 API 密钥"
            )

        supported_providers = {"fake", "openai_compatible"}
        if provider not in supported_providers:
            raise ConfigurationError("配置 LLM_PROVIDER 不受支持")

        model = (get("LLM_MODEL", "unset") or "unset").strip()
        base_url = (get("LLM_BASE_URL") or "").strip() or None
        if enabled and provider == "openai_compatible":
            if not model or model.casefold() == "unset":
                raise ConfigurationError("配置 LLM_MODEL 缺失")
            if base_url is None:
                raise ConfigurationError("配置 LLM_BASE_URL 缺失")
            _validate_llm_base_url(base_url)

        return cls(
            app_env=(get("APP_ENV", "development") or "development").strip(),
            database_url=(get("DATABASE_URL", cls.database_url) or cls.database_url).strip(),
            llm_enabled=enabled,
            llm_provider=provider,
            llm_model=model,
            llm_api_key=api_key,
            llm_base_url=base_url,
            data_dir=Path(get("DATA_DIR", "./data") or "./data"),
            snapshot_dir=Path(get("SNAPSHOT_DIR", "./data/snapshots") or "./data/snapshots"),
            playwright_auth_dir=Path(
                get("PLAYWRIGHT_AUTH_DIR", "./data/playwright") or "./data/playwright"
            ),
            browser_headless=_as_bool(get("BROWSER_HEADLESS", "true") or "true", "BROWSER_HEADLESS"),
            browser_dry_run=_as_bool(get("BROWSER_DRY_RUN", "true") or "true", "BROWSER_DRY_RUN"),
            log_level=(get("LOG_LEVEL", "INFO") or "INFO").strip().upper(),
            max_daily_submissions=_as_positive_int(
                get("MAX_DAILY_SUBMISSIONS", "10") or "10", "MAX_DAILY_SUBMISSIONS"
            ),
        )

    def ensure_runtime_directories(self) -> None:
        """创建本地运行目录；导入配置时不产生文件系统副作用。"""

        for directory in (self.data_dir, self.snapshot_dir, self.playwright_auth_dir):
            directory.mkdir(parents=True, exist_ok=True)
