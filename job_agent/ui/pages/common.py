"""页面共享的安全提示组件。"""

import streamlit as st

from job_agent.ui.errors import to_ui_error


def show_error(exc: Exception) -> None:
    error = to_ui_error(exc)
    st.error(
        f"{error.message}\n\n错误代码：{error.code} · trace_id：{error.trace_id}"
    )


def show_empty(message: str, next_step: str) -> None:
    st.info(f"{message}\n\n下一步：{next_step}")


def initialize_operation_state(key: str) -> None:
    """操作状态仅用于页面反馈，不作为业务事实。"""

    if key not in st.session_state:
        st.session_state[key] = "idle"


__all__ = ["initialize_operation_state", "show_empty", "show_error"]
