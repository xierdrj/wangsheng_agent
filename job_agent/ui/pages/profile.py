"""个人资料页面。"""

from datetime import datetime, timezone

import streamlit as st

from job_agent.ui.pages.common import initialize_operation_state, show_empty, show_error
from job_agent.ui.types import ServiceBundle
from job_agent.ui.view_models import (
    build_candidate_profile,
    model_list_json,
    safe_profile_view,
)


def _lines(values: list[str]) -> str:
    return "\n".join(values)


def render(bundle: ServiceBundle, candidate_id: str) -> None:
    st.title("个人资料")
    st.caption(f"当前 Candidate：{candidate_id}")
    initialize_operation_state("profile_operation_state")
    try:
        current = bundle.profile.get_profile(candidate_id)
    except Exception as exc:
        show_error(exc)
        current = None

    if current is None:
        show_empty("当前 Candidate 尚未创建。", "填写下方表单并先生成预览。")
    else:
        st.subheader("数据库中的当前资料")
        st.json(safe_profile_view(current))

    with st.form("profile_form"):
        st.subheader("基本信息与求职偏好")
        full_name = st.text_input(
            "姓名",
            value=current.basic_info.full_name if current else "",
        )
        city = st.text_input(
            "城市",
            value=current.basic_info.city or "" if current else "",
        )
        roles = st.text_area(
            "目标岗位（每行一个）",
            value=_lines(current.preferences.roles) if current else "",
        )
        locations = st.text_area(
            "目标地点（每行一个）",
            value=_lines(current.preferences.locations) if current else "",
        )
        industries = st.text_area(
            "目标行业（每行一个）",
            value=_lines(current.preferences.industries) if current else "",
        )
        skills = st.text_area(
            "技能（每行一个）",
            value=_lines(current.skills) if current else "",
        )
        awards = st.text_area(
            "奖项（每行一个）",
            value=_lines(current.awards) if current else "",
        )
        graduation_year = st.text_input(
            "毕业年份",
            value=(
                str(current.preferences.graduation_year)
                if current and current.preferences.graduation_year
                else ""
            ),
        )
        salary_expectation = st.text_input(
            "薪资期望",
            value=current.preferences.salary_expectation or "" if current else "",
        )
        excluded_companies = st.text_area(
            "排除公司（每行一个）",
            value=_lines(current.preferences.excluded_companies) if current else "",
        )
        accepts_travel = st.checkbox(
            "接受出差",
            value=bool(current.preferences.accepts_travel) if current else False,
        )
        accepts_relocation = st.checkbox(
            "接受异地调动",
            value=bool(current.preferences.accepts_relocation) if current else False,
        )

        st.subheader("结构化经历")
        st.caption("以下字段必须是 JSON 数组，保存前会逐项通过 Pydantic 校验。")
        education_json = st.text_area(
            "教育经历 JSON",
            value=model_list_json(current.education) if current else "[]",
            height=150,
        )
        internships_json = st.text_area(
            "实习经历 JSON",
            value=model_list_json(current.internships) if current else "[]",
            height=150,
        )
        projects_json = st.text_area(
            "项目经历 JSON",
            value=model_list_json(current.projects) if current else "[]",
            height=150,
        )

        st.subheader("敏感字段（独立编辑）")
        st.caption(
            "邮箱和手机号默认不回显；编辑时输入新值，留空则保留数据库原值。"
            "当前页面不支持清空这两个字段。"
        )
        email = st.text_input("邮箱", value="", type="password")
        phone = st.text_input("手机号", value="", type="password")
        preview_clicked = st.form_submit_button("生成保存预览")

    preview_key = f"profile_preview:{candidate_id}"
    if preview_clicked:
        try:
            preview = build_candidate_profile(
                {
                    "candidate_id": candidate_id,
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "city": city,
                    "roles": roles,
                    "locations": locations,
                    "industries": industries,
                    "skills": skills,
                    "awards": awards,
                    "graduation_year": graduation_year,
                    "salary_expectation": salary_expectation,
                    "excluded_companies": excluded_companies,
                    "accepts_travel": accepts_travel,
                    "accepts_relocation": accepts_relocation,
                    "education_json": education_json,
                    "internships_json": internships_json,
                    "projects_json": projects_json,
                },
                current=current,
                now=datetime.now(timezone.utc),
            )
            # Session State 只保存确认状态，不保存 Profile 或未脱敏联系方式。
            st.session_state[preview_key] = True
            st.session_state["profile_operation_state"] = "idle"
        except Exception as exc:
            st.session_state["profile_operation_state"] = "failed"
            show_error(exc)

    if st.session_state.get(preview_key):
        try:
            preview = build_candidate_profile(
                {
                    "candidate_id": candidate_id,
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "city": city,
                    "roles": roles,
                    "locations": locations,
                    "industries": industries,
                    "skills": skills,
                    "awards": awards,
                    "graduation_year": graduation_year,
                    "salary_expectation": salary_expectation,
                    "excluded_companies": excluded_companies,
                    "accepts_travel": accepts_travel,
                    "accepts_relocation": accepts_relocation,
                    "education_json": education_json,
                    "internships_json": internships_json,
                    "projects_json": projects_json,
                },
                current=current,
                now=datetime.now(timezone.utc),
            )
        except Exception as exc:
            del st.session_state[preview_key]
            st.session_state["profile_operation_state"] = "failed"
            show_error(exc)
            return

        st.subheader("保存前预览")
        st.json(safe_profile_view(preview))
        confirm_col, cancel_col = st.columns(2)
        if confirm_col.button("确认保存", key="confirm_profile"):
            try:
                st.session_state["profile_operation_state"] = "running"
                with st.spinner("正在保存个人资料……"):
                    existing = bundle.profile.get_profile(candidate_id)
                    if existing is None:
                        bundle.profile.create_profile(preview)
                    else:
                        bundle.profile.update_profile(candidate_id, preview)
                    refreshed = bundle.profile.get_profile(candidate_id)
                st.session_state["profile_operation_state"] = "succeeded"
                del st.session_state[preview_key]
                st.success("个人资料已保存并从数据库重新读取。")
                if refreshed is not None:
                    st.json(safe_profile_view(refreshed))
            except Exception as exc:
                st.session_state["profile_operation_state"] = "failed"
                show_error(exc)
        if cancel_col.button("取消预览", key="cancel_profile"):
            del st.session_state[preview_key]
            st.session_state["profile_operation_state"] = "idle"
            st.info("已取消，本次预览未写入数据库。")


__all__ = ["render"]
