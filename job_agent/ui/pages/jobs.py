"""岗位手动录入和加入待投池页面。"""

from datetime import datetime, timezone

import streamlit as st

from job_agent.application.contracts import AddToApplicationPoolRequest
from job_agent.ui.pages.common import initialize_operation_state, show_empty, show_error
from job_agent.ui.types import ServiceBundle
from job_agent.ui.view_models import (
    build_job_posting,
    format_datetime,
    make_application_id,
    safe_display_url,
    url_contains_sensitive_data,
)


def render(bundle: ServiceBundle, candidate_id: str) -> None:
    st.title("岗位录入")
    st.caption("仅支持手动录入已结构化岗位；fingerprint 不会自动生成。")
    initialize_operation_state("job_operation_state")
    initialize_operation_state("pool_operation_state")

    with st.form("job_form"):
        job_id = st.text_input("岗位 ID")
        external_job_id = st.text_input("外部岗位 ID（可选）")
        company = st.text_input("公司")
        title = st.text_input("岗位名称")
        location = st.text_input("地点")
        url = st.text_input("岗位 URL")
        source = st.text_input("岗位来源", value="manual")
        raw_jd = st.text_area("原始 JD")
        responsibilities = st.text_area("职责（每行一个）")
        requirements = st.text_area("必需条件（每行一个）")
        preferred_qualifications = st.text_area("优先条件（每行一个）")
        skills = st.text_area("技能（每行一个）")
        education_requirement = st.text_input("学历要求")
        graduation_requirement = st.text_input("毕业年份要求")
        experience_requirement = st.text_input("经验要求")
        deadline = st.text_input(
            "截止时间（ISO 8601，可选）",
            placeholder="2026-10-31T23:59:00+08:00",
        )
        fingerprint = st.text_input("fingerprint（必填，由用户或上游提供）")
        save_clicked = st.form_submit_button("保存岗位")

    if save_clicked:
        try:
            st.session_state["job_operation_state"] = "running"
            payload = build_job_posting(
                {
                    "id": job_id,
                    "external_job_id": external_job_id,
                    "company": company,
                    "title": title,
                    "location": location,
                    "url": url,
                    "source": source,
                    "raw_jd": raw_jd,
                    "responsibilities": responsibilities,
                    "requirements": requirements,
                    "preferred_qualifications": preferred_qualifications,
                    "skills": skills,
                    "education_requirement": education_requirement,
                    "graduation_requirement": graduation_requirement,
                    "experience_requirement": experience_requirement,
                    "deadline": deadline,
                    "fingerprint": fingerprint,
                },
                now=datetime.now(timezone.utc),
            )
            with st.spinner("正在保存岗位……"):
                saved = bundle.jobs.save_manual_job(payload)
                refreshed = bundle.jobs.get_job(saved.id)
            st.session_state["job_operation_state"] = "succeeded"
            st.success("岗位已保存并按 fingerprint 去重。")
            if refreshed is not None:
                st.json(refreshed.model_dump(mode="json"))
        except Exception as exc:
            st.session_state["job_operation_state"] = "failed"
            show_error(exc)

    st.subheader("已保存岗位")
    try:
        jobs_page = bundle.jobs.list_jobs(limit=100)
    except Exception as exc:
        show_error(exc)
        return
    if not jobs_page.items:
        show_empty("数据库中暂无岗位。", "填写上方表单手动保存一个岗位。")
        return

    for job in jobs_page.items:
        with st.expander(f"{job.company} · {job.title} · {job.id}"):
            st.write(f"地点：{job.location or '—'}")
            st.write(f"来源：{job.source}")
            st.write(f"截止：{format_datetime(job.deadline)}")
            st.write(f"fingerprint：{job.fingerprint}")
            st.write(f"岗位地址：{safe_display_url(job.url)}")
            if url_contains_sensitive_data(job.url):
                st.warning("该 URL 含认证参数，已禁用页面跳转。")
            else:
                st.link_button("打开岗位页面", job.url)

    profile = None
    try:
        profile = bundle.profile.get_profile(candidate_id)
    except Exception as exc:
        show_error(exc)
    if profile is None:
        st.info("创建当前 Candidate Profile 后，才能将岗位加入待投池。")
        return

    st.subheader("加入待投池")
    labels = {job.id: f"{job.company} · {job.title} · {job.id}" for job in jobs_page.items}
    selected_id = st.selectbox(
        "选择岗位",
        list(labels),
        format_func=lambda value: labels[value],
        key="pool_job_id",
    )
    selected_job = next(job for job in jobs_page.items if job.id == selected_id)
    application_url = st.text_input(
        "申请 URL（留空使用岗位 URL）", key="pool_application_url"
    )
    resume_version_id = st.text_input(
        "简历版本 ID（可选）", key="pool_resume_version_id"
    )
    pool_source = st.text_input(
        "操作来源", value="streamlit_ui", key="pool_source"
    )
    if st.button("加入待投池", key="add_to_pool"):
        try:
            st.session_state["pool_operation_state"] = "running"
            resolved_application_url = application_url.strip() or selected_job.url
            if url_contains_sensitive_data(resolved_application_url):
                raise ValueError("申请 URL 不得包含认证信息")
            request = AddToApplicationPoolRequest(
                application_id=make_application_id(candidate_id, selected_job.id),
                candidate_id=candidate_id,
                job_id=selected_job.id,
                application_url=resolved_application_url,
                resume_version_id=resume_version_id.strip() or None,
                source=pool_source,
            )
            with st.spinner("正在加入待投池……"):
                application = bundle.applications.add_to_application_pool(request)
                refreshed = bundle.applications.get_application(application.id)
            st.session_state["pool_operation_state"] = "succeeded"
            st.success("岗位已加入待投池；重复操作不会生成第二条投递。")
            if refreshed is not None:
                st.json(refreshed.model_dump(mode="json"))
        except Exception as exc:
            st.session_state["pool_operation_state"] = "failed"
            show_error(exc)


__all__ = ["render"]
