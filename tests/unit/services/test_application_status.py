"""Application 状态转换纯函数测试。"""

import pytest

from job_agent.application.rules import (
    NORMAL_STATUS_CHAIN,
    TERMINAL_STATUSES,
    can_transition,
    is_submitted_or_later,
)
from job_agent.domain import ApplicationStatus


def test_status_rule_explicitly_covers_every_application_status() -> None:
    assert set(NORMAL_STATUS_CHAIN) | set(TERMINAL_STATUSES) == set(ApplicationStatus)
    assert set(NORMAL_STATUS_CHAIN).isdisjoint(TERMINAL_STATUSES)


def test_complete_transition_matrix_matches_the_explicit_rules() -> None:
    """穷举所有状态对，避免某个边界仅靠示例测试覆盖。"""

    normal_index = {
        status: index for index, status in enumerate(NORMAL_STATUS_CHAIN)
    }
    for from_status in ApplicationStatus:
        for to_status in ApplicationStatus:
            if from_status is to_status:
                expected = True
            elif from_status in TERMINAL_STATUSES:
                expected = False
            elif to_status in TERMINAL_STATUSES:
                expected = True
            else:
                expected = normal_index[to_status] > normal_index[from_status]
            assert can_transition(from_status, to_status) is expected, (
                f"状态转换矩阵不一致: {from_status.value} -> {to_status.value}"
            )


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    list(zip(NORMAL_STATUS_CHAIN, NORMAL_STATUS_CHAIN[1:])),
)
def test_adjacent_forward_transitions_are_allowed(from_status, to_status) -> None:
    assert can_transition(from_status, to_status) is True


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (ApplicationStatus.SHORTLISTED, ApplicationStatus.READY_TO_APPLY),
        (ApplicationStatus.SUBMITTED, ApplicationStatus.INTERVIEW),
        (ApplicationStatus.DISCOVERED, ApplicationStatus.OFFER),
    ],
)
def test_forward_skips_are_allowed(from_status, to_status) -> None:
    assert can_transition(from_status, to_status) is True


@pytest.mark.parametrize("terminal_status", sorted(TERMINAL_STATUSES, key=str))
def test_every_normal_status_can_enter_each_terminal_status(terminal_status) -> None:
    assert all(can_transition(status, terminal_status) for status in NORMAL_STATUS_CHAIN)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (ApplicationStatus.PREPARING, ApplicationStatus.SHORTLISTED),
        (ApplicationStatus.INTERVIEW, ApplicationStatus.ONLINE_ASSESSMENT),
        (ApplicationStatus.OFFER, ApplicationStatus.DISCOVERED),
    ],
)
def test_backward_transitions_are_rejected(from_status, to_status) -> None:
    assert can_transition(from_status, to_status) is False


@pytest.mark.parametrize("terminal_status", sorted(TERMINAL_STATUSES, key=str))
def test_terminal_status_cannot_recover_through_normal_rule(terminal_status) -> None:
    assert all(
        not can_transition(terminal_status, status) for status in NORMAL_STATUS_CHAIN
    )
    assert all(
        not can_transition(terminal_status, other)
        for other in TERMINAL_STATUSES
        if other is not terminal_status
    )


@pytest.mark.parametrize("status", list(ApplicationStatus))
def test_same_status_is_idempotent(status) -> None:
    assert can_transition(status, status) is True


def test_submitted_or_later_only_covers_post_submission_normal_states() -> None:
    assert is_submitted_or_later(ApplicationStatus.READY_TO_APPLY) is False
    assert is_submitted_or_later(ApplicationStatus.SUBMITTED) is True
    assert is_submitted_or_later(ApplicationStatus.ONLINE_ASSESSMENT) is True
    assert is_submitted_or_later(ApplicationStatus.INTERVIEW) is True
    assert is_submitted_or_later(ApplicationStatus.OFFER) is True
    assert is_submitted_or_later(ApplicationStatus.REJECTED) is False
