# LangGraph 工作流设计

## 1. 总体原则

LangGraph 负责长期工作流的编排、中断、恢复和路由，不代替业务数据库、浏览器 Adapter 或领域规则。

节点设计原则：

- 单一职责；
- 输入输出使用 Schema；
- 外部副作用显式；
- 可重试节点尽量幂等；
- Node 不在内部静默吞异常；
- 条件路由基于受约束状态或错误码；
- 人工审批使用 `interrupt()`，恢复时复用原 `thread_id`。

## 2. Profile Graph

```text
START
→ ingest_resume
→ parse_resume
→ build_candidate_profile
→ build_evidence_items
→ validate_profile
→ human_review_profile
→ save_profile
→ END
```

### 节点职责

- `ingest_resume`：保存原始文件并计算哈希；
- `parse_resume`：提取文本和版面信息；
- `build_candidate_profile`：结构化基本信息和经历；
- `build_evidence_items`：拆分可独立引用的事实；
- `validate_profile`：Schema、日期、数字和引用一致性检查；
- `human_review_profile`：暂停并等待用户修正；
- `save_profile`：事务性保存 Profile 和 Evidence。

## 3. Job Discovery Graph

```text
START
→ load_candidate_preferences
→ plan_searches
→ perform_searches
→ normalize_jobs
→ deduplicate_jobs
→ hard_filter_jobs
→ semantic_match_jobs
→ save_jobs_and_matches
→ END
```

### 路由

- 搜索源暂时不可用：记录源级错误，其他源继续；
- 岗位缺少必要字段：进入 `needs_normalization_review`；
- Hard Filter 不通过：保存原因，不调用语义匹配；
- 全部搜索失败：Graph 失败并返回可重试状态，不生成虚假岗位。

## 4. Application Graph

```text
START
→ load_profile_and_job
→ validate_application_eligibility
→ analyze_jd
→ retrieve_evidence
→ generate_resume_content
→ generate_application_answers
→ validate_generated_content
→ human_review_content [interrupt]
→ prepare_browser_session
→ open_application_page
→ detect_and_extract_form
→ map_fields
→ fill_form
→ validate_form
→ handle_human_action_if_needed [interrupt]
→ capture_pre_submit_snapshot
→ human_review_submission [interrupt]
→ submit_application
→ verify_submission
→ save_application_snapshot
→ END
```

### 必须中断的场景

- 生成材料需要用户修改；
- 登录失效；
- 验证码或短信验证；
- 敏感字段；
- 低置信度字段；
- 表单校验仍有警告；
- 点击最终提交之前。

### 提交规则

`submit_application` 只接收服务器端保存的审批令牌或与当前表单快照绑定的批准结果，不能只依赖 UI 中一个未校验布尔值。

审批结果必须与：

- `application_id`；
- 表单快照哈希；
- ResumeVersion；
- 审批时间；

关联。若审批后表单发生变化，审批失效并重新确认。

## 5. Tracking Graph

```text
START
→ load_active_applications
→ collect_status_signals
→ normalize_signals
→ match_signal_to_application
→ propose_status_transition
→ validate_transition
→ human_review_if_ambiguous
→ append_event_and_update_status
→ END
```

LLM 可以对邮件或网页文本做分类，但状态转换合法性由普通 Python 校验。

## 6. State 示例

```python
from typing import TypedDict


class ApplicationGraphState(TypedDict, total=False):
    candidate_id: str
    job_id: str
    application_id: str
    stage: str
    match_result_id: str
    resume_version_id: str
    answer_ids: list[str]
    form_fields: list[dict]
    validation_errors: list[str]
    pending_human_action: dict | None
    approval_token: str | None
    error_code: str | None
    error_message: str | None
```

## 7. Node 返回规范

Node 只返回变更字段：

```python
def validate_form(state: ApplicationGraphState) -> dict:
    errors = ...
    return {
        "stage": "FORM_VALIDATED",
        "validation_errors": errors,
    }
```

不要就地修改共享 State，不要返回浏览器对象，不要把异常堆栈写入 State。

## 8. 错误与重试

### 可自动重试

- 临时网络失败；
- LLM 限流；
- 页面加载超时；
- 数据库瞬时锁冲突。

重试必须限制次数并使用退避。

### 不自动重试

- Schema 校验失败；
- 违反业务规则；
- 登录失效；
- 验证码；
- Selector 结构变化导致字段无法确认；
- 已出现可能提交成功但结果未知的情况。

最后一种情况必须先检查投递记录或成功页，不能盲目再次点击提交。

## 9. Checkpoint 与恢复

- 每次调用使用稳定 `thread_id`；
- `interrupt()` 后从相同线程恢复；
- 恢复前重新读取数据库中的最新业务事实；
- 外部网页可能已变化，恢复浏览器步骤时重新验证 URL、登录态和表单哈希；
- 已完成的提交节点通过事件和成功快照判断是否跳过。

## 10. Graph 测试要求

每条 Graph 至少覆盖：

- 正常路径；
- Schema 失败；
- 外部依赖失败；
- 中断并恢复；
- 重复调用幂等；
- 禁止非法路由；
- 不满足安全条件时不会进入提交节点。

