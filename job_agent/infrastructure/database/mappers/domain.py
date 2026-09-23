"""领域对象和 ORM 实体之间的显式转换。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from job_agent.domain.enums import ApplicationStatus, EvidenceVerification
from job_agent.application.contracts import ResumeRecord
from job_agent.domain.schemas import (
    ApplicationAnswer,
    ApplicationEvent,
    ApplicationRecord,
    CandidateProfile,
    JobPosting,
    MatchResult,
    ResumeEvidence,
    ResumeVersion,
)
from job_agent.infrastructure.database.models import (
    ApplicationAnswerORM,
    ApplicationEventORM,
    ApplicationORM,
    CandidateORM,
    JobMatchORM,
    JobORM,
    ResumeEvidenceORM,
    ResumeORM,
    ResumeVersionORM,
)


class MappingError(ValueError):
    """领域对象和 ORM 数据转换失败。"""


ModelT = TypeVar("ModelT", bound=BaseModel)


def _to_db_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise MappingError("持久化 datetime 必须包含有效时区")
    return value.astimezone(timezone.utc)


def _from_db_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _validate(model_type: type[ModelT], payload: dict[str, Any]) -> ModelT:
    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        raise MappingError(f"无法恢复 {model_type.__name__}: {exc}") from exc


def candidate_to_orm(domain: CandidateProfile, orm: CandidateORM | None = None) -> CandidateORM:
    target = orm or CandidateORM(id=domain.id)
    target.basic_info_json = domain.basic_info.model_dump(mode="json")
    target.preferences_json = domain.preferences.model_dump(mode="json")
    target.education_json = [item.model_dump(mode="json") for item in domain.education]
    target.internships_json = [item.model_dump(mode="json") for item in domain.internships]
    target.projects_json = [item.model_dump(mode="json") for item in domain.projects]
    target.skills_json = list(domain.skills)
    target.awards_json = list(domain.awards)
    target.created_at = _to_db_datetime(domain.created_at)
    target.updated_at = _to_db_datetime(domain.updated_at)
    return target


def candidate_to_domain(orm: CandidateORM) -> CandidateProfile:
    return _validate(
        CandidateProfile,
        {
            "id": orm.id,
            "basic_info": orm.basic_info_json,
            "preferences": orm.preferences_json,
            "education": orm.education_json,
            "internships": orm.internships_json,
            "projects": orm.projects_json,
            "skills": orm.skills_json,
            "awards": orm.awards_json,
            "created_at": _from_db_datetime(orm.created_at),
            "updated_at": _from_db_datetime(orm.updated_at),
        },
    )


def evidence_to_orm(domain: ResumeEvidence, orm: ResumeEvidenceORM | None = None) -> ResumeEvidenceORM:
    target = orm or ResumeEvidenceORM(id=domain.id)
    target.candidate_id = domain.candidate_id
    target.experience_id = domain.experience_id
    target.category = domain.category
    target.content = domain.content
    target.skills_json = list(domain.skills)
    target.metrics_json = list(domain.metrics)
    target.source_resume_id = domain.source_resume_id
    target.verification = domain.verification
    target.created_at = _to_db_datetime(domain.created_at)
    target.updated_at = _to_db_datetime(domain.updated_at)
    return target


def evidence_to_domain(orm: ResumeEvidenceORM) -> ResumeEvidence:
    return _validate(
        ResumeEvidence,
        {
            "id": orm.id,
            "candidate_id": orm.candidate_id,
            "experience_id": orm.experience_id,
            "category": orm.category,
            "content": orm.content,
            "skills": orm.skills_json,
            "metrics": orm.metrics_json,
            "source_resume_id": orm.source_resume_id,
            "verification": _enum_value(orm.verification),
            "created_at": _from_db_datetime(orm.created_at),
            "updated_at": _from_db_datetime(orm.updated_at),
        },
    )


def resume_to_orm(domain: ResumeRecord, orm: ResumeORM | None = None) -> ResumeORM:
    target = orm or ResumeORM(id=domain.id)
    target.candidate_id = domain.candidate_id
    target.name = domain.name
    target.source_file_path = domain.source_file_path
    target.content_hash = domain.content_hash
    target.parsed_content_json = domain.parsed_content
    return target


def resume_to_domain(orm: ResumeORM) -> ResumeRecord:
    return _validate(
        ResumeRecord,
        {
            "id": orm.id,
            "candidate_id": orm.candidate_id,
            "name": orm.name,
            "source_file_path": orm.source_file_path,
            "content_hash": orm.content_hash,
            "parsed_content": orm.parsed_content_json,
        },
    )


def job_to_orm(domain: JobPosting, orm: JobORM | None = None) -> JobORM:
    target = orm or JobORM(id=domain.id)
    target.external_job_id = domain.external_job_id
    target.company = domain.company
    target.title = domain.title
    target.location = domain.location
    target.url = domain.url
    target.source = domain.source
    target.raw_jd = domain.raw_jd
    target.normalized_json = {
        "responsibilities": list(domain.responsibilities),
        "requirements": list(domain.requirements),
        "preferred_qualifications": list(domain.preferred_qualifications),
        "skills": list(domain.skills),
        "education_requirement": domain.education_requirement,
        "graduation_requirement": domain.graduation_requirement,
        "experience_requirement": domain.experience_requirement,
    }
    target.fingerprint = domain.fingerprint
    target.deadline = _to_db_datetime(domain.deadline) if domain.deadline else None
    target.discovered_at = _to_db_datetime(domain.discovered_at)
    return target


def job_to_domain(orm: JobORM) -> JobPosting:
    normalized = orm.normalized_json or {}
    return _validate(
        JobPosting,
        {
            "id": orm.id,
            "external_job_id": orm.external_job_id,
            "company": orm.company,
            "title": orm.title,
            "location": orm.location,
            "url": orm.url,
            "source": orm.source,
            "raw_jd": orm.raw_jd,
            "responsibilities": normalized.get("responsibilities", []),
            "requirements": normalized.get("requirements", []),
            "preferred_qualifications": normalized.get("preferred_qualifications", []),
            "skills": normalized.get("skills", []),
            "education_requirement": normalized.get("education_requirement"),
            "graduation_requirement": normalized.get("graduation_requirement"),
            "experience_requirement": normalized.get("experience_requirement"),
            "deadline": _from_db_datetime(orm.deadline) if orm.deadline else None,
            "fingerprint": orm.fingerprint,
            "discovered_at": _from_db_datetime(orm.discovered_at),
        },
    )


def match_to_orm(domain: MatchResult, orm: JobMatchORM | None = None) -> JobMatchORM:
    target = orm or JobMatchORM(id=domain.id)
    target.candidate_id = domain.candidate_id
    target.job_id = domain.job_id
    target.hard_filter_passed = domain.hard_filter_passed
    target.overall_score = domain.overall_score
    target.details_json = {
        "hard_filter_reasons": list(domain.hard_filter_reasons),
        "dimensions": [item.model_dump(mode="json") for item in domain.dimensions],
        "strengths": list(domain.strengths),
        "gaps": list(domain.gaps),
        "evidence_ids": list(domain.evidence_ids),
        "recommendation": domain.recommendation,
    }
    target.created_at = _to_db_datetime(domain.created_at)
    return target


def match_to_domain(orm: JobMatchORM) -> MatchResult:
    details = orm.details_json or {}
    return _validate(
        MatchResult,
        {
            "id": orm.id,
            "candidate_id": orm.candidate_id,
            "job_id": orm.job_id,
            "hard_filter_passed": orm.hard_filter_passed,
            "hard_filter_reasons": details.get("hard_filter_reasons", []),
            "overall_score": orm.overall_score,
            "dimensions": details.get("dimensions", []),
            "strengths": details.get("strengths", []),
            "gaps": details.get("gaps", []),
            "evidence_ids": details.get("evidence_ids", []),
            "recommendation": details.get("recommendation", "UNKNOWN"),
            "created_at": _from_db_datetime(orm.created_at),
        },
    )


def resume_version_to_orm(domain: ResumeVersion, orm: ResumeVersionORM | None = None) -> ResumeVersionORM:
    target = orm or ResumeVersionORM(id=domain.id)
    target.candidate_id = domain.candidate_id
    target.job_id = domain.job_id
    target.base_resume_id = domain.base_resume_id
    target.content_json = dict(domain.content)
    target.source_evidence_ids_json = list(domain.source_evidence_ids)
    target.file_path = domain.file_path
    target.content_hash = domain.content_hash
    target.created_at = _to_db_datetime(domain.created_at)
    return target


def resume_version_to_domain(orm: ResumeVersionORM) -> ResumeVersion:
    return _validate(
        ResumeVersion,
        {
            "id": orm.id,
            "candidate_id": orm.candidate_id,
            "job_id": orm.job_id,
            "base_resume_id": orm.base_resume_id,
            "content": orm.content_json,
            "source_evidence_ids": orm.source_evidence_ids_json,
            "file_path": orm.file_path,
            "content_hash": orm.content_hash,
            "created_at": _from_db_datetime(orm.created_at),
        },
    )


def application_to_orm(domain: ApplicationRecord, orm: ApplicationORM | None = None) -> ApplicationORM:
    target = orm or ApplicationORM(id=domain.id)
    target.candidate_id = domain.candidate_id
    target.job_id = domain.job_id
    target.status = domain.status
    target.application_url = domain.application_url
    target.resume_version_id = domain.resume_version_id
    target.submitted_at = _to_db_datetime(domain.submitted_at) if domain.submitted_at else None
    target.last_updated_at = _to_db_datetime(domain.last_updated_at)
    return target


def application_to_domain(orm: ApplicationORM) -> ApplicationRecord:
    return _validate(
        ApplicationRecord,
        {
            "id": orm.id,
            "candidate_id": orm.candidate_id,
            "job_id": orm.job_id,
            "status": _enum_value(orm.status),
            "application_url": orm.application_url,
            "resume_version_id": orm.resume_version_id,
            "submitted_at": _from_db_datetime(orm.submitted_at) if orm.submitted_at else None,
            "last_updated_at": _from_db_datetime(orm.last_updated_at),
        },
    )


def application_answer_to_orm(
    domain: ApplicationAnswer, orm: ApplicationAnswerORM | None = None
) -> ApplicationAnswerORM:
    target = orm or ApplicationAnswerORM(id=domain.id)
    target.application_id = domain.application_id
    target.question = domain.question
    target.question_type = domain.question_type
    target.answer = domain.answer
    target.character_limit = domain.character_limit
    target.source_evidence_ids_json = list(domain.source_evidence_ids)
    target.is_user_edited = domain.is_user_edited
    target.created_at = _to_db_datetime(domain.created_at)
    return target


def application_answer_to_domain(orm: ApplicationAnswerORM) -> ApplicationAnswer:
    return _validate(
        ApplicationAnswer,
        {
            "id": orm.id,
            "application_id": orm.application_id,
            "question": orm.question,
            "question_type": orm.question_type,
            "answer": orm.answer,
            "character_limit": orm.character_limit,
            "source_evidence_ids": orm.source_evidence_ids_json,
            "is_user_edited": orm.is_user_edited,
            "created_at": _from_db_datetime(orm.created_at),
        },
    )


def application_event_to_orm(
    domain: ApplicationEvent, orm: ApplicationEventORM | None = None
) -> ApplicationEventORM:
    target = orm or ApplicationEventORM(id=domain.id)
    target.application_id = domain.application_id
    target.event_type = domain.event_type
    target.from_status = domain.from_status
    target.to_status = domain.to_status
    target.source = domain.source
    target.details_json = dict(domain.details)
    target.occurred_at = _to_db_datetime(domain.occurred_at)
    return target


def application_event_to_domain(orm: ApplicationEventORM) -> ApplicationEvent:
    return _validate(
        ApplicationEvent,
        {
            "id": orm.id,
            "application_id": orm.application_id,
            "event_type": orm.event_type,
            "from_status": _optional_enum_value(orm.from_status),
            "to_status": _optional_enum_value(orm.to_status),
            "source": orm.source,
            "details": orm.details_json,
            "occurred_at": _from_db_datetime(orm.occurred_at),
        },
    )


def _enum_value(value: Any) -> str:
    return value.value if isinstance(value, (ApplicationStatus, EvidenceVerification)) else str(value)


def _optional_enum_value(value: Any) -> str | None:
    return None if value is None else _enum_value(value)
