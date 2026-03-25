# Agent 项目 v0.5 新增功能测试报告
**类型**：静态审查 / 设计级风险测试  
**技术栈**：FastAPI + React  
**范围**：ProductCategory、Task 状态机、CrawlRun/Candidate、ConversationThread、TaskOrchestrator、AgentRouter、tasks/categories/crawl/generate API、WorkbenchPage、React Query、图像处理集成

## 一、总体结论
本次针对 v0.5 新增功能做了结构化风险审查，共识别 **18 个问题**：

- **高严重级：9 个**
- **中严重级：9 个**

### 核心风险
1. **Task 状态机缺少严格流转约束**
2. **advance / select-candidate 存在并发与越域风险**
3. **ConversationThread / ChatMessage 线程边界不清**
4. **crawl 接口存在 SSRF / Prompt Injection 安全风险**
5. **图像/视频等长任务若同步执行，会拖垮 API worker**
6. **前端 React Query 缓存与本地状态容易和服务端脱节**

> 结论：**高风险问题未修复前，不建议直接上线生产环境。**

---

## 二、问题清单

| ID | 分类 | 严重级 | 问题描述 | 影响 | 修复建议 |
|---|---|---|---|---|---|
| 1 | 数据模型 | 高 | **ProductCategory 仅有 `parent_id`，未见防环、自引用、深度限制、删除策略。** 可能出现 A→B→A 循环、父分类删除后子分类悬挂。 | 分类树查询死循环、前端树组件卡死、项目筛选异常、脏数据难清理。 | 服务层增加环检测；DB 至少禁止 `parent_id = id`；删除时采用 `restrict / reparent / soft delete` 之一；为 `parent_id` 建索引。 |
| 2 | 数据模型 | 中 | **Project 新增 `category_id` 后，历史数据回填、空值策略、外键约束、删除联动不明确。** | 老项目可能没有分类，或引用已删除分类；列表筛选、统计、搜索结果不稳定。 | 增加迁移脚本；设“未分类”兜底；补充 FK 与索引；明确 `on delete restrict/set null` 规则。 |
| 3 | 数据模型 / 会话 | 高 | **ConversationThread / ChatMessage.thread_id 仅加字段但未明确线程边界。** 若 thread 未绑定 project/task/user，消息可能串线。 | Agent 获取错误上下文；跨任务、跨项目消息污染；严重时造成数据泄露。 | Thread 必须绑定 `project_id/task_id/owner_id`；查询统一加 scope；迁移历史消息；补 FK 与级联规则。 |
| 4 | 数据模型 | 中 | **`Version.content_type` 唯一性范围不清，`Asset.metadata_json` 缺少 schema/version/大小约束。** | 版本“最新值”不确定；同类内容可能重复或覆盖；metadata 格式漂移导致前后端解析失败、查询慢。 | 明确唯一键（如 `task_id + content_type + version_no`）；增加 `schema_version`；用 Pydantic/JSON Schema 校验；限制 JSON 大小并对常用键建索引。 |
| 5 | 状态机 | 高 | **Task 5 步状态机未见显式合法迁移表与前置条件校验。** 可能从 `input` 直接跳到 `content_extend`，或未选商品就进入 `scene_generate`。 | 任务流程失真、内容缺失、后续生成失败、人工纠错成本高。 | 在后端集中定义合法迁移矩阵；每步校验必填条件；非法流转返回 `409 Conflict`；补充单元/集成测试。 |
| 6 | 状态机 / 并发 | 高 | **`advance` 接口缺少幂等与并发控制。** 多标签页、重复点击、重试请求可能重复推进状态。 | 状态跳步、重复生成 copy/video、重复扣费、版本/资产重复写入。 | 增加 `idempotency key`；使用 `expected_status` 或 `task_version` 做 CAS；单任务加锁；重复请求返回同一结果。 |
| 7 | 状态机 / 业务一致性 | 高 | **`select-candidate` 未强校验 candidate 是否属于当前 task / crawl run / project，且未限制只能在 `product_select` 状态调用。** | 选中别的任务或别的项目的候选；数据串用；越权风险高。 | 校验 `task.status == product_select`；校验 `candidate -> crawl_run -> task -> project` 全链路；原子化更新 candidate 与 task 状态。 |
| 8 | 数据一致性 | 中 | **CrawlRun / Candidate 生命周期不完整。** 新一轮 crawl 后旧 Candidate 未失效；部分失败 run 的 Candidate 仍可选；删除 run 可能遗留孤儿数据。 | 选到陈旧/无效候选，导致后续生成失败；数据越来越脏。 | 增加 `CrawlRun.status`（pending/running/succeeded/partial_failed/failed/cancelled）；Candidate 增加 `valid/is_selected`；限定仅展示最新成功 run 的候选。 |
| 9 | 编排 / Agent | 高 | **TaskOrchestrator + AgentRouter 缺少失败态、重试计数、错误码、补偿逻辑。** 路由失败/模型失败后任务可能卡在中间状态。 | 任务“看似运行中、实际已失败”；前端无法判断；需人工改库。 | 增加 `sub_status / error_code / retry_count / last_error`；支持 retry/resume/cancel；状态推进与版本/资产写入放在事务或 Saga 内。 |
| 10 | API 契约 | 中 | **tasks CRUD / advance / select-candidate / crawl / generate-video / generate-copy 的同步/异步语义、响应体、错误码风格可能不一致。** | 前端适配复杂；超时后无法判断任务是否已提交；错误处理混乱。 | 长任务统一 `202 + job_id`；提供 job 查询或 SSE/WebSocket；错误码统一为 `400/401/403/404/409/422/429/500`；OpenAPI 补示例。 |
| 11 | 前端静态设计 | 中 | **WorkbenchPage 若硬编码 5 个步骤、Tab 映射和按钮规则，前后端状态枚举容易漂移。** | 后端状态新增/改名后，前端显示错乱、按钮误启用、页面进入未知态。 | 通过 OpenAPI 生成 TS 类型或共享枚举；未知状态给兜底 UI；按钮启用逻辑以服务端状态为准。 |
| 12 | 前端缓存 | 中 | **React Query 缓存键和失效策略若未覆盖 `projectId/taskId/threadId/crawlRunId` 等维度，会出现脏缓存。** | 切项目后还显示旧候选；select-candidate 后预览不刷新；进度条停在旧状态。 | 设计层级化 queryKey；mutation 后精准 invalidate/update cache；避免跨项目共用缓存。 |
| 13 | 前端状态管理 | 中 | **WorkbenchPage 本地状态与服务端状态双写。** 当前 Tab、选中候选、预览内容若主要靠本地 state，刷新/回退/切项目后容易错位。 | 页面显示“已进入下一步”，服务端实际还在上一步；用户误操作。 | 以服务端 `task.status` 为单一真源；将项目/任务/Tab 放入 URL 或路由状态；刷新后从服务端恢复。 |
| 14 | 前端异常处理 | 中 | **空态、失败态、超时态处理不足。** 无 Candidate、无 Thread、外部服务失败、接口 409/422/500 时，页面可能白屏或永远 loading。 | 用户体验差；重复提交；定位困难。 | 增加 Error Boundary、空态组件、Skeleton、请求超时提示、冲突态提示；对 `409/422` 给出明确文案。 |
| 15 | 安全 | 高 | **crawl 接口存在 SSRF 与 Prompt Injection 风险。** 若允许抓任意 URL，可访问内网地址；抓取内容直接喂给 LLM 也会被恶意提示污染。 | 内网探测、敏感资源读取、模型输出被操控，属于高危。 | 禁止私网/回环/链路本地地址；做 DNS 解析校验；限制协议/域名/大小/类型；对抓取文本做清洗与提示隔离。 |
| 16 | 安全 / 权限 | 高 | **tasks / threads / candidates / categories 若只按 ID 访问，缺少 project/user 级鉴权，会有 IDOR。** | 可读写他人任务、会话、候选数据，造成严重越权。 | 所有查询强制带租户/项目/用户 scope；服务层做 ownership check；记录审计日志。 |
| 17 | 性能 / 稳定性 | 高 | **rembg / remove.bg / NumPy / 视频生成等重 CPU/IO 操作若在 FastAPI 请求线程同步执行，会阻塞 worker。** 外部服务无熔断也会放大问题。 | API 超时、吞吐下降、OOM、普通 CRUD 也被拖慢。 | 使用异步任务队列（Celery/RQ/Arq）；限制上传尺寸与并发；设置超时/重试/熔断；清理临时文件。 |
| 18 | 性能 / 数据库 | 中 | **新增字段 `parent_id/category_id/thread_id/status/crawl_run_id` 若无索引，列表页与树查询易产生 N+1 / 全表扫描。** | WorkbenchPage 打开慢；数据量上涨后性能快速恶化。 | 对高频过滤/关联字段建索引；分页返回；预加载摘要数据；只在详情页拉取大字段/metadata/messages。 |

---

## 三、优先修复建议

### P0（上线前必须处理）
- Task 状态机合法流转与并发控制（ID 5、6、7、9）
- crawl SSRF / Prompt Injection（ID 15）
- 资源鉴权 / IDOR（ID 16）
- 重 CPU/IO 任务异步化（ID 17）

### P1（建议首轮迭代完成）
- ProductCategory 层级完整性（ID 1）
- Thread 边界与上下文隔离（ID 3）
- API 契约统一（ID 10）
- 前端缓存与状态一致性（ID 11、12、13、14）

### P2（稳定性与长期治理）
- Project.category_id 数据迁移（ID 2）
- Version / Asset 模型约束收口（ID 4）
- CrawlRun/Candidate 生命周期治理（ID 8）
- 索引与查询优化（ID 18）

---

## 四、测试结论
从 QA 视角看，v0.5 的主要问题不是“单点功能缺失”，而是 **状态一致性、权限边界、异步任务治理、前后端契约统一**。  
如果这些问题不先收口，后续会出现：

- 流程乱跳、重复生成
- 候选与会话串线
- 前端显示与服务端真实状态不一致
- 长任务拖垮接口
- 安全风险直接暴露

如果你愿意，我可以继续把这份报告整理成：
1. **Jira 缺陷单格式**  
2. **测试用例清单（正常/异常/并发）**  
3. **上线前验收 checklist**