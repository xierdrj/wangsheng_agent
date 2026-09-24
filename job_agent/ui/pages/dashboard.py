"""Dashboard 页面。"""

import streamlit as st

from job_agent.ui.pages.common import show_empty, show_error
from job_agent.ui.types import ServiceBundle
from job_agent.ui.view_models import format_datetime, safe_event_details


def render(bundle: ServiceBundle, candidate_id: str) -> None:
    st.title("Dashboard")
    st.caption(f"当前 Candidate：{candidate_id}")
    try:
        if bundle.profile.get_profile(candidate_id) is None:
            st.info("当前 Candidate 尚未创建，请前往“个人资料”页面创建。")
    except Exception as exc:
        show_error(exc)
    try:
        summary = bundle.dashboard.get_summary(candidate_id)
    except Exception as exc:  # 页面边界必须防止单个组件拖垮导航
        show_error(exc)
        return

    first_row = st.columns(4)
    first_row[0].metric("本周新增岗位", summary.jobs_added_this_week)
    first_row[1].metric("待审核 Evidence", summary.evidence_pending_review)
    first_row[2].metric("待提交申请", summary.applications_pending_submission)
    first_row[3].metric("已投递", summary.applications_submitted)
    second_row = st.columns(3)
    second_row[0].metric("在线测评", summary.online_assessments)
    second_row[1].metric("面试", summary.interviews)
    second_row[2].metric("Offer", summary.offers)

    st.subheader("最近投递事件")
    if not summary.recent_events:
        show_empty("暂无投递事件。", "在岗位录入页将岗位加入待投池。")
    for event in summary.recent_events:
        from_status = event.from_status.value if event.from_status else "—"
        to_status = event.to_status.value if event.to_status else "—"
        with st.expander(
            f"{event.event_type} · {from_status} → {to_status} · "
            f"{format_datetime(event.occurred_at)}"
        ):
            st.write(f"来源：{event.source}")
            st.json(safe_event_details(event.details))

    st.subheader("未来 14 天即将截止")
    if not summary.upcoming_jobs:
        show_empty("暂无明确截止日期的临近岗位。", "在岗位录入页补充 deadline。")
    for job in summary.upcoming_jobs:
        st.write(
            f"**{job.company} · {job.title}** — {format_datetime(job.deadline)}"
        )

    st.caption("高匹配岗位需要后续 Match 能力，本页面不生成或伪造匹配结果。")


__all__ = ["render"]
