"""Streamlit 页面导航。"""

from collections.abc import Callable

import streamlit as st

from job_agent.ui.pages import applications, dashboard, evidence, jobs, profile
from job_agent.ui.types import ServiceBundle


PageRenderer = Callable[[ServiceBundle, str], None]

PAGES: dict[str, PageRenderer] = {
    "Dashboard": dashboard.render,
    "个人资料": profile.render,
    "证据库": evidence.render,
    "岗位录入": jobs.render,
    "投递记录": applications.render,
}


def render_navigation(bundle: ServiceBundle) -> None:
    st.sidebar.title("秋招投递智能体")
    candidate_id = st.sidebar.text_input(
        "当前 candidate_id",
        value="candidate-1",
        key="active_candidate_id",
    ).strip()
    page_name = st.sidebar.radio("页面", list(PAGES), key="active_page")
    if not candidate_id:
        st.warning("请输入非空 candidate_id。")
        return
    PAGES[page_name](bundle, candidate_id)


__all__ = ["PAGES", "render_navigation"]
