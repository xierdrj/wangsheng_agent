# 秋招投递智能体

这是一个本地运行、由用户保持最终控制权的秋招工作流系统。当前代码处于 T001 工程骨架阶段，仅提供可安装的 Python 包、集中配置和最小启动入口，尚未实现业务功能。

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

T001 的 smoke test 覆盖包导入、默认配置、`.env` 与环境变量优先级，以及非 fake LLM 缺少密钥时的明确配置错误。

## 当前范围

已完成：工程目录、`pyproject.toml`、配置对象、`.env.example`、`.gitignore`、最小启动入口和 smoke test。

未实现：Candidate、数据库业务表、岗位搜索、LLM Agent、LangGraph 业务图、Playwright 自动化和 Streamlit 业务页面。

