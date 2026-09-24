"""证据库页面。"""

import streamlit as st

from job_agent.domain import EvidenceVerification
from job_agent.ui.pages.common import initialize_operation_state, show_empty, show_error
from job_agent.ui.types import ServiceBundle
from job_agent.ui.view_models import format_datetime, safe_source_name


_FILTERS = {
    "全部审核数据": None,
    "仅 UNVERIFIED": EvidenceVerification.UNVERIFIED,
    "仅 VERIFIED": EvidenceVerification.VERIFIED,
    "仅 REJECTED": EvidenceVerification.REJECTED,
    "VERIFIED 正式数据": "formal",
}


def render(bundle: ServiceBundle, candidate_id: str) -> None:
    st.title("证据库")
    st.caption(f"当前 Candidate：{candidate_id}")
    initialize_operation_state("evidence_operation_state")
    selected = st.selectbox("数据视图", list(_FILTERS), key="evidence_filter")
    try:
        filter_value = _FILTERS[selected]
        if filter_value == "formal":
            page = bundle.profile.list_verified_evidence(candidate_id, limit=100)
            st.caption("正式数据固定通过 VERIFIED 专用 Service 查询。")
        elif isinstance(filter_value, EvidenceVerification):
            page = bundle.profile.list_evidence_by_verification(
                candidate_id, filter_value, limit=100
            )
        else:
            page = bundle.profile.list_evidence_for_review(candidate_id, limit=100)
    except Exception as exc:
        show_error(exc)
        return

    st.write(f"共 {page.total} 条")
    if not page.items:
        show_empty("当前视图没有 Evidence。", "先通过结构化导入创建待审核证据。")
        return

    for evidence in page.items:
        with st.expander(
            f"{evidence.category} · {evidence.verification.value} · {evidence.id}"
        ):
            st.write(evidence.content)
            st.write(f"技能：{', '.join(evidence.skills) or '—'}")
            st.write(f"指标：{', '.join(evidence.metrics) or '—'}")
            st.write(f"来源：{safe_source_name(evidence.source_resume_id)}")
            st.write(f"更新时间：{format_datetime(evidence.updated_at)}")
            if evidence.verification is EvidenceVerification.UNVERIFIED:
                if st.button("显式验证", key=f"verify:{evidence.id}"):
                    try:
                        st.session_state["evidence_operation_state"] = "running"
                        with st.spinner("正在验证 Evidence……"):
                            bundle.profile.verify_evidence(evidence.id)
                            refreshed = bundle.profile.list_evidence_for_review(
                                candidate_id, limit=100
                            )
                        st.session_state["evidence_operation_state"] = "succeeded"
                        st.success(
                            f"Evidence 已验证；数据库当前共有 {refreshed.total} 条审核数据。"
                        )
                    except Exception as exc:
                        st.session_state["evidence_operation_state"] = "failed"
                        show_error(exc)

    st.caption("Evidence 编辑和拒绝操作尚无 T005 Service 支持，本页面不绕过 Service。")


__all__ = ["render"]
