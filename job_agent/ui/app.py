"""Streamlit 独立入口。"""

import streamlit as st

from job_agent.config import Settings
from job_agent.ui.bootstrap import create_service_bundle
from job_agent.ui.errors import to_ui_error
from job_agent.ui.navigation import render_navigation
from job_agent.ui.types import ServiceBundle


@st.cache_resource(show_spinner=False)
def _cached_bundle(settings: Settings) -> ServiceBundle:
    return create_service_bundle(settings)


def render_app(bundle: ServiceBundle) -> None:
    """渲染应用；显式参数便于组件测试注入 Service。"""

    try:
        render_navigation(bundle)
    except Exception as exc:
        error = to_ui_error(exc)
        st.error(
            f"页面暂时不可用：{error.message}\n\n"
            f"错误代码：{error.code} · trace_id：{error.trace_id}"
        )


def main() -> None:
    st.set_page_config(page_title="秋招投递智能体", page_icon="📋", layout="wide")
    try:
        settings = Settings.from_env()
        bundle = _cached_bundle(settings)
    except Exception as exc:
        error = to_ui_error(exc)
        st.error(
            f"UI 初始化失败：{error.message}\n\n"
            f"错误代码：{error.code} · trace_id：{error.trace_id}"
        )
        return
    render_app(bundle)


if __name__ == "__main__":
    main()


__all__ = ["main", "render_app"]
