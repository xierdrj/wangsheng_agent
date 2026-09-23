"""T005 Profile Service 集成与架构验收测试。"""

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from job_agent.application.contracts import ProfileImportRequest, ProfileImportResult
from job_agent.application.ports import (
    DuplicateEntityError,
    EntityNotFoundError,
    ImmutableFieldError,
    InvalidPaginationError,
)
from job_agent.application.services import EvidenceStateError, ProfileService
from job_agent.domain import (
    BasicInfo,
    CandidateProfile,
    EvidenceVerification,
    JobPreference,
    ResumeEvidence,
)
from job_agent.infrastructure.database import (
    SqlAlchemyProfileUnitOfWork,
    create_engine_from_url,
    create_session_factory,
    initialize_database,
)
from job_agent.infrastructure.database.models import CandidateORM, ResumeEvidenceORM


UTC_PLUS_8 = timezone(timedelta(hours=8))
CALLER_TIME = datetime(2025, 1, 1, 8, 0, tzinfo=UTC_PLUS_8)
NOW = datetime(2026, 10, 1, 2, 0, tzinfo=timezone.utc)


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


@pytest.fixture()
def session_factory(tmp_path):
    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'profile-service.sqlite3'}")
    initialize_database(engine)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture()
def service_context(session_factory):
    clock = MutableClock(NOW)
    unit_of_work_factory = lambda: SqlAlchemyProfileUnitOfWork(session_factory)
    return ProfileService(unit_of_work_factory, clock=clock), clock, unit_of_work_factory


def candidate(candidate_id: str = "candidate-1") -> CandidateProfile:
    return CandidateProfile(
        id=candidate_id,
        basic_info=BasicInfo(
            full_name="脱敏候选人",
            email=f"{candidate_id}@example.com",
            phone="13800000000",
        ),
        preferences=JobPreference(roles=["Python 工程师"]),
        skills=["Python"],
        created_at=CALLER_TIME,
        updated_at=CALLER_TIME,
    )


def evidence(
    evidence_id: str,
    candidate_id: str = "candidate-1",
    *,
    verification: EvidenceVerification = EvidenceVerification.UNVERIFIED,
) -> ResumeEvidence:
    return ResumeEvidence(
        id=evidence_id,
        candidate_id=candidate_id,
        category="project",
        content=f"脱敏事实-{evidence_id}",
        skills=["Python"],
        verification=verification,
        created_at=CALLER_TIME,
        updated_at=CALLER_TIME,
    )


def test_profile_create_query_update_and_time_semantics(service_context) -> None:
    service, clock, _ = service_context
    created = service.create_profile(candidate())

    assert isinstance(created, CandidateProfile)
    assert created.created_at == NOW
    assert created.updated_at == NOW
    assert created.created_at.tzinfo is timezone.utc
    assert service.get_profile(created.id) == created
    assert service.get_profile("missing") is None

    clock.value = NOW + timedelta(hours=1)
    edited_input = created.model_copy(
        update={
            "skills": ["Python", "SQL"],
            "created_at": NOW + timedelta(days=30),
            "updated_at": NOW - timedelta(days=30),
        }
    )
    edited = service.update_profile(created.id, edited_input)
    assert edited.skills == ["Python", "SQL"]
    assert edited.created_at == created.created_at
    assert edited.updated_at == clock.value
    assert edited.updated_at.tzinfo is timezone.utc

    with pytest.raises(ImmutableFieldError):
        service.update_profile("another-id", edited)
    with pytest.raises(EntityNotFoundError):
        service.update_profile("missing", candidate("missing"))
    with pytest.raises(DuplicateEntityError):
        service.create_profile(candidate())


def test_profile_update_timestamp_is_monotonic(service_context) -> None:
    service, clock, _ = service_context
    created = service.create_profile(candidate())
    clock.value = NOW - timedelta(days=1)

    edited = service.update_profile(
        created.id,
        created.model_copy(update={"awards": ["脱敏奖项"]}),
    )

    assert edited.updated_at == created.updated_at + timedelta(microseconds=1)
    assert edited.updated_at.tzinfo is timezone.utc


def test_structured_import_validates_all_input_before_writing(service_context) -> None:
    service, _, _ = service_context
    payload = {
        "profile": candidate("candidate-import").model_dump(mode="python"),
        "evidence": [
            evidence("evidence-1", "candidate-import").model_dump(mode="python"),
            evidence("evidence-2", "candidate-import").model_dump(mode="python"),
        ],
    }

    result = service.import_structured(payload)

    assert isinstance(result, ProfileImportResult)
    assert result.profile.created_at == NOW
    assert len(result.evidence) == 2
    assert all(item.verification is EvidenceVerification.UNVERIFIED for item in result.evidence)
    assert all(item.created_at == NOW == item.updated_at for item in result.evidence)

    invalid_payloads = [
        {**payload, "unexpected": True},
        {
            **payload,
            "profile": {
                **payload["profile"],
                "basic_info": {
                    **payload["profile"]["basic_info"],
                    "email": "invalid-email",
                },
                "id": "candidate-invalid",
            },
            "evidence": [],
        },
        {
            "profile": candidate("candidate-verified").model_dump(mode="python"),
            "evidence": [
                evidence(
                    "evidence-verified",
                    "candidate-verified",
                    verification=EvidenceVerification.VERIFIED,
                ).model_dump(mode="python")
            ],
        },
    ]
    for invalid in invalid_payloads:
        with pytest.raises(ValidationError):
            service.import_structured(invalid)

    assert service.get_profile("candidate-invalid") is None
    assert service.get_profile("candidate-verified") is None


def test_structured_import_rolls_back_candidate_and_all_evidence(service_context) -> None:
    service, _, _ = service_context
    service.create_profile(candidate("candidate-existing"))
    existing = service.add_evidence(evidence("evidence-conflict", "candidate-existing"))
    request = ProfileImportRequest(
        profile=candidate("candidate-new"),
        evidence=[
            evidence("evidence-new", "candidate-new"),
            evidence("evidence-conflict", "candidate-new"),
        ],
    )

    with pytest.raises(DuplicateEntityError):
        service.import_structured(request)

    assert service.get_profile("candidate-new") is None
    assert service.list_evidence_for_review("candidate-new").items == []
    assert service.list_evidence_for_review("candidate-existing").items == [existing]


def test_add_and_verify_evidence_use_explicit_safe_flow(service_context) -> None:
    service, clock, unit_of_work_factory = service_context
    service.create_profile(candidate())

    added = service.add_evidence(evidence("evidence-1"))
    assert isinstance(added, ResumeEvidence)
    assert added.verification is EvidenceVerification.UNVERIFIED
    assert added.candidate_id == "candidate-1"
    assert added.created_at == NOW == added.updated_at

    with pytest.raises(EntityNotFoundError):
        service.add_evidence(evidence("orphan", "missing"))
    with pytest.raises(EvidenceStateError):
        service.add_evidence(
            evidence("verified-directly", verification=EvidenceVerification.VERIFIED)
        )

    clock.value = NOW + timedelta(hours=1)
    verified = service.verify_evidence(added.id)
    assert verified.verification is EvidenceVerification.VERIFIED
    assert verified.candidate_id == added.candidate_id
    assert verified.content == added.content
    assert verified.created_at == added.created_at
    assert verified.updated_at == clock.value

    clock.value = NOW + timedelta(hours=2)
    assert service.verify_evidence(added.id) == verified
    with pytest.raises(EntityNotFoundError):
        service.verify_evidence("missing")

    rejected = evidence(
        "evidence-rejected",
        verification=EvidenceVerification.REJECTED,
    )
    with unit_of_work_factory() as unit_of_work:
        unit_of_work.evidence.add(rejected)
    with pytest.raises(EvidenceStateError):
        service.verify_evidence(rejected.id)


def test_verified_query_filters_in_database_before_pagination(service_context) -> None:
    service, _, _ = service_context
    service.create_profile(candidate())
    service.create_profile(candidate("candidate-empty"))
    for evidence_id in ["evidence-a", "evidence-b", "evidence-c", "evidence-d"]:
        service.add_evidence(evidence(evidence_id))
    service.verify_evidence("evidence-b")
    service.verify_evidence("evidence-d")

    review = service.list_evidence_for_review("candidate-1", limit=2, offset=0)
    first = service.list_verified_evidence("candidate-1", limit=1, offset=0)
    second = service.list_verified_evidence("candidate-1", limit=1, offset=1)
    empty = service.list_verified_evidence("candidate-empty", limit=10, offset=0)

    assert review.total == 4
    assert [item.id for item in review.items] == ["evidence-a", "evidence-b"]
    assert (first.total, first.limit, first.offset) == (2, 1, 0)
    assert [item.id for item in first.items] == ["evidence-b"]
    assert [item.id for item in second.items] == ["evidence-d"]
    assert all(item.verification is EvidenceVerification.VERIFIED for item in first.items)
    assert (empty.items, empty.total) == ([], 0)

    with pytest.raises(InvalidPaginationError):
        service.list_verified_evidence("candidate-1", limit=0)


def test_profile_service_architecture_has_no_sqlalchemy_or_commit_dependency() -> None:
    paths = [
        Path("job_agent/application/services/profile.py"),
        Path("job_agent/application/ports/unit_of_work.py"),
        Path("job_agent/application/contracts/profile.py"),
    ]
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(name == "sqlalchemy" or name.startswith("sqlalchemy.") for name in modules)
        assert ".commit(" not in source


def test_unit_of_work_returns_domain_objects_not_orm_entities(service_context) -> None:
    service, _, _ = service_context
    profile = service.create_profile(candidate())
    item = service.add_evidence(evidence("evidence-1"))

    assert isinstance(profile, CandidateProfile)
    assert isinstance(item, ResumeEvidence)
    assert not isinstance(profile, CandidateORM)
    assert not isinstance(item, ResumeEvidenceORM)
