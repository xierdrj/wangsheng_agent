"""领域层枚举定义。"""

from enum import StrEnum


class ApplicationStatus(StrEnum):
    """投递主状态。"""

    DISCOVERED = "DISCOVERED"
    SHORTLISTED = "SHORTLISTED"
    PREPARING = "PREPARING"
    READY_TO_APPLY = "READY_TO_APPLY"
    SUBMITTED = "SUBMITTED"
    ONLINE_ASSESSMENT = "ONLINE_ASSESSMENT"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    CLOSED = "CLOSED"


class EvidenceVerification(StrEnum):
    """简历证据的核验状态。"""

    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class ReviewDecision(StrEnum):
    """人工审核决定。"""

    APPROVE = "APPROVE"
    EDIT = "EDIT"
    DEFER = "DEFER"
    CANCEL = "CANCEL"