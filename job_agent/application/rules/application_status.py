"""Application 状态转换的确定性规则。"""

from job_agent.domain import ApplicationStatus


NORMAL_STATUS_CHAIN: tuple[ApplicationStatus, ...] = (
    ApplicationStatus.DISCOVERED,
    ApplicationStatus.SHORTLISTED,
    ApplicationStatus.PREPARING,
    ApplicationStatus.READY_TO_APPLY,
    ApplicationStatus.SUBMITTED,
    ApplicationStatus.ONLINE_ASSESSMENT,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.OFFER,
)

TERMINAL_STATUSES: frozenset[ApplicationStatus] = frozenset(
    {
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.CLOSED,
    }
)

_NORMAL_STATUS_INDEX = {
    status: index for index, status in enumerate(NORMAL_STATUS_CHAIN)
}
_SUBMITTED_INDEX = _NORMAL_STATUS_INDEX[ApplicationStatus.SUBMITTED]


def can_transition(
    from_status: ApplicationStatus,
    to_status: ApplicationStatus,
) -> bool:
    """判断普通状态接口是否允许转换；同状态请求保持幂等。"""

    if from_status is to_status:
        return True
    if from_status in TERMINAL_STATUSES:
        return False
    if to_status in TERMINAL_STATUSES:
        return from_status in _NORMAL_STATUS_INDEX
    if from_status not in _NORMAL_STATUS_INDEX or to_status not in _NORMAL_STATUS_INDEX:
        return False
    return _NORMAL_STATUS_INDEX[to_status] > _NORMAL_STATUS_INDEX[from_status]


def is_submitted_or_later(status: ApplicationStatus) -> bool:
    """判断正常状态是否已经到达提交阶段。"""

    index = _NORMAL_STATUS_INDEX.get(status)
    return index is not None and index >= _SUBMITTED_INDEX


__all__ = [
    "NORMAL_STATUS_CHAIN",
    "TERMINAL_STATUSES",
    "can_transition",
    "is_submitted_or_later",
]
