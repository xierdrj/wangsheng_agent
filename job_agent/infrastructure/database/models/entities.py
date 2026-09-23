"""与领域模型分离的 SQLAlchemy ORM 实体。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Enum as SAEnum, ForeignKey, Index, String, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_agent.domain.enums import ApplicationStatus, EvidenceVerification
from job_agent.infrastructure.database.base import Base


def _enum_type(enum_class: type[Any]) -> SAEnum[Any]:
    return SAEnum(
        enum_class,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda values: [item.value for item in values],
    )


JsonObject = dict[str, Any]


class UTCDateTime(TypeDecorator[datetime]):
    """将带时区 datetime 以 UTC naive 形式存入 SQLite，并在读取时恢复时区。"""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        return dialect.type_descriptor(DateTime(timezone=False))

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("数据库 datetime 必须包含有效时区")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class CandidateORM(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    basic_info_json: Mapped[JsonObject] = mapped_column(JSON, nullable=False)
    preferences_json: Mapped[JsonObject] = mapped_column(JSON, nullable=False)
    education_json: Mapped[list[JsonObject]] = mapped_column(JSON, nullable=False, default=list)
    internships_json: Mapped[list[JsonObject]] = mapped_column(JSON, nullable=False, default=list)
    projects_json: Mapped[list[JsonObject]] = mapped_column(JSON, nullable=False, default=list)
    skills_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    awards_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    resumes: Mapped[list[ResumeORM]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )
    evidence: Mapped[list[ResumeEvidenceORM]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )
    matches: Mapped[list[JobMatchORM]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )
    resume_versions: Mapped[list[ResumeVersionORM]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )
    applications: Mapped[list[ApplicationORM]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )


class ResumeORM(Base):
    __tablename__ = "resumes"
    __table_args__ = (UniqueConstraint("candidate_id", "content_hash", name="uq_resumes_candidate_hash"),)

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    parsed_content_json: Mapped[JsonObject | None] = mapped_column(JSON, nullable=True)

    candidate: Mapped[CandidateORM] = relationship(back_populates="resumes")
    evidence: Mapped[list[ResumeEvidenceORM]] = relationship(back_populates="source_resume")


class ResumeEvidenceORM(Base):
    __tablename__ = "resume_evidence"
    __table_args__ = (Index("ix_resume_evidence_candidate_category", "candidate_id", "category"),)

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    experience_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    skills_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    metrics_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_resume_id: Mapped[str | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    verification: Mapped[EvidenceVerification] = mapped_column(
        _enum_type(EvidenceVerification), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    candidate: Mapped[CandidateORM] = relationship(back_populates="evidence")
    source_resume: Mapped[ResumeORM | None] = relationship(back_populates="evidence")


class JobORM(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    external_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_jd: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_json: Mapped[JsonObject] = mapped_column(JSON, nullable=False, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    deadline: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    matches: Mapped[list[JobMatchORM]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )
    applications: Mapped[list[ApplicationORM]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )


class JobMatchORM(Base):
    __tablename__ = "job_matches"
    __table_args__ = (UniqueConstraint("candidate_id", "job_id", name="uq_job_matches_candidate_job"),)

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hard_filter_passed: Mapped[bool] = mapped_column(nullable=False)
    overall_score: Mapped[float] = mapped_column(nullable=False)
    details_json: Mapped[JsonObject] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    candidate: Mapped[CandidateORM] = relationship(back_populates="matches")
    job: Mapped[JobORM] = relationship(back_populates="matches")


class ResumeVersionORM(Base):
    __tablename__ = "resume_versions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    base_resume_id: Mapped[str] = mapped_column(String(128), nullable=False)
    content_json: Mapped[JsonObject] = mapped_column(JSON, nullable=False)
    source_evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    candidate: Mapped[CandidateORM] = relationship(back_populates="resume_versions")


class ApplicationORM(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("candidate_id", "job_id", name="uq_applications_candidate_job"),)

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        _enum_type(ApplicationStatus), nullable=False, index=True
    )
    application_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    resume_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    candidate: Mapped[CandidateORM] = relationship(back_populates="applications")
    job: Mapped[JobORM] = relationship(back_populates="applications")
    answers: Mapped[list[ApplicationAnswerORM]] = relationship(
        back_populates="application", cascade="all, delete-orphan", passive_deletes=True
    )
    events: Mapped[list[ApplicationEventORM]] = relationship(
        back_populates="application", cascade="all, delete-orphan", passive_deletes=True
    )


class ApplicationAnswerORM(Base):
    __tablename__ = "application_answers"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(128), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    character_limit: Mapped[int | None] = mapped_column(nullable=True)
    source_evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_user_edited: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    application: Mapped[ApplicationORM] = relationship(back_populates="answers")


class ApplicationEventORM(Base):
    __tablename__ = "application_events"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    from_status: Mapped[ApplicationStatus | None] = mapped_column(
        _enum_type(ApplicationStatus), nullable=True
    )
    to_status: Mapped[ApplicationStatus | None] = mapped_column(
        _enum_type(ApplicationStatus), nullable=True
    )
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    details_json: Mapped[JsonObject] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    application: Mapped[ApplicationORM] = relationship(back_populates="events")
