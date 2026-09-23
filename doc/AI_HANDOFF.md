# AI 开发接力记录

## 项目信息

- 仓库名称：wangsheng_agent
- Python 包名称：job_agent
- Python 要求：3.11+
- 当前稳定任务：T005
- 已完成任务：T001、T002、T003、T004、T005
- 下一任务：T006
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

### T003：数据库与 ORM 持久化基础

已完成：

- SQLAlchemy 2.x Engine 和 Session 工厂
- SQLite 外键约束启用
- 显式数据库初始化入口
- Candidate、Resume、ResumeEvidence、Job、JobMatch、ResumeVersion、Application、ApplicationAnswer、ApplicationEvent ORM
- 领域 Schema 与 ORM 的显式映射
- UTC datetime 和 StrEnum 持久化策略
- 使用显式 Alembic DDL 的不可变初始迁移
- 迁移与 ORM metadata 结构一致性及升级/降级/再升级验证
- 临时 SQLite 集成测试

### T004：Repository 与事务层

已完成：

- 与 SQLAlchemy 实现分离的 Repository Protocol 和分页 `Page[T]`
- Candidate、Resume、ResumeEvidence、Job、Match、ResumeVersion、Application Repository
- Application 聚合内的 Answer/Event 新增和分页查询
- 一致的 add/get/list/update/delete 行为；查询不到返回 `None`，删除不存在返回 `False`，更新不存在抛 `EntityNotFoundError`
- Job、Resume、Match、Application 按明确业务唯一键执行 upsert，并保留数据库 id 与不可变键
- 分页参数校验（`limit` 1～100、`offset >= 0`）与时间/id 稳定排序
- Repository 只 flush，不 commit；共享 Session 的外层事务负责提交和回滚
- SQLAlchemy 完整性和持久化异常转换为项目级异常并保留异常链
- 使用 T003 Mapper；未修改 Schema、数据库表或 `0001_initial_persistence.py`
- 临时 SQLite 集成测试覆盖 CRUD、upsert、分页、异常转换和跨 Repository 回滚
- Windows 启动入口显式使用 UTF-8 stdout，启动文本有子进程字节级回归测试

### T005：Profile Service

已完成：

- Profile 创建、按 ID 查询和完整编辑
- 服务端 UTC Clock 规范化创建时间，并在编辑时保留 `created_at`、单调更新 `updated_at`
- `ProfileImportRequest` / `ProfileImportResult` 结构化导入契约
- Candidate 与多个 Evidence 的同事务原子导入
- 普通新增和导入固定使用 `UNVERIFIED`，拒绝绕过显式验证流程
- Evidence 显式验证和重复验证幂等行为
- 审核查询返回全部状态；正式查询使用数据库级 VERIFIED 专用分页
- application 层 `ProfileUnitOfWork` Protocol 与 infrastructure 层 SQLAlchemy 适配器
- Service 不导入 SQLAlchemy、Session 或 ORM，不调用 commit
- 未修改 Schema 或 migration

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

T005 完成时：

- 完整 pytest：48 passed
- T005 Profile Service 集成测试：8 passed
- T004 Repository 集成测试：10 passed
- 数据库集成测试：10 passed
- T002 领域模型测试：16 passed
- T001 smoke test：4 passed
- compileall：通过
- python -m job_agent：通过
- Alembic upgrade/downgrade：通过
- git diff --check：通过

## 当前未实现

- Job 与 Application Service
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

8. ORM 使用 UTC naive datetime 存储于 SQLite，映射恢复为 UTC aware datetime；领域层不依赖 SQLAlchemy。
9. T003 初始 revision 使用显式 `op.create_table`/`op.create_index`/`op.drop_table`，不导入 ORM metadata；迁移通过 `DATABASE_URL` 或 Alembic 命令配置读取数据库地址，不写入机器绝对路径。
10. T005 文档称 EvidenceVerification 只有 UNVERIFIED/VERIFIED，但 T002 公开枚举和领域文档还包含 REJECTED；当前保留 T002 契约，REJECTED 不进入正式查询，也不能被 Profile Service 自动验证。

## T003 新增公共接口

- `create_engine_from_url`
- `create_engine_from_settings`
- `create_session_factory`
- `session_scope`
- `initialize_database`
- `job_agent.infrastructure.database.mappers` 中的显式领域/ORM 转换函数

## T004 新增公共接口

- `job_agent.application.ports.repositories` 中的 Repository Protocol、`Page` 和项目级异常
- `job_agent.infrastructure.database.repositories` 中的 SQLAlchemy Repository 实现
- `job_agent.application.contracts.ResumeRecord`：针对 T002 尚未定义业务 Schema 的原始简历持久化 DTO；`ports` 保留兼容导出

## T005 新增公共接口

- `job_agent.application.services.ProfileService`
- `job_agent.application.services.EvidenceStateError`
- `job_agent.application.contracts.ProfileImportRequest`
- `job_agent.application.contracts.ProfileImportResult`
- `job_agent.application.ports.ProfileUnitOfWork`
- `job_agent.infrastructure.database.SqlAlchemyProfileUnitOfWork`
- `ResumeEvidenceRepository.list_by_candidate`
- `ResumeEvidenceRepository.list_verified_by_candidate`

## 下一任务

下一任务是 T006。T005 只实现 Profile 和 Evidence 业务边界，未实现 Job/Application Service、LLM、LangGraph、Playwright、Streamlit 或其他后续功能。

## 每次任务完成后的更新要求

每完成一个 Txxx，必须更新本文件中的：

- 当前稳定任务
- 已完成任务
- 新增公共接口
- 最近测试结果
- 已知风险
- 下一任务
