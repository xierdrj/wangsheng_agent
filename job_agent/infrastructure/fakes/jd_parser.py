"""基于显式 Fixture 的确定性 JD Parser Fake。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from job_agent.application.contracts.jd_parser import (
    JDParseRequest,
    JDParserFixture,
    ParsedJD,
)
from job_agent.application.ports.jd_parser import JDParser, JDParserError


class FakeJDParserNotConfiguredError(JDParserError):
    """合法请求没有对应的 Fake Fixture。"""


def load_jd_parser_fixture(path: str | Path) -> JDParserFixture:
    """显式加载并校验一个 JSON Fixture，不在模块导入时访问文件。"""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return JDParserFixture.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
        raise JDParserError("JD Parser Fixture 无法加载或校验") from exc


def _lookup_key(request: JDParseRequest) -> str:
    if request.external_job_id is not None:
        return f"external:{request.external_job_id}"
    digest = hashlib.sha256(request.raw_jd.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


class FakeJDParser:
    """仅按外部 ID 或完整原文摘要精确命中的 Parser Fake。"""

    def __init__(self, fixtures: Iterable[JDParserFixture]) -> None:
        self._fixtures: dict[str, JDParserFixture] = {}
        for fixture in fixtures:
            validated = JDParserFixture.model_validate(fixture.model_dump())
            key = _lookup_key(validated.input)
            if key in self._fixtures:
                raise JDParserError("JD Parser Fake Fixture 存在重复匹配键")
            self._fixtures[key] = validated.model_copy(deep=True)

    def parse(self, request: JDParseRequest) -> ParsedJD:
        """按精确键返回独立输出；不尝试相似、关键词或默认匹配。"""

        if not isinstance(request, JDParseRequest):
            raise TypeError("JDParser.parse 需要已校验的 JDParseRequest")

        key = _lookup_key(request)
        fixture = self._fixtures.get(key)
        if fixture is None:
            raise FakeJDParserNotConfiguredError(
                "JD Parser Fake 未配置与该请求精确匹配的 Fixture"
            )
        if fixture.expected.raw_jd != request.raw_jd:
            raise JDParserError("JD Parser Fixture 原文与请求不一致")

        output = fixture.expected.model_copy(
            deep=True,
            update={
                "source_url": request.source_url,
                "source_name": request.source_name,
                "external_job_id": request.external_job_id,
            },
        )
        validated = ParsedJD.model_validate(output.model_dump())
        if validated.raw_jd != request.raw_jd:
            raise JDParserError("JD Parser 输出原文与请求不一致")
        return validated


__all__ = [
    "FakeJDParser",
    "FakeJDParserNotConfiguredError",
    "load_jd_parser_fixture",
]
