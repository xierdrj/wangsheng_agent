# 秋招投递智能体

这是一个本地运行、由用户保持最终控制权的秋招工作流系统。当前已完成 T001 工程骨架、T002 领域 Schema、T003 数据库持久化基础和 T004 Repository 与事务层；业务工作流和业务页面仍在后续任务中实现。

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

测试覆盖 T001 smoke test、T002 领域模型、T003 临时 SQLite 数据库与迁移，以及 T004 Repository CRUD、upsert、分页、异常转换和跨 Repository 事务。

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

未实现：业务 Service、岗位搜索、LLM Agent、LangGraph 业务图、Playwright 自动化和 Streamlit 业务页面。
