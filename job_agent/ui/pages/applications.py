"""投递记录、状态更新与 Timeline 页面。"""

import streamlit as st

from job_agent.application.contracts import ApplicationTransitionRequest
from job_agent.ui.pages.common import initialize_operation_state, show_empty, show_error
from job_agent.ui.types import ServiceBundle
from job_agent.ui.view_models import (
    allowed_target_statuses,
    format_datetime,
    reason_is_safe,
    safe_display_url,
    safe_event_details,
)


def render(bundle: ServiceBundle, candidate_id: str) -> None:
    st.title("投递记录与 Timeline")
    st.caption(f"当前 Candidate：{candidate_id}")
    initialize_operation_state("application_operation_state")
    try:
        page = bundle.applications.list_applications(candidate_id, limit=100)
    except Exception as exc:
        show_error(exc)
        return

    if not page.items:
        show_empty("当前 Candidate 尚无投递记录。", "在岗位录入页将岗位加入待投池。")
        return

    job_labels: dict[str, str] = {}
    for application in page.items:
        try:
            job = bundle.jobs.get_job(application.job_id)
            job_labels[application.id] = (
                f"{job.company} · {job.title}"
                if job is not None
                else f"岗位 {application.job_id}"
            )
        except Exception as exc:
            show_error(exc)
            job_labels[application.id] = f"岗位 {application.job_id}"

    selected_id = st.selectbox(
        "选择投递",
        [item.id for item in page.items],
        format_func=lambda value: f"{job_labels[value]} · {value}",
        key="selected_application_id",
    )
    try:
        current = bundle.applications.get_application(selected_id)
    except Exception as exc:
        show_error(exc)
        return
    if current is None:
        st.warning("投递记录已变化，请刷新页面。")
        return

    st.subheader("投递详情")
    st.write(f"公司/岗位：{job_labels[current.id]}")
    st.write(f"当前状态：**{current.status.value}**")
    st.write(f"申请 URL：{safe_display_url(current.application_url)}")
    st.write(f"最后更新：{format_datetime(current.last_updated_at)}")
    st.write(f"提交时间：{format_datetime(current.submitted_at)}")

    targets = allowed_target_statuses(current.status)
    if targets:
        with st.form("application_status_form"):
            target = st.selectbox(
                "合法目标状态",
                targets,
                format_func=lambda value: value.value,
            )
            source = st.text_input("状态来源", value="streamlit_ui")
            reason = st.text_area("原因/备注（不得包含认证数据）")
            transition_clicked = st.form_submit_button("更新状态")
        if transition_clicked:
            try:
                if not reason_is_safe(reason):
                    raise ValueError("原因中不得包含认证数据")
                st.session_state["application_operation_state"] = "running"
                request = ApplicationTransitionRequest(
                    application_id=current.id,
                    to_status=target,
                    source=source,
                    details={"reason": reason.strip()} if reason.strip() else {},
                )
                with st.spinner("正在更新状态并写入事件……"):
                    bundle.applications.transition_status(request)
                    current = bundle.applications.get_application(current.id)
                    timeline = bundle.applications.list_application_events(
                        selected_id, limit=100
                    )
                st.session_state["application_operation_state"] = "succeeded"
                st.success(
                    f"状态已更新为 {current.status.value if current else '未知'}；"
                    f"Timeline 共 {timeline.total} 条。"
                )
            except Exception as exc:
                st.session_state["application_operation_state"] = "failed"
                show_error(exc)
    else:
        st.info("当前为终止状态；T007 不开放普通恢复操作。")

    st.subheader("Timeline")
    try:
        timeline = bundle.applications.list_application_events(selected_id, limit=100)
    except Exception as exc:
        show_error(exc)
        return
    for event in timeline.items:
        from_status = event.from_status.value if event.from_status else "—"
        to_status = event.to_status.value if event.to_status else "—"
        with st.expander(
            f"{format_datetime(event.occurred_at)} · {event.event_type} · "
            f"{from_status} → {to_status}"
        ):
            st.write(f"来源：{event.source}")
            st.json(safe_event_details(event.details))


__all__ = ["render"]
