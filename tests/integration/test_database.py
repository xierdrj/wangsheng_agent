"""T003 数据库、ORM、映射和迁移验收测试。"""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from job_agent.domain import (
    ApplicationAnswer,
    ApplicationEvent,
    ApplicationRecord,
    ApplicationStatus,
    BasicInfo,
    CandidateProfile,
    EvidenceVerification,
    JobPosting,
    JobPreference,
    MatchDimension,
    MatchResult,
    ResumeEvidence,
    ResumeVersion,
)
from job_agent.infrastructure.database.base import Base
from job_agent.infrastructure.database.engine import (
    DatabaseConfigurationError,
    create_engine_from_url,
    sqlite_foreign_keys_enabled,
)
from job_agent.infrastructure.database.init import initialize_database
from job_agent.infrastructure.database.mappers import (
    application_answer_to_domain,
    application_answer_to_orm,
    application_event_to_domain,
    application_event_to_orm,
    application_to_domain,
    application_to_orm,
    candidate_to_domain,
    candidate_to_orm,
    evidence_to_domain,
    evidence_to_orm,
    job_to_domain,
    job_to_orm,
    match_to_domain,
    match_to_orm,
    resume_version_to_domain,
    resume_version_to_orm,
)
from job_agent.infrastructure.database.models import (
    ApplicationAnswerORM,
    ApplicationEventORM,
    ApplicationORM,
    CandidateORM,
    JobORM,
    ResumeEvidenceORM,
)
from job_agent.infrastructure.database.session import create_session_factory, session_scope


ROOT = Path(__file__).parents[2]
UTC_PLUS_8 = timezone(timedelta(hours=8))
LOCAL_TIME = datetime(2026, 9, 21, 16, 30, tzinfo=UTC_PLUS_8)


@pytest.fixture()
def db(tmp_path: Path):
    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    initialize_database(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def make_candidate() -> CandidateProfile:
    return CandidateProfile(
        id="candidate-1",
        basic_info=BasicInfo(
            full_name="脱敏候选人",
            email="candidate@example.com",
            phone="13800000000",
            city="成都",
        ),
        preferences=JobPreference(roles=["算法工程师"], locations=["成都"]),
        skills=["Python", "SQL"],
        created_at=LOCAL_TIME,
        updated_at=LOCAL_TIME,
    )


def make_job() -> JobPosting:
    return JobPosting(
        id="job-1",
        company="脱敏科技",
        title="算法工程师",
        location="成都",
        url="https://jobs.example.com/job-1",
        source="fixture",
        raw_jd="负责模型训练",
        responsibilities=["模型训练"],
        requirements=["Python"],
        skills=["Python"],
        fingerprint="fingerprint-1",
        discovered_at=LOCAL_TIME,
    )


def make_application() -> ApplicationRecord:
    return ApplicationRecord(
        id="application-1",
        candidate_id="candidate-1",
        job_id="job-1",
        status=ApplicationStatus.READY_TO_APPLY,
        application_url="https://apply.example.com/job-1",
        last_updated_at=LOCAL_TIME,
    )


def _normalized_sql(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _schema_signature(engine) -> dict[str, object]:
    """反射数据库结构，用于逐项比较迁移结果和 ORM metadata。"""

    inspector = inspect(engine)
    result: dict[str, object] = {}
    for table_name in sorted(set(inspector.get_table_names()) - {"alembic_version"}):
        columns = tuple(
            (
                column["name"],
                str(column["type"]).upper(),
                column["nullable"],
                column.get("primary_key", 0),
            )
            for column in inspector.get_columns(table_name)
        )
        foreign_keys = tuple(
            sorted(
                (
                    tuple(item["constrained_columns"]),
                    item["referred_table"],
                    tuple(item["referred_columns"]),
                    item.get("options", {}).get("ondelete"),
                )
                for item in inspector.get_foreign_keys(table_name)
            )
        )
        unique_constraints = tuple(
            sorted(
                (item["name"] or "", tuple(item["column_names"]))
                for item in inspector.get_unique_constraints(table_name)
            )
        )
        indexes = tuple(
            sorted(
                (item["name"], tuple(item["column_names"]), item["unique"])
                for item in inspector.get_indexes(table_name)
            )
        )
        check_constraints = tuple(
            sorted(
                (item["name"] or "", _normalized_sql(item["sqltext"]))
                for item in inspector.get_check_constraints(table_name)
            )
        )
        result[table_name] = {
            "columns": columns,
            "primary_key": tuple(inspector.get_pk_constraint(table_name)["constrained_columns"]),
            "foreign_keys": foreign_keys,
            "unique_constraints": unique_constraints,
            "indexes": indexes,
            "check_constraints": check_constraints,
        }
    return result


def test_engine_factory_and_sqlite_foreign_keys(tmp_path: Path) -> None:
    database_path = tmp_path / "factory.sqlite3"
    engine = create_engine_from_url(f"sqlite:///{database_path}")

    assert not database_path.exists()
    assert sqlite_foreign_keys_enabled(engine) is True
    engine.dispose()

    with pytest.raises(DatabaseConfigurationError):
        create_engine_from_url("not-a-database-url")


def test_importing_database_package_does_not_create_database_file(tmp_path: Path) -> None:
    database_path = tmp_path / "import-side-effect.sqlite3"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path}"
    environment["PYTHONPATH"] = str(ROOT)

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sqlalchemy; "
                "sqlalchemy.create_engine = lambda *args, **kwargs: "
                "(_ for _ in ()).throw(AssertionError('导入阶段禁止创建 Engine')); "
                "import job_agent.infrastructure.database"
            ),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert not database_path.exists()


def test_initialize_database_creates_expected_tables(db) -> None:
    table_names = set(inspect(db).get_table_names())

    assert {
        "candidates",
        "resumes",
        "resume_evidence",
        "jobs",
        "job_matches",
        "resume_versions",
        "applications",
        "application_answers",
        "application_events",
    } <= table_names


def test_session_scope_commits_and_rolls_back(db) -> None:
    factory = create_session_factory(db)
    candidate = candidate_to_orm(make_candidate())

    with session_scope(factory) as session:
        session.add(candidate)
    assert not session.in_transaction()

    with session_scope(factory) as session:
        assert session.scalar(select(CandidateORM).where(CandidateORM.id == "candidate-1")) is not None

    with pytest.raises(RuntimeError):
        with session_scope(factory) as session:
            session.add(candidate_to_orm(make_candidate(), CandidateORM(id="candidate-rollback")))
            raise RuntimeError("模拟事务失败")

    with session_scope(factory) as session:
        assert session.get(CandidateORM, "candidate-rollback") is None


def test_foreign_key_and_unique_constraints_are_enforced(db) -> None:
    factory = create_session_factory(db)
    with pytest.raises(IntegrityError):
        with session_scope(factory) as session:
            session.add(
                ResumeEvidenceORM(
                    id="evidence-orphan",
                    candidate_id="missing",
                    category="project",
                    content="事实",
                    skills_json=[],
                    metrics_json=[],
                    verification=EvidenceVerification.UNVERIFIED,
                    created_at=LOCAL_TIME,
                    updated_at=LOCAL_TIME,
                )
            )

    with session_scope(factory) as session:
        session.add(job_to_orm(make_job()))

    with pytest.raises(IntegrityError):
        with session_scope(factory) as session:
            session.add(job_to_orm(make_job(), JobORM(id="job-duplicate")))


def test_candidate_delete_cascades_application_events(db) -> None:
    factory = create_session_factory(db)
    with session_scope(factory) as session:
        candidate = candidate_to_orm(make_candidate())
        job = job_to_orm(make_job())
        application = application_to_orm(make_application())
        event = application_event_to_orm(
            ApplicationEvent(
                id="event-1",
                application_id="application-1",
                event_type="created",
                to_status=ApplicationStatus.READY_TO_APPLY,
                source="test",
                occurred_at=LOCAL_TIME,
            )
        )
        session.add_all([candidate, job, application, event])

    with session_scope(factory) as session:
        candidate = session.get(CandidateORM, "candidate-1")
        session.delete(candidate)

    with session_scope(factory) as session:
        assert session.get(ApplicationORM, "application-1") is None
        assert session.get(ApplicationEventORM, "event-1") is None


def test_application_status_is_persisted_as_stable_string(db) -> None:
    factory = create_session_factory(db)
    with session_scope(factory) as session:
        session.add(candidate_to_orm(make_candidate()))
        session.add(job_to_orm(make_job()))
        session.add(application_to_orm(make_application()))

    with db.connect() as connection:
        assert connection.execute(text("SELECT status FROM applications")).scalar() == "READY_TO_APPLY"


def test_domain_orm_mappers_round_trip_and_preserve_utc() -> None:
    candidate = make_candidate()
    candidate_round_trip = candidate_to_domain(candidate_to_orm(candidate))
    assert candidate_round_trip.basic_info == candidate.basic_info
    assert candidate_round_trip.created_at.tzinfo == timezone.utc
    assert candidate_round_trip.created_at.hour == 8

    job = make_job()
    assert job_to_domain(job_to_orm(job)) == job.model_copy(update={"discovered_at": job.discovered_at.astimezone(timezone.utc)})

    evidence = ResumeEvidence(
        id="evidence-1",
        candidate_id=candidate.id,
        category="project",
        content="完成了可复现的数据处理流程",
        skills=["Python"],
        metrics=["1 个流程"],
        verification=EvidenceVerification.VERIFIED,
        created_at=LOCAL_TIME,
        updated_at=LOCAL_TIME,
    )
    assert evidence_to_domain(evidence_to_orm(evidence)).verification is EvidenceVerification.VERIFIED

    match = MatchResult(
        id="match-1",
        candidate_id=candidate.id,
        job_id=job.id,
        hard_filter_passed=True,
        overall_score=88,
        dimensions=[MatchDimension(name="skills", score=90, weight=0.5)],
        recommendation="SHORTLIST",
        created_at=LOCAL_TIME,
    )
    assert match_to_domain(match_to_orm(match)).dimensions[0].score == 90

    resume = ResumeVersion(
        id="resume-version-1",
        candidate_id=candidate.id,
        job_id=job.id,
        base_resume_id="resume-base-1",
        content={"summary": "基于证据的摘要"},
        source_evidence_ids=[evidence.id],
        content_hash="hash-1",
        created_at=LOCAL_TIME,
    )
    assert resume_version_to_domain(resume_version_to_orm(resume)).source_evidence_ids == [evidence.id]

    application = make_application()
    assert application_to_domain(application_to_orm(application)).status is ApplicationStatus.READY_TO_APPLY

    answer = ApplicationAnswer(
        id="answer-1",
        application_id=application.id,
        question="请介绍一个项目",
        question_type="text",
        answer="脱敏回答",
        source_evidence_ids=[evidence.id],
        character_limit=200,
        created_at=LOCAL_TIME,
    )
    assert application_answer_to_domain(application_answer_to_orm(answer)).source_evidence_ids == [evidence.id]

    event = ApplicationEvent(
        id="event-1",
        application_id=application.id,
        event_type="created",
        from_status=None,
        to_status=ApplicationStatus.READY_TO_APPLY,
        source="test",
        details={"dry_run": True},
        occurred_at=LOCAL_TIME,
    )
    assert application_event_to_domain(application_event_to_orm(event)).to_status is ApplicationStatus.READY_TO_APPLY


def test_initial_revision_is_immutable_and_independent_from_orm() -> None:
    revision_path = ROOT / "migrations" / "versions" / "0001_initial_persistence.py"
    source = revision_path.read_text(encoding="utf-8")

    assert "op.create_table" in source
    assert "op.drop_table" in source
    assert "create_all" not in source
    assert "drop_all" not in source
    assert "job_agent" not in source
    assert re.search(r"[A-Za-z]:[\\/]", source) is None


def test_alembic_schema_matches_orm_and_is_repeatable(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.sqlite3"
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")
    migrated_engine = create_engine_from_url(f"sqlite:///{database_path}")
    metadata_engine = create_engine_from_url("sqlite:///:memory:")
    try:
        initialize_database(metadata_engine)
        assert sqlite_foreign_keys_enabled(migrated_engine) is True
        assert _schema_signature(migrated_engine) == _schema_signature(metadata_engine)
        with migrated_engine.connect() as connection:
            context = MigrationContext.configure(connection)
            assert compare_metadata(context, Base.metadata) == []
    finally:
        migrated_engine.dispose()
        metadata_engine.dispose()

    command.downgrade(config, "base")
    engine = create_engine_from_url(f"sqlite:///{database_path}")
    try:
        assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine_from_url(f"sqlite:///{database_path}")
    try:
        assert _schema_signature(engine)
        assert "applications" in inspect(engine).get_table_names()
        assert sqlite_foreign_keys_enabled(engine) is True
    finally:
        engine.dispose()
