"""不绑定解析实现的 JD Parser 应用端口。"""

from typing import Protocol, runtime_checkable

from job_agent.application.contracts.jd_parser import JDParseRequest, ParsedJD


class JDParserError(ValueError):
    """JD Parser 执行阶段错误。"""


@runtime_checkable
class JDParser(Protocol):
    """将已校验的原始 JD 解析为中间契约。"""

    def parse(self, request: JDParseRequest) -> ParsedJD: ...


__all__ = ["JDParser", "JDParserError"]
