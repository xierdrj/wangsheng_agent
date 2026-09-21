# 秋招投递智能体

这是一个本地运行、由用户保持最终控制权的秋招工作流系统。当前已完成 T001 工程骨架和 T002 领域 Schema，数据库、工作流和业务页面仍在后续任务中实现。

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

## 测试

```powershell
python -m pytest -q
```

测试覆盖 T001 smoke test，以及 T002 领域枚举、Schema 合法/非法输入、额外字段、时区和默认值隔离。

## 当前范围

已完成：工程目录、`pyproject.toml`、配置对象、`.env.example`、`.gitignore`、最小启动入口、领域枚举、Pydantic Schema 和单元测试。

未实现：数据库业务表、岗位搜索、LLM Agent、LangGraph 业务图、Playwright 自动化和 Streamlit 业务页面。
