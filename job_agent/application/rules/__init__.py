"""确定性的应用层业务规则。"""

from job_agent.application.rules.application_status import (
    NORMAL_STATUS_CHAIN,
    TERMINAL_STATUSES,
    can_transition,
    is_submitted_or_later,
)

__all__ = [
    "NORMAL_STATUS_CHAIN",
    "TERMINAL_STATUSES",
    "can_transition",
    "is_submitted_or_later",
]
