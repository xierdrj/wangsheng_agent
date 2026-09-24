"""T007 UI 装配刷新持久化与导入无副作用测试。"""

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys

from job_agent.application.contracts import AddToApplicationPoolRequest
from job_agent.config import Settings
from job_agent.domain import (
    BasicInfo,
    CandidateProfile,
    EvidenceVerification,
    JobPosting,
    JobPreference,
    ResumeEvidence,
)
from job_agent.ui.bootstrap import create_service_bundle


NOW = datetime(2026, 9, 23, 8, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).parents[2]


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        database_url=f"sqlite:///{tmp_path / 'ui-persistence.sqlite3'}",
        data_dir=tmp_path / "data",
        snapshot_dir=tmp_path / "snapshots",
        playwright_auth_dir=tmp_path / "playwright",
    )


def test_recreated_service_bundle_reads_persisted_ui_business_data(tmp_path) -> None:
    settings = _settings(tmp_path)
    first = create_service_bundle(settings)
    try:
        profile = first.profile.create_profile(
            CandidateProfile(
                id="candidate-refresh",
                basic_info=BasicInfo(
                    full_name="脱敏候选人",
                    email="refresh@example.com",
                    phone="13800000000",
                ),
                preferences=JobPreference(roles=["Python 工程师"]),
                created_at=NOW,
                updated_at=NOW,
            )
        )
        evidence = first.profile.add_evidence(
            ResumeEvidence(
                id="evidence-refresh",
                candidate_id=profile.id,
                category="project",
                content="完成脱敏项目",
                verification=EvidenceVerification.UNVERIFIED,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        first.profile.verify_evidence(evidence.id)
        job = first.jobs.save_manual_job(
            JobPosting(
                id="job-refresh",
                company="脱敏科技",
                title="Python 工程师",
                url="https://jobs.example.com/refresh",
                source="manual",
                raw_jd="负责后端开发",
                fingerprint="refresh-fingerprint",
                discovered_at=NOW,
            )
        )
        application = first.applications.add_to_application_pool(
            AddToApplicationPoolRequest(
                application_id="application-refresh",
                candidate_id=profile.id,
                job_id=job.id,
                application_url=job.url,
                source="streamlit_ui",
            )
        )
    finally:
        first.close()

    second = create_service_bundle(settings)
    try:
        assert second.profile.get_profile(profile.id) is not None
        verified = second.profile.list_verified_evidence(profile.id)
        assert [item.id for item in verified.items] == [evidence.id]
        assert second.jobs.get_job(job.id) is not None
        assert second.applications.get_application(application.id) is not None
        timeline = second.applications.list_application_events(application.id)
        assert timeline.total == 1
        assert timeline.items[0].event_type == "APPLICATION_CREATED"
    finally:
        second.close()


def test_importing_ui_modules_has_no_database_or_session_state_side_effect(
    tmp_path,
) -> None:
    database_path = tmp_path / "import-only.sqlite3"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path}"
    environment["PYTHONPATH"] = str(ROOT)
    code = (
        "import sqlalchemy; "
        "sqlalchemy.create_engine = lambda *args, **kwargs: "
        "(_ for _ in ()).throw(AssertionError('导入阶段禁止创建 Engine')); "
        "import streamlit as st; "
        "import job_agent.ui; "
        "import job_agent.ui.app; "
        "import job_agent.ui.bootstrap; "
        "import job_agent.ui.navigation; "
        "assert not dict(st.session_state)"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert not database_path.exists()
