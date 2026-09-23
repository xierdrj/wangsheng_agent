# 秋招投递智能体

这是一个本地运行、由用户保持最终控制权的秋招工作流系统。当前已完成 T001 工程骨架、T002 领域 Schema、T003 数据库持久化基础、T004 Repository 与事务层、T005 Profile Service，以及 T006 Job/Application Service；岗位搜索、自动投递和业务页面仍在后续任务中实现。

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

## 测试

```powershell
python -m pytest -q
```

测试覆盖 T001 smoke test、T002 领域模型、T003 临时 SQLite 数据库与迁移、T004 Repository、T005 Profile Service，以及 T006 岗位去重、待投池幂等创建、状态机、事件 Timeline 和事务回滚。

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

已完成：工程目录、`pyproject.toml`、配置对象、`.env.example`、`.gitignore`、最小启动入口、领域枚举、Pydantic Schema、SQLAlchemy ORM、数据库初始化、Alembic 初始迁移、Repository 接口/实现和单元/集成测试。

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

未实现：T007 Streamlit 基础 UI、岗位搜索、LLM Agent、LangGraph 业务图、Playwright 自动化和自动提交。
