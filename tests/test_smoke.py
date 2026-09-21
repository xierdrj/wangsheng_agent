"""T001 工程骨架 smoke test。

使用标准库 ``unittest`` 编写，因此在 pytest 尚未安装的最小环境中也能执行。
"""

import tempfile
import unittest
from pathlib import Path

from job_agent.config import ConfigurationError, Settings


class SettingsSmokeTests(unittest.TestCase):
    def test_package_import_and_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings.from_env(environ={}, env_file=Path(temp_dir) / "missing.env")

        self.assertEqual(settings.app_env, "development")
        self.assertEqual(settings.llm_provider, "fake")
        self.assertTrue(settings.browser_dry_run)


    def test_environment_overrides_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "APP_ENV=file\nBROWSER_DRY_RUN=false\nMAX_DAILY_SUBMISSIONS=3\n",
                encoding="utf-8",
            )

            settings = Settings.from_env(
                environ={"APP_ENV": "test", "BROWSER_DRY_RUN": "true"},
                env_file=env_file,
            )

        self.assertEqual(settings.app_env, "test")
        self.assertTrue(settings.browser_dry_run)
        self.assertEqual(settings.max_daily_submissions, 3)


    def test_non_fake_provider_requires_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ConfigurationError, "LLM_API_KEY"):
                Settings.from_env(
                    environ={"LLM_PROVIDER": "openai"},
                    env_file=Path(temp_dir) / "missing.env",
                )


if __name__ == "__main__":
    unittest.main()
