"""建立 T003 业务数据库基础表。

Revision ID: 0001_initial_persistence
Revises:
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial_persistence"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


APPLICATION_STATUS_VALUES = (
    "DISCOVERED",
    "SHORTLISTED",
    "PREPARING",
    "READY_TO_APPLY",
    "SUBMITTED",
    "ONLINE_ASSESSMENT",
    "INTERVIEW",
    "OFFER",
    "REJECTED",
    "WITHDRAWN",
    "CLOSED",
)

EVIDENCE_VERIFICATION_VALUES = (
    "UNVERIFIED",
    "VERIFIED",
    "REJECTED",
)


def _application_status_enum() -> sa.Enum:
    """返回与 ORM 定义一致的非原生投递状态枚举。"""

    return sa.Enum(
        *APPLICATION_STATUS_VALUES,
        name="applicationstatus",
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )


def _evidence_verification_enum() -> sa.Enum:
    """返回与 ORM 定义一致的非原生证据状态枚举。"""

    return sa.Enum(
        *EVIDENCE_VERIFICATION_VALUES,
        name="evidenceverification",
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )


def upgrade() -> None:
    """按外键依赖顺序显式创建 T003 业务表、约束和索引。"""

    op.create_table(
        "candidates",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("basic_info_json", sa.JSON(), nullable=False),
        sa.Column("preferences_json", sa.JSON(), nullable=False),
        sa.Column("education_json", sa.JSON(), nullable=False),
        sa.Column("internships_json", sa.JSON(), nullable=False),
        sa.Column("projects_json", sa.JSON(), nullable=False),
        sa.Column("skills_json", sa.JSON(), nullable=False),
        sa.Column("awards_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("external_job_id", sa.String(length=255), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("raw_jd", sa.Text(), nullable=False),
        sa.Column("normalized_json", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=False), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=False), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_fingerprint", "jobs", ["fingerprint"], unique=True)

    op.create_table(
        "job_matches",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("candidate_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("hard_filter_passed", sa.Boolean(), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_job_matches_candidate_job"),
    )
    op.create_index("ix_job_matches_candidate_id", "job_matches", ["candidate_id"], unique=False)
    op.create_index("ix_job_matches_job_id", "job_matches", ["job_id"], unique=False)

    op.create_table(
        "resume_versions",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("candidate_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("base_resume_id", sa.String(length=128), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("source_evidence_ids_json", sa.JSON(), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_resume_versions_candidate_id", "resume_versions", ["candidate_id"], unique=False
    )
    op.create_index("ix_resume_versions_job_id", "resume_versions", ["job_id"], unique=False)

    op.create_table(
        "resumes",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("candidate_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_file_path", sa.String(length=1024), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("parsed_content_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "content_hash", name="uq_resumes_candidate_hash"),
    )
    op.create_index("ix_resumes_candidate_id", "resumes", ["candidate_id"], unique=False)

    op.create_table(
        "applications",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("candidate_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("status", _application_status_enum(), nullable=False),
        sa.Column("application_url", sa.String(length=1024), nullable=False),
        sa.Column("resume_version_id", sa.String(length=128), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["resume_version_id"], ["resume_versions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_applications_candidate_job"),
    )
    op.create_index("ix_applications_candidate_id", "applications", ["candidate_id"], unique=False)
    op.create_index("ix_applications_job_id", "applications", ["job_id"], unique=False)
    op.create_index(
        "ix_applications_resume_version_id", "applications", ["resume_version_id"], unique=False
    )
    op.create_index("ix_applications_status", "applications", ["status"], unique=False)

    op.create_table(
        "resume_evidence",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("candidate_id", sa.String(length=128), nullable=False),
        sa.Column("experience_id", sa.String(length=128), nullable=True),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("skills_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("source_resume_id", sa.String(length=128), nullable=True),
        sa.Column("verification", _evidence_verification_enum(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_resume_id"], ["resumes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resume_evidence_candidate_id", "resume_evidence", ["candidate_id"])
    op.create_index("ix_resume_evidence_category", "resume_evidence", ["category"])
    op.create_index(
        "ix_resume_evidence_source_resume_id", "resume_evidence", ["source_resume_id"]
    )
    op.create_index("ix_resume_evidence_verification", "resume_evidence", ["verification"])
    op.create_index(
        "ix_resume_evidence_candidate_category",
        "resume_evidence",
        ["candidate_id", "category"],
    )

    op.create_table(
        "application_answers",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("application_id", sa.String(length=128), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(length=128), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("character_limit", sa.Integer(), nullable=True),
        sa.Column("source_evidence_ids_json", sa.JSON(), nullable=False),
        sa.Column("is_user_edited", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_application_answers_application_id",
        "application_answers",
        ["application_id"],
        unique=False,
    )

    op.create_table(
        "application_events",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("application_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("from_status", _application_status_enum(), nullable=True),
        sa.Column("to_status", _application_status_enum(), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_application_events_application_id",
        "application_events",
        ["application_id"],
        unique=False,
    )


def downgrade() -> None:
    """按外键依赖的反向顺序删除 T003 业务表。"""

    op.drop_index("ix_application_events_application_id", table_name="application_events")
    op.drop_table("application_events")

    op.drop_index("ix_application_answers_application_id", table_name="application_answers")
    op.drop_table("application_answers")

    op.drop_index("ix_resume_evidence_candidate_category", table_name="resume_evidence")
    op.drop_index("ix_resume_evidence_verification", table_name="resume_evidence")
    op.drop_index("ix_resume_evidence_source_resume_id", table_name="resume_evidence")
    op.drop_index("ix_resume_evidence_category", table_name="resume_evidence")
    op.drop_index("ix_resume_evidence_candidate_id", table_name="resume_evidence")
    op.drop_table("resume_evidence")

    op.drop_index("ix_applications_status", table_name="applications")
    op.drop_index("ix_applications_resume_version_id", table_name="applications")
    op.drop_index("ix_applications_job_id", table_name="applications")
    op.drop_index("ix_applications_candidate_id", table_name="applications")
    op.drop_table("applications")

    op.drop_index("ix_resumes_candidate_id", table_name="resumes")
    op.drop_table("resumes")

    op.drop_index("ix_resume_versions_job_id", table_name="resume_versions")
    op.drop_index("ix_resume_versions_candidate_id", table_name="resume_versions")
    op.drop_table("resume_versions")

    op.drop_index("ix_job_matches_job_id", table_name="job_matches")
    op.drop_index("ix_job_matches_candidate_id", table_name="job_matches")
    op.drop_table("job_matches")

    op.drop_index("ix_jobs_fingerprint", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("candidates")
