"""供测试和离线开发使用的确定性基础设施替身。"""

from job_agent.infrastructure.fakes.jd_parser import (
    FakeJDParser,
    FakeJDParserNotConfiguredError,
    load_jd_parser_fixture,
)

__all__ = [
    "FakeJDParser",
    "FakeJDParserNotConfiguredError",
    "load_jd_parser_fixture",
]
