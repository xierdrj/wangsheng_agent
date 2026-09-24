"""不依赖 Streamlit 的表单转换、展示和状态选项函数。"""

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import re
from typing import TypeVar
from urllib.parse import parse_qsl, urlsplit, urlunsplit
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from job_agent.application.rules import can_transition
from job_agent.domain import (
    ApplicationStatus,
    BasicInfo,
    CandidateProfile,
    Education,
    Experience,
    JobPosting,
    JobPreference,
)


ModelT = TypeVar("ModelT", bound=BaseModel)
LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
_SENSITIVE_REASON_PATTERN = re.compile(
    r"(?i)(api[_-]?key|token|cookie|password|authorization|client[_-]?secret)\s*[:=]"
)
_SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "client_secret",
    "cookie",
    "credential",
    "credentials",
    "password",
    "refresh_token",
    "secret",
    "session_cookie",
    "token",
}
_SENSITIVE_URL_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "refresh_token",
    "secret",
    "token",
}


def parse_lines(value: str) -> list[str]:
    """按换行或逗号解析列表并去除空项。"""

    return [item.strip() for item in re.split(r"[,，\n]", value) if item.strip()]


def parse_optional_datetime(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("日期时间必须包含时区，例如 +08:00")
    return parsed.astimezone(timezone.utc)


def parse_model_list(value: str, model_type: type[ModelT]) -> list[ModelT]:
    """严格解析 JSON 数组中的嵌套 Pydantic 对象。"""

    parsed = json.loads(value or "[]")
    if not isinstance(parsed, list):
        raise ValueError("嵌套数据必须是 JSON 数组")
    return [model_type.model_validate(item) for item in parsed]


def mask_phone(value: str) -> str:
    digits = value.strip()
    if len(digits) <= 4:
        return "*" * len(digits)
    return f"{digits[:3]}{'*' * max(4, len(digits) - 7)}{digits[-4:]}"


def mask_email(value: str) -> str:
    local, separator, domain = value.partition("@")
    if not separator:
        return "***"
    visible = local[:1] if local else ""
    return f"{visible}***@{domain}"


def safe_profile_view(profile: CandidateProfile) -> dict[str, object]:
    data = profile.model_dump(mode="json")
    basic_info = dict(data["basic_info"])
    basic_info["phone"] = mask_phone(profile.basic_info.phone)
    basic_info["email"] = mask_email(str(profile.basic_info.email))
    basic_info["sensitive_profile_id"] = (
        "[已设置]" if profile.basic_info.sensitive_profile_id else None
    )
    data["basic_info"] = basic_info
    return data


def build_candidate_profile(
    values: Mapping[str, object],
    *,
    current: CandidateProfile | None,
    now: datetime,
) -> CandidateProfile:
    """将 UI 草稿转换为完整 CandidateProfile，时间仅作为 Service 输入占位。"""

    email_input = str(values.get("email", "")).strip()
    email = email_input or (str(current.basic_info.email) if current else "")
    phone_input = str(values.get("phone", "")).strip()
    phone = phone_input or (current.basic_info.phone if current else "")
    return CandidateProfile(
        id=str(values["candidate_id"]).strip(),
        basic_info=BasicInfo(
            full_name=str(values["full_name"]).strip(),
            email=email,
            phone=phone,
            city=str(values.get("city", "")).strip() or None,
            sensitive_profile_id=(
                current.basic_info.sensitive_profile_id if current else None
            ),
        ),
        education=parse_model_list(str(values.get("education_json", "[]")), Education),
        internships=parse_model_list(
            str(values.get("internships_json", "[]")), Experience
        ),
        projects=parse_model_list(str(values.get("projects_json", "[]")), Experience),
        skills=parse_lines(str(values.get("skills", ""))),
        awards=parse_lines(str(values.get("awards", ""))),
        preferences=JobPreference(
            roles=parse_lines(str(values.get("roles", ""))),
            locations=parse_lines(str(values.get("locations", ""))),
            industries=parse_lines(str(values.get("industries", ""))),
            graduation_year=(
                int(str(values["graduation_year"]).strip())
                if str(values.get("graduation_year", "")).strip()
                else None
            ),
            salary_expectation=str(values.get("salary_expectation", "")).strip()
            or None,
            excluded_companies=parse_lines(
                str(values.get("excluded_companies", ""))
            ),
            accepts_travel=bool(values.get("accepts_travel", False)),
            accepts_relocation=bool(values.get("accepts_relocation", False)),
        ),
        created_at=current.created_at if current else now,
        updated_at=current.updated_at if current else now,
    )


def build_job_posting(values: Mapping[str, object], *, now: datetime) -> JobPosting:
    url = str(values["url"]).strip()
    if url_contains_sensitive_data(url):
        raise ValueError("岗位 URL 不得包含认证信息")
    return JobPosting(
        id=str(values["id"]).strip(),
        external_job_id=str(values.get("external_job_id", "")).strip() or None,
        company=str(values["company"]).strip(),
        title=str(values["title"]).strip(),
        location=str(values.get("location", "")).strip() or None,
        url=url,
        source=str(values["source"]).strip(),
        raw_jd=str(values["raw_jd"]).strip(),
        responsibilities=parse_lines(str(values.get("responsibilities", ""))),
        requirements=parse_lines(str(values.get("requirements", ""))),
        preferred_qualifications=parse_lines(
            str(values.get("preferred_qualifications", ""))
        ),
        skills=parse_lines(str(values.get("skills", ""))),
        education_requirement=str(values.get("education_requirement", "")).strip()
        or None,
        graduation_requirement=str(values.get("graduation_requirement", "")).strip()
        or None,
        experience_requirement=str(values.get("experience_requirement", "")).strip()
        or None,
        deadline=parse_optional_datetime(str(values.get("deadline", ""))),
        fingerprint=str(values["fingerprint"]).strip(),
        discovered_at=now.astimezone(timezone.utc),
    )


def allowed_target_statuses(current: ApplicationStatus) -> list[ApplicationStatus]:
    """直接复用 T006 规则，只展示会产生真实变化的合法目标。"""

    return [
        status
        for status in ApplicationStatus
        if status is not current and can_transition(current, status)
    ]


def make_application_id(candidate_id: str, job_id: str) -> str:
    """为同一 candidate/job 生成稳定 UI 幂等键。"""

    return str(uuid5(NAMESPACE_URL, f"job-agent:{candidate_id}:{job_id}"))


def reason_is_safe(value: str) -> bool:
    return _SENSITIVE_REASON_PATTERN.search(value) is None


def url_contains_sensitive_data(value: str) -> bool:
    parsed = urlsplit(value)
    if parsed.username or parsed.password:
        return True
    query_keys = {
        key.strip().lower().replace("-", "_")
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
    }
    return bool(query_keys & _SENSITIVE_URL_KEYS)


def safe_display_url(value: str) -> str:
    """展示 URL 时去除用户信息、查询参数和 fragment。"""

    parsed = urlsplit(value)
    hostname = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port:
        hostname = f"{hostname}:{port}"
    return urlunsplit((parsed.scheme, hostname, parsed.path, "", ""))


def safe_source_name(value: str | None) -> str:
    if not value:
        return "未记录"
    name = value.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return name if name not in {"", ".", ".."} else "未记录"


def safe_event_details(value: object) -> object:
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for key, nested in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            result[str(key)] = (
                "[已脱敏]"
                if normalized in _SENSITIVE_KEYS
                else safe_event_details(nested)
            )
        return result
    if isinstance(value, (list, tuple)):
        return [safe_event_details(item) for item in value]
    return value


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.astimezone(LOCAL_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S Asia/Shanghai")


def model_list_json(items: list[BaseModel]) -> str:
    return json.dumps(
        [item.model_dump(mode="json") for item in items],
        ensure_ascii=False,
        indent=2,
    )


__all__ = [
    "allowed_target_statuses",
    "build_candidate_profile",
    "build_job_posting",
    "format_datetime",
    "make_application_id",
    "mask_email",
    "mask_phone",
    "model_list_json",
    "parse_lines",
    "parse_model_list",
    "parse_optional_datetime",
    "reason_is_safe",
    "safe_display_url",
    "safe_event_details",
    "safe_profile_view",
    "safe_source_name",
    "url_contains_sensitive_data",
]
