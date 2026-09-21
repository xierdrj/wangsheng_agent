"""简历版本和网申答案 Schema。"""

from datetime import datetime

from pydantic import Field, field_validator

from job_agent.domain.schemas._base import DomainModel, validate_aware_datetime

# ApplicationAnswer 在 application 模块定义，这里保留兼容导出路径。
from job_agent.domain.schemas.application import ApplicationAnswer

__all__ = ["ApplicationAnswer", "ResumeVersion"]


class ResumeVersion(DomainModel):
    id: str
    candidate_id: str
    job_id: str
    base_resume_id: str
    content: dict[str, object]
    source_evidence_ids: list[str] = Field(default_factory=list)
    file_path: str | None = None
    content_hash: str = Field(min_length=1)
    created_at: datetime

    _created_at_timezone = field_validator("created_at")(validate_aware_datetime)
