"""待投池、投递状态和事件时间线的应用服务。"""

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from job_agent.application.contracts import (
    AddToApplicationPoolRequest,
    ApplicationTransitionRequest,
)
from job_agent.application.ports import (
    DuplicateEntityError,
    EntityNotFoundError,
    JobApplicationUnitOfWork,
    Page,
)
from job_agent.application.rules import can_transition, is_submitted_or_later
from job_agent.domain import (
    ApplicationEvent,
    ApplicationRecord,
    ApplicationStatus,
)


Clock = Callable[[], datetime]
EventIdFactory = Callable[[], str]
UnitOfWorkFactory = Callable[[], JobApplicationUnitOfWork]

APPLICATION_CREATED = "APPLICATION_CREATED"
STATUS_CHANGED = "STATUS_CHANGED"


class ApplicationConflictError(ValueError):
    """待投池请求与现有 Application 的不可变信息冲突。"""


class InvalidApplicationTransitionError(ValueError):
    """Application 状态转换不符合确定性状态规则。"""


def _system_utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid_event_id() -> str:
    return str(uuid4())


class ApplicationService:
    """通过 Repository 与 Unit of Work 编排投递业务。"""

    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        *,
        clock: Clock = _system_utc_now,
        event_id_factory: EventIdFactory = _uuid_event_id,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._event_id_factory = event_id_factory

    def add_to_application_pool(
        self, payload: AddToApplicationPoolRequest | Mapping[str, object]
    ) -> ApplicationRecord:
        """创建 SHORTLISTED Application 和初始事件，重复请求保持幂等。"""

        request = AddToApplicationPoolRequest.model_validate(payload)
        with self._unit_of_work_factory() as unit_of_work:
            if unit_of_work.candidates.get_by_id(request.candidate_id) is None:
                raise EntityNotFoundError(f"候选人不存在: {request.candidate_id}")
            if unit_of_work.jobs.get_by_id(request.job_id) is None:
                raise EntityNotFoundError(f"岗位不存在: {request.job_id}")
            self._validate_resume_version(unit_of_work, request)

            existing = unit_of_work.applications.get_by_candidate_and_job(
                request.candidate_id, request.job_id
            )
            if existing is not None:
                if self._is_same_pool_request(unit_of_work, existing, request):
                    return existing
                raise ApplicationConflictError("同一 candidate/job 已存在不同的投递请求")
            if unit_of_work.applications.get_by_id(request.application_id) is not None:
                raise ApplicationConflictError(
                    f"Application ID 已被使用: {request.application_id}"
                )

            occurred_at = self._now()
            application = ApplicationRecord(
                id=request.application_id,
                candidate_id=request.candidate_id,
                job_id=request.job_id,
                status=ApplicationStatus.SHORTLISTED,
                application_url=request.application_url,
                resume_version_id=request.resume_version_id,
                submitted_at=None,
                last_updated_at=occurred_at,
            )
            event = ApplicationEvent(
                id=self._new_event_id(),
                application_id=request.application_id,
                event_type=APPLICATION_CREATED,
                from_status=None,
                to_status=ApplicationStatus.SHORTLISTED,
                source=request.source,
                details={},
                occurred_at=occurred_at,
            )
            try:
                created = unit_of_work.applications.add(application)
                unit_of_work.applications.append_event(event)
            except DuplicateEntityError as exc:
                raise ApplicationConflictError("投递或初始事件存在唯一性冲突") from exc
            return created

    def get_application(self, application_id: str) -> ApplicationRecord | None:
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.applications.get_by_id(application_id)

    def list_applications(
        self, candidate_id: str, *, limit: int = 50, offset: int = 0
    ) -> Page[ApplicationRecord]:
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.applications.list_by_candidate(
                candidate_id, limit=limit, offset=offset
            )

    def list_application_events(
        self, application_id: str, *, limit: int = 50, offset: int = 0
    ) -> Page[ApplicationEvent]:
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.applications.list_events(
                application_id, limit=limit, offset=offset
            )

    def transition_status(
        self, payload: ApplicationTransitionRequest | Mapping[str, object]
    ) -> ApplicationRecord:
        """按确定性规则更新状态并在同一事务追加事件。"""

        request = ApplicationTransitionRequest.model_validate(payload)
        with self._unit_of_work_factory() as unit_of_work:
            current = unit_of_work.applications.get_by_id(request.application_id)
            if current is None:
                raise EntityNotFoundError(f"投递记录不存在: {request.application_id}")
            if current.status is request.to_status:
                return current
            if not can_transition(current.status, request.to_status):
                raise InvalidApplicationTransitionError(
                    f"不允许从 {current.status.value} 转换到 {request.to_status.value}"
                )

            occurred_at = self._next_timestamp(current.last_updated_at)
            submitted_at = current.submitted_at
            if submitted_at is None and is_submitted_or_later(request.to_status):
                submitted_at = occurred_at
            updated = current.model_copy(
                update={
                    "status": request.to_status,
                    "submitted_at": submitted_at,
                    "last_updated_at": occurred_at,
                }
            )
            event = ApplicationEvent(
                id=self._new_event_id(),
                application_id=current.id,
                event_type=STATUS_CHANGED,
                from_status=current.status,
                to_status=request.to_status,
                source=request.source,
                details=dict(request.details),
                occurred_at=occurred_at,
            )
            changed = unit_of_work.applications.update(updated)
            unit_of_work.applications.append_event(event)
            return changed

    def _validate_resume_version(
        self,
        unit_of_work: JobApplicationUnitOfWork,
        request: AddToApplicationPoolRequest,
    ) -> None:
        if request.resume_version_id is None:
            return
        resume_version = unit_of_work.resume_versions.get_by_id(request.resume_version_id)
        if resume_version is None:
            raise EntityNotFoundError(
                f"简历版本不存在: {request.resume_version_id}"
            )
        if resume_version.candidate_id != request.candidate_id:
            raise ApplicationConflictError("简历版本不属于当前 Candidate")

    def _is_same_pool_request(
        self,
        unit_of_work: JobApplicationUnitOfWork,
        existing: ApplicationRecord,
        request: AddToApplicationPoolRequest,
    ) -> bool:
        immutable_fields_match = (
            existing.id == request.application_id
            and existing.candidate_id == request.candidate_id
            and existing.job_id == request.job_id
            and existing.application_url == request.application_url
            and existing.resume_version_id == request.resume_version_id
        )
        if not immutable_fields_match:
            return False
        events = unit_of_work.applications.list_events(existing.id, limit=1, offset=0)
        if not events.items:
            return False
        initial_event = events.items[0]
        return (
            initial_event.event_type == APPLICATION_CREATED
            and initial_event.from_status is None
            and initial_event.to_status is ApplicationStatus.SHORTLISTED
            and initial_event.source == request.source
        )

    def _new_event_id(self) -> str:
        event_id = self._event_id_factory()
        if not event_id.strip():
            raise ValueError("Event ID 不能为空")
        return event_id

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Application Service Clock 必须返回带时区时间")
        return value.astimezone(timezone.utc)

    def _next_timestamp(self, previous: datetime) -> datetime:
        now = self._now()
        previous_utc = previous.astimezone(timezone.utc)
        if now <= previous_utc:
            return previous_utc + timedelta(microseconds=1)
        return now


__all__ = [
    "APPLICATION_CREATED",
    "STATUS_CHANGED",
    "ApplicationConflictError",
    "ApplicationService",
    "InvalidApplicationTransitionError",
]
