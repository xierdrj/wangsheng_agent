"""浏览器表单字段 Schema。"""

from pydantic import Field

from job_agent.domain.schemas._base import DomainModel


class FormField(DomainModel):
    id: str
    label: str | None = None
    field_type: str = Field(min_length=1)
    required: bool = False
    options: list[str] = Field(default_factory=list)
    locator_hint: dict[str, object] = Field(default_factory=dict)
    mapped_source: str | None = None
    proposed_value: str | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    needs_review: bool = False
    sensitive: bool = False
