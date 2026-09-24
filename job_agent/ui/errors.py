"""统一、安全的 UI 错误转换。"""

from dataclasses import dataclass
import re
from uuid import uuid4

from pydantic import ValidationError

from job_agent.application.ports import (
    DuplicateEntityError,
    EntityNotFoundError,
    ImmutableFieldError,
    InvalidPaginationError,
    RepositoryError,
)
from job_agent.application.services import (
    ApplicationConflictError,
    EvidenceStateError,
    InvalidApplicationTransitionError,
)


@dataclass(frozen=True)
class UiError:
    code: str
    message: str
    trace_id: str


_REDACTION_PATTERNS = (
    re.compile(
        r"(?i)(api[_-]?key|token|cookie|password|authorization|secret|credential)"
        r"\s*[:=]\s*\S+"
    ),
    re.compile(r"(?i)\b(?:sqlite|postgresql|mysql)(?:\+\w+)?://\S+"),
)


def redact_text(value: str) -> str:
    """清除常见认证值和数据库连接串，供安全日志或测试使用。"""

    result = value
    for pattern in _REDACTION_PATTERNS:
        result = pattern.sub("[已脱敏]", result)
    return result


def to_ui_error(exc: Exception) -> UiError:
    """将异常映射为固定中文提示，不把底层异常文本回显给用户。"""

    trace_id = uuid4().hex
    if isinstance(exc, ValidationError):
        return UiError("VALIDATION_FAILED", "输入未通过校验，请检查必填项和格式。", trace_id)
    if isinstance(exc, EntityNotFoundError):
        return UiError("NOT_FOUND", "未找到操作所需的数据，请刷新后重试。", trace_id)
    if isinstance(exc, (DuplicateEntityError, ApplicationConflictError)):
        return UiError("CONFLICT", "记录已存在或与现有数据冲突，请核对后重试。", trace_id)
    if isinstance(
        exc,
        (
            EvidenceStateError,
            InvalidApplicationTransitionError,
            ImmutableFieldError,
            InvalidPaginationError,
            ValueError,
        ),
    ):
        return UiError("BUSINESS_RULE_REJECTED", "当前操作不符合业务规则，请检查输入。", trace_id)
    if isinstance(exc, RepositoryError):
        return UiError("DATA_ACCESS_FAILED", "数据暂时无法访问，请稍后重试。", trace_id)
    return UiError("UNEXPECTED_ERROR", "操作未完成，请使用 trace_id 排查。", trace_id)


__all__ = ["UiError", "redact_text", "to_ui_error"]
