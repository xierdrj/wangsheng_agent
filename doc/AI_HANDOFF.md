# AI 开发接力记录

## 项目信息

- 仓库名称：wangsheng_agent
- Python 包名称：job_agent
- Python 要求：3.11+
- 当前稳定任务：T002
- 已完成任务：T001、T002
- 下一任务：T003
- 默认开发数据库：SQLite

## 当前实现状态

### T001：工程骨架

已完成：

- Python 包结构
- pyproject.toml
- 集中配置
- .env.example
- .gitignore
- 最小启动入口
- smoke test

### T002：领域模型

已完成：

- ApplicationStatus
- EvidenceVerification
- ReviewDecision
- BasicInfo
- Education
- Experience
- JobPreference
- CandidateProfile
- ResumeEvidence
- JobPosting
- MatchDimension
- MatchResult
- ResumeVersion
- ApplicationAnswer
- ApplicationRecord
- ApplicationEvent
- FormField

## 当前领域层规则

- 所有领域模型使用 Pydantic。
- 默认 extra="forbid"。
- 列表和字典使用 Field(default_factory=...)。
- datetime 字段要求携带有效时区。
- URL 只允许 HTTP(S)。
- 分数、权重和置信度具有范围约束。
- 枚举使用 StrEnum。
- 领域层不依赖 SQLAlchemy、Alembic、LangGraph、Playwright、Streamlit 或具体 LLM SDK。

## 最近验证结果

T002 完成时：

- 完整 pytest：19 passed
- 领域模型测试：16 passed
- T001 smoke test：3 passed
- compileall：通过
- python -m job_agent：通过
- git diff --check：通过

## 当前未实现

- 数据库连接和会话管理
- SQLAlchemy ORM
- 数据库迁移
- Repository
- 业务服务
- 岗位搜索与匹配
- LLM Agent
- LangGraph 业务图
- Playwright 自动化
- Streamlit 业务界面

## 当前风险和约束

1. 必须使用 Python 3.11+。
2. 当前本机指定环境为：
   C:\ProgramData\Miniconda3\envs\lc\python.exe
3. 默认 Python 3.9 不作为项目验收环境。
4. 不得在 .env.example 中保存真实密钥。
5. 不得提交 .env、数据库文件、缓存、Cookie 或个人信息。
6. 不得提前执行真实职位投递。
7. ruff 和 mypy 当前尚未配置。

## 下一任务

下一任务是：

T003：数据库与 ORM 持久化基础

T003 具体范围和验收要求见：

doc/tasks/T003.md

T003 不实现 Repository CRUD，Repository 放在 T004 或后续任务。

## 每次任务完成后的更新要求

每完成一个 Txxx，必须更新本文件中的：

- 当前稳定任务
- 已完成任务
- 新增公共接口
- 最近测试结果
- 已知风险
- 下一任务
