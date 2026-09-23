"""Application Service 的输入契约。"""

from pydantic import Field, field_validator

from job_agent.domain import ApplicationStatus
from job_agent.domain.schemas._base import (
    DomainModel,
    validate_http_url,
    validate_non_blank,
)


_SENSITIVE_DETAIL_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
}


def _contains_sensitive_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in _SENSITIVE_DETAIL_KEYS or _contains_sensitive_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


class AddToApplicationPoolRequest(DomainModel):
    """将已保存岗位加入候选人待投池的请求。"""

    application_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    application_url: str = Field(min_length=1)
    resume_version_id: str | None = Field(default=None, min_length=1)
    source: str = Field(min_length=1)

    _url_is_http = field_validator("application_url")(validate_http_url)
    _source_not_blank = field_validator("source")(validate_non_blank)


class ApplicationTransitionRequest(DomainModel):
    """通过普通状态接口推进投递状态的请求。"""

    application_id: str = Field(min_length=1)
    to_status: ApplicationStatus
    source: str = Field(min_length=1)
    details: dict[str, object] = Field(default_factory=dict)

    _source_not_blank = field_validator("source")(validate_non_blank)

    @field_validator("details")
    @classmethod
    def details_must_not_contain_credentials(
        cls, value: dict[str, object]
    ) -> dict[str, object]:
        if _contains_sensitive_key(value):
            raise ValueError("Event details 不得包含密钥、Cookie 或认证信息")
        return value


__all__ = ["AddToApplicationPoolRequest", "ApplicationTransitionRequest"]
