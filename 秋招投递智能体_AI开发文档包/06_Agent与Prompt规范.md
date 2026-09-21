# Agent 与 Prompt 规范

## 1. LLM 使用边界

适合 LLM：

- JD 结构化；
- 问题意图分类；
- 语义匹配解释；
- 证据相关性排序；
- 简历表达重写；
- 网申开放题草稿；
- 招聘邮件事件分类。

不适合 LLM：

- 状态机合法性；
- 唯一性、去重和哈希；
- 截止日期比较；
- 数据库事务；
- 是否允许最终提交；
- 验证码处理；
- 读取密码或 Cookie；
- 生成不存在的个人事实。

## 2. Agent 划分

| Agent | 输入 | 输出 |
|---|---|---|
| Search Planner | 求职意向 | SearchPlan |
| JD Parser | raw_jd | ParsedJD |
| Match Agent | ParsedJD + Evidence | MatchResult 草案 |
| Evidence Retriever | requirement + Evidence Bank | EvidenceHit[] |
| Resume Tailor | JD + EvidenceHit[] | TailoredSection[] |
| Answer Generator | question + JD + EvidenceHit[] | ApplicationAnswer 草案 |
| Status Classifier | 邮件/页面文本 | StatusSignal |

浏览器执行器不是自由行动型 LLM Agent；它是由确定性步骤和受控字段映射组成的执行模块。

## 3. 所有 Prompt 的公共约束

每个 Prompt 都必须明确：

1. 任务目标；
2. 输入字段；
3. 输出 Pydantic Schema；
4. 禁止事项；
5. 不确定时的行为；
6. 事实依据规则；
7. 示例仅用于格式，不可复制事实。

公共系统约束：

```text
你只能使用输入中明确提供的候选人事实。
不得补充、推断或夸大不存在的经历、技能、数字和成果。
每个涉及候选人能力的结论都必须返回 source_evidence_ids。
若没有足够证据，将该要求列入 gaps 或 needs_human_review。
只输出指定结构，禁止附加结构外说明。
```

## 4. 结构化输出

优先使用模型原生 structured output 或 Pydantic 解析。禁止依靠正则从大段自由文本中抢救 JSON 作为正常路径。

失败处理：

1. 第一次 Schema 校验失败，使用校验错误进行一次修复调用；
2. 第二次失败，返回明确错误并进入人工处理；
3. 不允许无限循环重试；
4. 保存脱敏后的调用元数据用于调试。

## 5. JD Parser 输出契约

必须区分：

- responsibilities；
- hard requirements；
- preferred qualifications；
- skills；
- education；
- graduation year；
- experience years；
- location；
- deadline；
- ambiguous items。

不得将“优先”误判为硬性要求。原文没有的信息保持空值，不猜测。

## 6. Match Agent

Match Agent 只负责语义维度评分和解释，Hard Filter 在调用前完成。

每个强项必须包含：

- 对应 JD 要求；
- 证据 ID；
- 简短解释。

每个 gap 必须区分：

- `missing_evidence`：资料中未找到；
- `partial_match`：有相邻经验但不完全满足；
- `hard_gap`：明确不符合；
- `unknown`：信息不足。

LLM 分数是排序信号，不声明为客观概率。

## 7. Evidence Retriever

检索顺序：

1. 只筛选 `VERIFIED` Evidence；
2. 技能和分类精确匹配；
3. 关键词匹配；
4. 可选语义相似度；
5. LLM 重排前 N 条。

返回：`evidence_id`、相关性、支持说明、是否直接匹配。不得把检索不到等同于候选人一定不会，只能说明“资料中无证据”。

## 8. Resume Tailor

允许：

- 调整已有条目顺序；
- 压缩弱相关内容；
- 用规范术语重述；
- 突出与 JD 对应的真实职责；
- 在字数限制内改写。

禁止：

- 新增未提供的项目；
- 将“参与”改成“主导”；
- 凭空添加指标；
- 把相邻技术经验写成直接使用经验；
- 改变公司、职位、时间和学历事实。

输出必须同时返回变更说明和证据 ID，供 UI 展示 diff。

## 9. Answer Generator

输入应包含：问题、字符限制、公司/岗位信息、已批准 Answer Bank 内容、相关 Evidence。

若问题涉及薪资、外派、背景调查、竞业、家庭、政治或法律声明，直接标记 `needs_human_review=True`，不代替用户作决定。

## 10. Prompt 文件管理

Prompt 保存在 `prompts/`，每个文件头部包含：

```text
prompt_id
version
input_schema
output_schema
owner
last_updated
```

修改 Prompt 时必须：

- 更新版本；
- 增加或更新固定评测样例；
- 运行结构化输出和事实一致性测试；
- 不在 Prompt 中放真实个人敏感信息。

## 11. LLM 可观测性

记录：

- provider/model；
- prompt_id/version；
- latency；
- token usage；
- schema validation result；
- retry count；
- trace_id。

不记录：API Key、完整敏感资料、Cookie、密码。生产日志中的 Prompt/Response 默认只保存脱敏摘要或哈希。

