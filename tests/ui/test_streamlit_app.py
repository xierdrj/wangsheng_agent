"""T007 Streamlit 导航、关键交互和安全错误测试。"""

from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

from job_agent.config import Settings
from job_agent.domain import EvidenceVerification, ResumeEvidence
from job_agent.ui.bootstrap import create_service_bundle


APP_PATH = str(Path(__file__).parents[2] / "job_agent" / "ui" / "app.py")


def _set_ui_environment(monkeypatch, tmp_path: Path) -> Settings:
    database_path = tmp_path / "apptest.sqlite3"
    data_dir = tmp_path / "data"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("SNAPSHOT_DIR", str(data_dir / "snapshots"))
    monkeypatch.setenv("PLAYWRIGHT_AUTH_DIR", str(data_dir / "playwright"))
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    return Settings.from_env()


def _widget_by_label(widgets, label: str):
    matches = [widget for widget in widgets if widget.label == label]
    assert len(matches) == 1, f"未找到唯一控件: {label}"
    return matches[0]


def _button(at: AppTest, label: str):
    return _widget_by_label(at.button, label)


def test_empty_database_can_navigate_all_five_pages(monkeypatch, tmp_path) -> None:
    _set_ui_environment(monkeypatch, tmp_path)
    at = AppTest.from_file(APP_PATH).run(timeout=15)
    assert not at.exception
    assert [item.value for item in at.title if item.value == "Dashboard"] == [
        "Dashboard"
    ]
    assert at.sidebar.radio[0].options == [
        "Dashboard",
        "个人资料",
        "证据库",
        "岗位录入",
        "投递记录",
    ]

    expected_titles = {
        "Dashboard": "Dashboard",
        "个人资料": "个人资料",
        "证据库": "证据库",
        "岗位录入": "岗位录入",
        "投递记录": "投递记录与 Timeline",
    }
    for page, title in expected_titles.items():
        at.sidebar.radio[0].set_value(page)
        at.run(timeout=15)
        assert not at.exception
        assert title in [item.value for item in at.title]

    st.cache_resource.clear()


def test_profile_evidence_job_pool_application_and_timeline_interactions(
    monkeypatch,
    tmp_path,
) -> None:
    settings = _set_ui_environment(monkeypatch, tmp_path)
    at = AppTest.from_file(APP_PATH).run(timeout=15)

    at.sidebar.radio[0].set_value("个人资料")
    at.run(timeout=15)
    _widget_by_label(at.text_input, "姓名").set_value("脱敏候选人")
    _widget_by_label(at.text_input, "邮箱").set_value("ui@example.com")
    _widget_by_label(at.text_input, "手机号").set_value("13800000000")
    _widget_by_label(at.text_area, "目标岗位（每行一个）").set_value(
        "Python 工程师"
    )
    _button(at, "生成保存预览").click()
    at.run(timeout=15)
    assert not at.exception
    _button(at, "取消预览").click()
    at.run(timeout=15)
    assert not at.exception
    cancelled = create_service_bundle(settings)
    try:
        assert cancelled.profile.get_profile("candidate-1") is None
    finally:
        cancelled.close()

    _button(at, "生成保存预览").click()
    at.run(timeout=15)
    _button(at, "确认保存").click()
    at.run(timeout=15)
    assert not at.exception
    assert any("个人资料已保存" in item.value for item in at.success)
    assert "13800000000" not in "\n".join(
        str(item.value) for item in [*at.json, *at.markdown]
    )

    external = create_service_bundle(settings)
    try:
        created_profile = external.profile.get_profile("candidate-1")
        assert created_profile is not None
        created_at = created_profile.created_at
        external.profile.add_evidence(
            ResumeEvidence(
                id="evidence-ui",
                candidate_id="candidate-1",
                category="project",
                content="完成脱敏 UI 项目",
                verification=EvidenceVerification.UNVERIFIED,
                created_at=external.profile.get_profile("candidate-1").created_at,
                updated_at=external.profile.get_profile("candidate-1").updated_at,
            )
        )
    finally:
        external.close()

    at.sidebar.radio[0].set_value("Dashboard")
    at.run(timeout=15)
    at.sidebar.radio[0].set_value("个人资料")
    at.run(timeout=15)
    _widget_by_label(at.text_input, "姓名").set_value("脱敏候选人（更新）")
    _widget_by_label(at.text_input, "邮箱").set_value("")
    _widget_by_label(at.text_input, "手机号").set_value("")
    _button(at, "生成保存预览").click()
    at.run(timeout=15)
    _button(at, "确认保存").click()
    at.run(timeout=15)
    assert not at.exception
    edited_bundle = create_service_bundle(settings)
    try:
        edited = edited_bundle.profile.get_profile("candidate-1")
        assert edited is not None
        assert edited.basic_info.full_name == "脱敏候选人（更新）"
        assert str(edited.basic_info.email) == "ui@example.com"
        assert edited.basic_info.phone == "13800000000"
        assert edited.created_at == created_at
        assert edited.updated_at > created_at
    finally:
        edited_bundle.close()

    at.sidebar.radio[0].set_value("证据库")
    at.run(timeout=15)
    assert not at.exception
    _button(at, "显式验证").click()
    at.run(timeout=15)
    assert not at.exception
    assert any("Evidence 已验证" in item.value for item in at.success)
    at.selectbox[0].set_value("VERIFIED 正式数据")
    at.run(timeout=15)
    assert any("evidence-ui" in item.label for item in at.expander)

    at.sidebar.radio[0].set_value("岗位录入")
    at.run(timeout=15)
    _widget_by_label(at.text_input, "岗位 ID").set_value("job-ui")
    _widget_by_label(at.text_input, "公司").set_value("脱敏科技")
    _widget_by_label(at.text_input, "岗位名称").set_value("Python 工程师")
    _widget_by_label(at.text_input, "岗位 URL").set_value(
        "https://jobs.example.com/ui"
    )
    _widget_by_label(at.text_area, "原始 JD").set_value("负责后端服务开发")
    _widget_by_label(
        at.text_input, "fingerprint（必填，由用户或上游提供）"
    ).set_value("fingerprint-ui")
    _button(at, "保存岗位").click()
    at.run(timeout=15)
    assert not at.exception
    assert any("岗位已保存" in item.value for item in at.success)

    _button(at, "加入待投池").click()
    at.run(timeout=15)
    assert not at.exception
    assert any("岗位已加入待投池" in item.value for item in at.success)
    _button(at, "加入待投池").click()
    at.run(timeout=15)
    assert not at.exception
    assert not at.error

    at.sidebar.radio[0].set_value("投递记录")
    at.run(timeout=15)
    assert not at.exception
    assert any("APPLICATION_CREATED" in item.label for item in at.expander)
    _button(at, "更新状态").click()
    at.run(timeout=15)
    assert not at.exception
    assert any("状态已更新为 PREPARING" in item.value for item in at.success)
    assert any("STATUS_CHANGED" in item.label for item in at.expander)

    at.sidebar.radio[0].set_value("岗位录入")
    at.run(timeout=15)
    _button(at, "加入待投池").click()
    at.run(timeout=15)
    assert not at.exception
    assert not at.error

    verifier = create_service_bundle(settings)
    try:
        profile = verifier.profile.get_profile("candidate-1")
        jobs = verifier.jobs.list_jobs(limit=100)
        applications = verifier.applications.list_applications(
            "candidate-1", limit=100
        )
        assert profile is not None
        assert profile.basic_info.full_name == "脱敏候选人（更新）"
        assert jobs.total == 1
        assert applications.total == 1
        timeline = verifier.applications.list_application_events(
            applications.items[0].id
        )
        assert [event.event_type for event in timeline.items] == [
            "APPLICATION_CREATED",
            "STATUS_CHANGED",
        ]
    finally:
        verifier.close()
        st.cache_resource.clear()


def test_service_exception_is_rendered_as_safe_traceable_error() -> None:
    source = '''
from job_agent.ui.app import render_app
from job_agent.ui.types import ServiceBundle

class FailingDashboard:
    def get_summary(self, candidate_id):
        raise RuntimeError(
            "token=TEST_SECRET Cookie=COOKIE_SECRET "
            "Authorization=AUTH_SECRET sqlite:///private/database.db"
        )

class EmptyProfile:
    def get_profile(self, candidate_id):
        return None

bundle = ServiceBundle(
    profile=EmptyProfile(),
    jobs=object(),
    applications=object(),
    dashboard=FailingDashboard(),
)
render_app(bundle)
'''
    at = AppTest.from_string(source).run(timeout=15)
    assert not at.exception
    assert len(at.error) == 1
    message = at.error[0].value
    assert "trace_id" in message
    assert "TEST_SECRET" not in message
    assert "COOKIE_SECRET" not in message
    assert "AUTH_SECRET" not in message
    assert "sqlite:///" not in message
    assert "Traceback" not in message
