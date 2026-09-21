# API 与 Streamlit 界面

## 1. 总体原则

- 页面只通过 Service 层访问业务能力；
- 页面不得直接操作 ORM Session、LLM 或 Playwright；
- UI 展示的状态与业务数据库一致；
- 长任务使用明确的运行状态和刷新机制；
- Streamlit Session State 只保存页面交互状态，不作为业务事实存储。

## 2. Service 层

建议接口：

```python
class ProfileService:
    def create_profile(self, command): ...
    def update_profile(self, candidate_id, command): ...
    def import_resume(self, candidate_id, file_path): ...
    def verify_evidence(self, evidence_id, decision): ...


class JobService:
    def create_job(self, command): ...
    def discover_jobs(self, candidate_id): ...
    def get_job_detail(self, job_id): ...
    def shortlist(self, candidate_id, job_id): ...


class ApplicationService:
    def prepare_application(self, candidate_id, job_id): ...
    def resume_workflow(self, application_id, human_input): ...
    def update_status(self, application_id, new_status, reason): ...
```

## 3. Streamlit 页面

### 3.1 Dashboard

展示：

- 本周新增岗位；
- 高匹配岗位；
- 待审核内容；
- 待提交申请；
- 已投递、笔试、面试、Offer 数；
- 最近事件；
- 即将截止岗位。

### 3.2 个人资料

- 基本信息；
- 教育、实习、项目、技能；
- 求职偏好；
- 敏感信息独立编辑；
- 保存前预览变更。

### 3.3 证据库

- 按经历、技能、验证状态筛选；
- 查看 Evidence 来源；
- 批准、编辑、拒绝；
- 显示哪些简历版本或答案引用了该证据。

### 3.4 岗位发现

- 搜索参数；
- 岗位列表；
- 硬过滤结果；
- 匹配分数和缺口；
- 加入待投池。

### 3.5 岗位详情

左侧显示 JD，右侧显示：

- 分项匹配；
- Strengths / Gaps；
- 对应证据；
- 推荐材料；
- 生成或重新生成；
- 创建投递。

### 3.6 待审批

分为：

- Profile/Evidence 审批；
- 简历与答案审批；
- 表单字段审批；
- 最终提交审批。

最终提交页必须显示：公司、岗位、URL、简历版本、开放题答案、敏感字段、校验警告和提交前截图。

### 3.7 投递记录

- 按公司、状态、时间筛选；
- 显示 Timeline；
- 下载投递快照；
- 手动更新状态；
- 查看当时使用的简历和答案。

### 3.8 设置

- 模型 Provider 和模型名；
- 数据目录；
- 浏览器 Headless / Dry Run；
- 最大每日提交数；
- 登录态管理；
- 日志级别。

API Key 输入应使用密码控件，不回显已保存值。

## 4. 页面状态

页面必须明确区分：

- `idle`；
- `running`；
- `waiting_for_human`；
- `succeeded`；
- `failed`；
- `cancelled`。

失败时显示用户可理解的信息和 `trace_id`，不要直接展示完整异常堆栈或敏感数据。

## 5. FastAPI（可选）

第一版纯 Streamlit 可以直接调用 Service。若启用 API，建议路由：

```text
GET    /health
GET    /candidates/{id}
POST   /candidates
POST   /candidates/{id}/resumes
GET    /candidates/{id}/evidence
PATCH  /evidence/{id}
POST   /jobs
GET    /jobs
GET    /jobs/{id}
POST   /jobs/{id}/match
POST   /applications
GET    /applications
GET    /applications/{id}
POST   /applications/{id}/resume
POST   /applications/{id}/approve-content
POST   /applications/{id}/approve-submission
PATCH  /applications/{id}/status
```

## 6. API 契约

- 请求和响应使用独立 DTO；
- 错误格式统一；
- 创建接口支持幂等键；
- 不在响应中返回 Cookie、Token 和本地认证文件路径；
- 所有人工审批写入事件表；
- 最终提交审批应绑定当前快照哈希。

建议错误响应：

```json
{
  "error": {
    "code": "PROFILE_VALIDATION_FAILED",
    "message": "候选人资料缺少求职方向",
    "details": [],
    "trace_id": "..."
  }
}
```

## 7. 第一阶段 UI 验收

- 可以创建并编辑 Candidate Profile；
- 可以查看和验证 Evidence；
- 可以手动创建 JobPosting；
- 可以创建 ApplicationRecord；
- 可以安全地更新状态并看到 Timeline；
- 页面刷新后业务数据仍存在；
- 错误不会导致整个页面不可用；
- 页面中没有泄露密钥和认证状态。

