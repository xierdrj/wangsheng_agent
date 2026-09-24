# 秋招投递智能体

这是一个本地运行、由用户保持最终控制权的秋招工作流系统。当前已完成 T001～T008、T101 和 T102，包括领域与持久化基础、Profile/Job/Application Service、本地单用户 Streamlit 基础 UI、V0.1 全流程集成验收，以及 JD Parser 的 Fake 与 OpenAI-compatible 真实适配器；岗位搜索、匹配、自动化投递仍属于后续任务。

## 环境要求

- Python 3.11 或更高版本
- 推荐使用虚拟环境

## 安装

PowerShell 示例：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

安装命令会同时安装 Streamlit 1.39.x、直接依赖的 `httpx` 和 pytest 开发依赖。当前约束固定在已通过 Python 3.11、`streamlit.testing.v1` 和现有依赖集合验证的次版本，避免未审核的 UI 测试契约或传递依赖漂移；升级依赖时应单独执行兼容性与页面回归验证。

复制 `.env.example` 为 `.env` 后按需修改。`.env` 不会被提交到 Git。

## 启动

```powershell
python -m job_agent
```

也可以使用安装时注册的命令：

```powershell
job-agent
```

启动只会加载并校验配置，不会连接数据库、调用模型或打开浏览器。
启动入口会显式以 UTF-8 输出中文状态信息，避免 Windows 管道或非 UTF-8 默认代码页破坏文本。

### Streamlit UI

首次运行前可显式准备数据库：

```powershell
python -c "from job_agent.config import Settings; from job_agent.infrastructure.database import create_engine_from_settings, initialize_database; initialize_database(create_engine_from_settings(Settings.from_env()))"
```

启动 UI：

```powershell
python -m streamlit run job_agent/ui/app.py
```

默认访问地址为 `http://localhost:8501`。UI 启动入口独立于 `python -m job_agent`；只有实际执行 UI 后才会装配 Engine、初始化表并创建 Service。

## 测试

```powershell
python -m pytest -q
```

T102 的默认 Provider 是 Fake，普通测试完全离线。真实 OpenAI-compatible Parser 只有在同时设置 `LLM_ENABLED=true`、`LLM_PROVIDER=openai_compatible`、非 `unset` 的 `LLM_MODEL`、`LLM_API_KEY` 和显式 `LLM_BASE_URL` 后才会在 `parse()` 时请求；Base URL 只填写 API 根地址，适配器会追加一次 `/chat/completions`。请求只发送原始 JD，不发送 Profile、Evidence、来源元数据或 trace_id，解析结果不会自动保存 JobPosting。

T102 离线专项测试：

```powershell
python -m pytest tests\unit\infrastructure\test_openai_compatible_jd_parser.py tests\unit\infrastructure\test_jd_parser_prompt.py -q
```

真实 smoke test 不属于普通 pytest，也不应把密钥写入仓库、命令行、日志或测试输出；应在本机临时设置全部配置后单独运行。默认配置和 `python -m job_agent` 不会连接 Provider。

V0.1 端到端验收可单独运行：

```powershell
python -m pytest tests\e2e\test_v01_workflow.py -q
```

该测试从 pytest 临时目录中的空 SQLite 数据库开始，使用真实 Service、Repository、Unit of Work 和 Dashboard Reader，验收 Profile → Evidence → Job → Application → Event → Dashboard → ServiceBundle 重建读取的完整闭环。测试不会读取或修改 `data/job_agent.db`。完整回归还覆盖 T001 smoke test、T002 领域模型、T003 临时 SQLite 数据库与迁移、T004 Repository、T005/T006 Service，以及 T007 ViewModel、Dashboard 聚合、刷新持久化和 Streamlit AppTest 关键交互。

## 数据库

默认数据库地址来自 `DATABASE_URL`，默认值为 `sqlite:///./data/job_agent.db`。模块导入不会创建数据库；可显式初始化当前 ORM 表：

```powershell
python -c "from job_agent.config import Settings; from job_agent.infrastructure.database import create_engine_from_settings, initialize_database; initialize_database(create_engine_from_settings(Settings.from_env()))"
```

使用 Alembic 迁移时：

```powershell
alembic upgrade head
alembic downgrade base
```

初始 revision 使用固定的 `op.create_table`、`op.create_index` 和反向删除操作，不依赖未来 ORM metadata，因此可以复现 T003 时的历史结构。

测试始终使用临时 SQLite 数据库，不读写默认 `data/job_agent.db`。

## 当前范围

已完成：工程目录、`pyproject.toml`、配置对象、`.env.example`、`.gitignore`、最小启动入口、领域枚举、Pydantic Schema、SQLAlchemy ORM、数据库初始化、Alembic 初始迁移、Repository 接口/实现和单元/集成测试；T102 新增严格的 Provider 输出 Schema、`jd-parser-v1` Prompt 和同步 httpx 适配器。

Repository 通过显式接收共享 `Session` 工作，不自行 `commit`；由外层 `session_scope` 统一提交或回滚。接口返回领域模型和 `Page[T]`，SQLAlchemy 异常会转换为项目级 Repository 异常并保留异常链。支持的业务唯一键 upsert 为：Job `fingerprint`、Resume `candidate_id + content_hash`、Match `candidate_id + job_id`、Application `candidate_id + job_id`。分页默认按时间字段和 `id` 升序稳定排序，`limit` 范围为 1～100。

## Profile Service

`ProfileService` 通过 Unit of Work 抽象创建、查询和编辑 Candidate Profile，也可以原子导入已经结构化的 Profile 与 ResumeEvidence。它不解析 PDF、Word、图片或自然语言简历。

普通新增和导入的 Evidence 只能是 `UNVERIFIED`；只有显式验证操作可以转为 `VERIFIED`。审核查询可返回全部状态，正式查询则固定在数据库分页和计数之前筛选 `VERIFIED`，调用方不能关闭该限制。

Service 不依赖 SQLAlchemy、ORM 或 Session，也不自行提交事务；SQLAlchemy Unit of Work 复用现有 `session_scope` 管理提交和回滚。

## Job 与 Application Service

`JobService` 接收已经结构化且通过 Pydantic 校验的 `JobPosting`，提供手动保存、按 ID 查询和分页查询。保存操作复用 `JobRepository.upsert()`，以调用方提供的 `fingerprint` 去重；更新现有岗位时保留数据库中的 `id`、`fingerprint` 和 `discovered_at`。本阶段不生成 fingerprint，也不解析或搜索 JD。

`ApplicationService` 使用“创建 `ApplicationRecord` 即加入待投池”的语义。创建前校验 Candidate、Job，以及可选 ResumeVersion 的存在性和归属关系；初始状态固定为 `SHORTLISTED`，并在同一事务追加 `APPLICATION_CREATED` 事件。同一 `candidate_id + job_id` 只允许一条记录，完全相同的重复请求返回已有记录，不重复生成事件。

普通状态接口使用独立、确定性的 Python 规则：正常状态可向标准链后方推进或进入 `REJECTED`、`WITHDRAWN`、`CLOSED`，禁止回退，终止状态不能自动恢复；同状态请求没有写入副作用。每次真实变化都在同一事务追加 `STATUS_CHANGED` 事件。第一次进入 `SUBMITTED` 或更靠后的正常状态时设置 `submitted_at`，随后保持不变；所有服务时间由可注入 Clock 生成、统一为 UTC aware，并保证 `last_updated_at` 单调递增。

应用服务只依赖 Repository Protocol 和 `JobApplicationUnitOfWork`，不导入 SQLAlchemy、Session 或 ORM，也不自行提交或回滚。查询返回领域对象或 `Page[T]`；Application Timeline 按 `occurred_at`、`id` 稳定升序返回。

## JD Parser Port 与 Fake

T101 已提供 Pydantic `JDParseRequest`、`JDRequirement`、`ParsedJD` 和 `JDParserFixture` 契约，以及同步 `JDParser` Port 和确定性 `FakeJDParser`。Fake 只根据 Fixture 的 `external_job_id` 精确值或完整原文 UTF-8 SHA-256 精确匹配，不调用真实模型或网络；未命中时明确失败。解析结果是中间契约，不会自动保存为 `JobPosting`。

运行相关测试：

```powershell
python -m pytest tests\unit\application\test_jd_parser_contracts.py -q
python -m pytest tests\unit\infrastructure\test_fake_jd_parser.py -q
```

T102 真实适配器只支持 OpenAI-compatible Chat Completions，不使用供应商 SDK；支持严格 JSON Schema、30,000 字符输入上限、1 MiB 响应上限、超时/网络/429/408/指定 5xx 的最多三次固定退避重试，以及安全项目异常和脱敏日志。适配器不持久化解析结果，不替换默认 Fake。

## Streamlit 基础 UI

UI 提供五个页面：

- Dashboard：展示数据库聚合得到的本周岗位、Evidence、投递状态、最近事件和未来 14 天截止岗位。
- 个人资料：创建、查询、编辑、Pydantic 校验和保存前预览；邮箱、手机号默认掩码并独立编辑，编辑时留空表示保留原值，当前不支持清空。
- 证据库：查看审核数据、按状态筛选、使用 VERIFIED 正式查询并显式验证 Evidence。
- 岗位录入：手动录入结构化 JobPosting、按 fingerprint 去重，并幂等加入待投池。
- 投递记录：查看 Application、合法状态选项和稳定排序的 Event Timeline。

页面只调用应用 Service；Session State 只保存导航、表单草稿、预览确认标记和操作状态，不保存 Profile 等业务对象。业务事实始终从 SQLite 重新查询。错误提示使用安全中文信息和 trace_id，不回显 traceback、SQL、连接字符串或认证数据。

T008 V0.1 集成验收已完成：Profile → Evidence → Job → Application → Event → Dashboard → ServiceBundle 重建读取闭环已通过真实临时 SQLite 验收。

尚未实现后续任务，包括岗位搜索、自动 fingerprint、Match、LangGraph、Playwright、自动提交、登录/设置页和 FastAPI。
