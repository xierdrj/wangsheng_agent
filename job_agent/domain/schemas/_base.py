"""领域 Schema 的共用校验基类。"""

from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, field_validator


class DomainModel(BaseModel):
    """默认拒绝未声明字段，避免外部 payload 静默污染领域对象。"""

    model_config = ConfigDict(extra="forbid")


def validate_non_blank(value: str) -> str:
    """拒绝只包含空白字符的字符串。"""

    if not value.strip():
        raise ValueError("字符串不能为空")
    return value


def validate_aware_datetime(value: datetime) -> datetime:
    """所有领域时间必须带有效时区。"""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("时间必须包含有效时区")
    return value


def validate_optional_aware_datetime(value: datetime | None) -> datetime | None:
    """校验可选时间；空值保持为空。"""

    if value is None:
        return None
    return validate_aware_datetime(value)


def validate_http_url(value: str) -> str:
    """校验 URL 为 HTTP 或 HTTPS，并保留字符串类型。"""

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL 必须是包含主机名的 HTTP(S) 地址")
    return value


class TimestampedModel(DomainModel):
    """包含创建和更新时间的 Schema 基类。"""

    created_at: datetime
    updated_at: datetime

    _created_at_timezone = field_validator("created_at")(validate_aware_datetime)
    _updated_at_timezone = field_validator("updated_at")(validate_aware_datetime)
