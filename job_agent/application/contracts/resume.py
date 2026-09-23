"""原始简历的临时应用层契约。

T002 尚未定义原始简历的正式领域 Schema，因此 T004 使用此 DTO 连接
Repository 与 T003 的 ``resumes`` 表。正式领域模型形成后，可在保持字段
兼容的前提下替换本契约。
"""

from pydantic import Field

from job_agent.domain.schemas._base import DomainModel


class ResumeRecord(DomainModel):
    """原始简历持久化 DTO，不依赖 SQLAlchemy 或 Session。"""

    id: str
    candidate_id: str
    name: str = Field(min_length=1)
    source_file_path: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)
    parsed_content: dict[str, object] | None = None


__all__ = ["ResumeRecord"]
