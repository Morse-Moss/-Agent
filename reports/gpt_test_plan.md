下面给出一份面向 **v0.5 图片处理 Agent 平台（FastAPI + React）** 的**健壮性/回归测试计划**。重点围绕你提到的已修复 **P0 问题** 做强回归，兼顾异常、边界、并发、安全与前后端状态一致性。

> 说明：  
> - 以下任务状态机示例按 **Pending / Running / Completed / Error / Cancelled** 5 态描述；若你们代码中的枚举名不同，请做 1:1 映射。  
> - 对于错误码，如果接口契约尚未完全冻结，建议以“**至少必须拒绝且状态不变/无越权/无脏数据**”为验收底线；文中给出的是推荐结果。  
> - 本计划共 **56 条测试用例**。

---

# 1. 测试范围与目标

## 1.1 测试目标
本轮测试目标是确认以下能力稳定可用，并防止已修复的 P0 问题回归：

1. **任务状态机健壮性**
   - 状态流转合法性
   - CAS 版本冲突保护
   - 幂等性
   - 失败态恢复
   - 并发竞争下无脏数据、无重复执行

2. **项目级数据隔离**
   - 项目 CRUD 正常
   - 软删除生效
   - 删除后资源不可误访问
   - 跨项目越权访问被阻断
   - 关键字段唯一约束生效

3. **crawl 安全性**
   - SSRF 防护有效
   - URL 格式校验有效
   - 私网/回环/DNS 解析绕过/重定向绕过均可阻断

4. **图像处理容错**
   - rembg 成功链路
   - rembg 失败后的兜底链路
   - 全部失败时系统可降级并正确落库
   - 非法图片/大图/处理中异常时不崩溃、不留脏状态

5. **前后端状态一致性**
   - React Query 轮询同步
   - 冲突后自动刷新
   - 错误态可见
   - 缓存失效/页面跳转/软删除后 UI 一致

6. **API 边界与认证授权**
   - 空值、长字符串、错误类型、非法 JSON、Content-Type 校验
   - token 缺失、过期、无效、跨项目越权

---

## 1.2 测试范围
### 后端
- FastAPI API 层
- SQLAlchemy 事务与并发控制
- Pydantic 参数校验
- 任务状态机服务层
- 项目/分类/候选/会话线程模型与权限
- crawl URL 校验与 SSRF 防护
- 图像处理管线（Pillow / rembg / remove.bg / NumPy）

### 前端
- React 18 页面与状态同步
- React Query 缓存、轮询、失效刷新
- Ant Design 表单校验与错误提示
- 冲突/错误/删除场景下的页面行为

### 数据库
- MySQL 主验证
- SQLite 兼容性回归

---

## 1.3 重点风险
- 状态机跳转失控导致重复执行/脏数据
- CAS 失效导致并发覆盖
- SSRF 可探测内网或云元数据地址
- 软删除后数据仍可被访问
- ConversationThread 缺少 project_id 导致隔离失效
- 关键字段唯一约束缺失导致重复记录
- 前端缓存陈旧导致误操作或错误展示

---

# 2. 测试策略

## 2.1 测试层次
1. **单元测试**
   - 状态流转规则函数
   - URL/IP 校验器
   - Pydantic schema 校验
2. **集成测试**
   - FastAPI + DB + Service
   - 图像处理 pipeline mock
   - SSRF 解析/重定向/解析结果拦截
3. **API 自动化**
   - pytest + httpx/TestClient
   - 并发场景用多线程/协程压测
4. **前端 E2E**
   - Playwright/Cypress
5. **安全测试**
   - SSRF、越权、token、非法输入
6. **回归测试**
   - 所有已修复 P0 必须纳入 CI

## 2.2 优先级定义
- **P0**：安全、数据一致性、核心流程、已修复 P0 回归
- **P1**：主要业务流程、重要异常路径
- **P2**：体验/兼容性/低风险边界

---

# 3. 详细测试用例清单

## 3.0 公共测试数据约定
为便于阅读，后续用例使用以下缩写：

### 账号
- **UA / TokenA**：用户A，拥有项目 PA
- **UB / TokenB**：用户B，拥有项目 PB
- **ExpiredToken**：过期 token
- **InvalidToken**：签名错误 token

### 项目/资源
- **PA**：用户A的正常项目
- **PB**：用户B的正常项目
- **PDEL**：已软删除项目
- **CAT_A1**：PA 下分类
- **CAT_B1**：PB 下分类
- **TH_A1**：PA 下会话线程
- **CAN_A1**：PA 下候选
- **CAN_B1**：PB 下候选

### 任务
- **Task_PEND(v1)**：Pending 状态任务，version=1
- **Task_RUN(v1)**：Running 状态任务
- **Task_ERR(v1)**：Error 状态任务
- **Task_DONE(v2)**：Completed 状态任务
- **Task_CANCEL(v2)**：Cancelled 状态任务

### URL
- **URL_PUBLIC**：公网合法 URL，如 `https://example-cdn.test/a.jpg`
- **URL_BAD**：非法 URL，如 `ht!tp://bad`
- **URL_FILE**：`file:///etc/passwd`
- **URL_LOCAL**：`http://127.0.0.1:8000/admin`
- **URL_PRIVATE**：`http://10.1.2.3/a.jpg`
- **URL_META**：`http://169.254.169.254/latest/meta-data`
- **URL_DNS_PRIVATE**：域名解析后落到私网 IP
- **URL_REDIRECT_PRIVATE**：首跳公网，302 到私网
- **URL_IPV6_LOCAL**：`http://[::1]/a.jpg`

### 图片
- **IMG_OK_JPG**：正常 jpg
- **IMG_OK_PNG**：正常 png
- **IMG_CORRUPT**：损坏图片
- **IMG_FAKE_JPG**：文本文件改后缀为 .jpg
- **IMG_LARGE**：接近或超过大小限制的大图

---

## 3.1 Task 状态机 / CAS / 幂等 / 恢复

| ID | 模块 | 类型 | 前置条件 | 步骤 | 预期结果 | 优先级 |
|---|---|---|---|---|---|---|
| TS-001 | Task状态机 | 正常 | Task_PEND(v1) 属于 PA | 调用 start，携带 version=1 | 返回成功；状态变为 Running；version+1；无重复执行记录 | P0 |
| TS-002 | Task状态机 | 正常 | Task_RUN(v1) | 调用 complete，携带 version=1 | 返回成功；状态变为 Completed；version+1 | P0 |
| TS-003 | Task状态机 | 正常 | Task_RUN(v1) | 调用 cancel，携带 version=1 | 返回成功；状态变为 Cancelled；version+1 | P0 |
| TS-004 | Task状态机 | 异常 | Task_PEND(v1) | 直接调用 complete | 被拒绝；返回 4xx（建议409/422）；状态与 version 不变 | P0 |
| TS-005 | Task状态机 | 异常 | Task_DONE(v2)、Task_CANCEL(v2) | 分别对已完成/已取消任务再调用 start/cancel/complete | 被拒绝；终态不可继续流转；状态不变 | P0 |
| TS-006 | Task恢复 | 异常 | Task_RUN(v1) | 调用 mark_error("mock error")，再调用 cancel | 先进入 Error，再允许恢复为 Cancelled（若业务允许）；保留错误原因/日志 | P0 |
| TS-007 | Task恢复 | 异常 | Task_RUN(v1) | 调用 mark_error("mock error")，再调用 complete | 先进入 Error，再允许恢复为 Completed（若业务允许）；保留错误原因/日志 | P0 |
| TS-008 | Task幂等 | 并发/异常 | Task_DONE(v2) | 对 complete 连续发送2次相同请求 | 不产生重复副作用；状态仍为 Completed；不重复写结果/事件 | P0 |
| TS-009 | Task幂等 | 并发/异常 | Task_CANCEL(v2) | 对 cancel 连续发送2次相同请求 | 不产生重复副作用；状态仍为 Cancelled | P0 |
| TS-010 | Task-CAS | 并发 | Task_RUN(v1) | 先用 version=1 完成一次合法更新，再用旧 version=1 发第二次更新 | 第二次返回冲突（建议409）；返回最新 state/version 或可供前端刷新 | P0 |
| TS-011 | Task并发 | 并发 | 有1条可领取的 Pending 任务 | 20 个并发 worker 同时 claim/start 同一任务 | 仅 1 个成功进入 Running；其余冲突/空结果；数据库无重复执行 | P0 |

---

## 3.2 项目 / 分类 / 候选 / ConversationThread

| ID | 模块 | 类型 | 前置条件 | 步骤 | 预期结果 | 优先级 |
|---|---|---|---|---|---|---|
| PR-001 | Project CRUD | 正常 | UA 已登录 | 创建项目 `Project-A-New` | 创建成功；返回新 project_id；列表可见 | P1 |
| PR-002 | Project唯一约束 | 异常 | PA 已存在，名称为 `Project-A` | UA 再创建同名项目 `Project-A` | 被拒绝；返回 4xx；数据库不产生重复活跃项目 | P0 |
| PR-003 | Project软删除 | 正常/异常 | PA 存在 | 删除 PA（软删除），然后查列表与详情 | 列表不再显示；详情返回 404/410；DB 标记 deleted_at，不物理删除 | P0 |
| PR-004 | 删除后依赖资源 | 异常 | PDEL 已软删除 | 尝试在 PDEL 下创建 task/category/thread/candidate 关联 | 全部被拒绝；返回 404/403；无新资源写入 | P0 |
| PR-005 | Category唯一约束 | 异常 | PA 下已有分类 `Shoes` | 在 PA 下再创建 `Shoes` | 被拒绝；同项目内名称唯一 | P0 |
| PR-006 | Category项目隔离 | 正常 | PA 下已有 `Shoes` | 在 PB 下创建同名 `Shoes` | 创建成功；跨项目允许同名 | P1 |
| PR-007 | ConversationThread | 异常 | UA 已登录 | 创建 ConversationThread，但不传 project_id | 参数校验失败；返回 422；不写入数据库 | P0 |
| PR-008 | ConversationThread隔离 | 安全 | TH_A1 属于 PA；UB 已登录 | UB 使用 TokenB 访问/更新 TH_A1 | 返回 403/404；不泄露线程内容 | P0 |
| PR-009 | Candidate选择 | 正常 | CAN_A1 属于 PA | 在 PA 内执行候选选择/确认 | 成功；生成1条合法关联记录 | P1 |
| PR-010 | Candidate去重 | 异常 | CAN_A1 已被选中过一次 | 再次选择同一候选到同一目标 | 不得产生重复记录；可返回幂等成功或冲突 | P0 |
| PR-011 | Candidate跨项目越权 | 安全 | CAN_A1 属于 PA；UB 已登录或使用 PB 上下文 | 对 CAN_A1 执行选择/确认/删除等操作 | 返回 403/404；跨项目操作被阻断 | P0 |

---

## 3.3 crawl / SSRF / URL 校验

| ID | 模块 | 类型 | 前置条件 | 步骤 | 预期结果 | 优先级 |
|---|---|---|---|---|---|---|
| CR-001 | Crawl URL校验 | 正常 | UA 已登录，PA 存在 | 使用 URL_PUBLIC 发起 crawl | 请求被接受；创建 crawl run；后续按正常流程执行 | P0 |
| CR-002 | Crawl URL校验 | 异常 | 无 | 使用 URL_BAD 发起 crawl | 参数校验失败；返回 4xx；不发起任何外部请求 | P1 |
| CR-003 | SSRF协议限制 | 安全 | 无 | 使用 URL_FILE 发起 crawl | 被拒绝；禁止 file:// 等非允许协议 | P0 |
| CR-004 | SSRF本地回环 | 安全 | 无 | 使用 `localhost` / `127.0.0.1` URL 发起 crawl | 被拒绝；服务端不向本地地址发请求 | P0 |
| CR-005 | SSRF私网IPv4 | 安全 | 无 | 分别使用 `10.x`、`172.16-31.x`、`192.168.x` URL 发起 crawl | 全部被拒绝；不发出实际请求 | P0 |
| CR-006 | SSRF云元数据 | 安全 | 无 | 使用 URL_META 发起 crawl | 被拒绝；阻断对云 metadata 地址访问 | P0 |
| CR-007 | SSRF-DNS解析绕过 | 安全 | 受控 DNS 域名解析到私网 IP | 使用 URL_DNS_PRIVATE 发起 crawl | 服务端解析最终 IP 后拒绝；不应因域名表面合法而放行 | P0 |
| CR-008 | SSRF-重定向绕过 | 安全 | 受控重定向服务，302 到私网 IP | 使用 URL_REDIRECT_PRIVATE 发起 crawl | 首跳可访问但最终因目标私网被拒绝；不应跟进到内网 | P0 |
| CR-009 | SSRF-IPv6 | 安全 | 无 | 使用 `::1` 或 `fc00::/7` 等 IPv6 私网/回环地址 | 被拒绝；IPv6 规则与 IPv4 一致 | P0 |

---

## 3.4 图像处理容错（rembg / remove.bg / NumPy）

| ID | 模块 | 类型 | 前置条件 | 步骤 | 预期结果 | 优先级 |
|---|---|---|---|---|---|---|
| IM-001 | 图像处理-rembg | 正常 | rembg mock 为成功；IMG_OK_JPG 可用 | 上传图片并触发去背 | 任务成功完成；输出图片有效；状态 Completed | P0 |
| IM-002 | 图像处理-兜底 | 异常 | rembg mock 抛异常；remove.bg mock 成功 | 上传图片并触发去背 | 系统自动走兜底链路并成功；任务最终 Completed；有 fallback 标记/日志 | P0 |
| IM-003 | 图像处理-全失败 | 异常 | rembg 失败；remove.bg 失败 | 上传图片并触发去背 | 任务进入 Error；错误原因可追踪；无半成品脏数据暴露 | P0 |
| IM-004 | 图像处理-后处理异常 | 异常 | NumPy 后处理 mock 抛异常 | 完整执行去背流程 | 任务进入 Error；临时文件被清理；数据库状态一致 | P0 |
| IM-005 | 图像处理-损坏图片 | 边界/异常 | IMG_CORRUPT 可用 | 上传损坏图片 | 明确报错；服务不崩溃；不进入异常死循环 | P1 |
| IM-006 | 图像处理-伪装文件 | 安全/异常 | IMG_FAKE_JPG 可用 | 上传伪装成 jpg 的文本文件 | 被拒绝或处理失败但可控；不得产生有效图片结果 | P1 |
| IM-007 | 图像处理-大图边界 | 边界 | IMG_LARGE 可用 | 上传接近/超过限制的大图 | 按策略成功处理或清晰拒绝；不能 OOM/卡死；状态可追踪 | P1 |

---

## 3.5 API 边界 / 参数校验 / 认证授权

| ID | 模块 | 类型 | 前置条件 | 步骤 | 预期结果 | 优先级 |
|---|---|---|---|---|---|---|
| API-001 | API参数校验 | 异常 | UA 已登录 | 提交 name/project_id/url 等必填字段为空或缺失 | 返回 422/400；错误字段明确；不写库 | P0 |
| API-002 | API边界 | 边界 | UA 已登录 | 提交超长字符串（如 256/1024/4096 长度） | 按 schema 拒绝或截断（以契约为准）；不得写入脏值 | P1 |
| API-003 | API格式 | 异常 | UA 已登录 | 发送 malformed JSON 请求体 | 返回 400；服务不抛 500 | P0 |
| API-004 | API类型 | 异常 | UA 已登录 | 传错参数类型，如 `project_id=[]`、`page="abc"` | 返回 422；不进入业务层 | P0 |
| API-005 | API枚举 | 异常 | UA 已登录 | 提交非法 status/action/enum 值 | 返回 422/400；状态不变 | P0 |
| API-006 | API分页边界 | 边界 | UA 已登录 | 传 `page=0`、`page_size=-1`、超大 page_size | 被拒绝或按契约钳制；不得导致全表扫描风险 | P1 |
| API-007 | Content-Type校验 | 异常 | UA 已登录 | JSON 接口发 `text/plain`；上传接口发错 Content-Type | 返回 415/422；不误解析 | P1 |
| API-008 | 认证 | 安全 | 无 token | 访问任意需登录接口 | 返回 401 | P0 |
| API-009 | 认证 | 安全 | 使用 ExpiredToken 或 InvalidToken | 访问任意需登录接口 | 返回 401；提示 token 无效/过期 | P0 |
| API-010 | 授权 | 安全 | TokenA 仅有 PA 权限 | 使用 TokenA 访问 PB 的资源 | 返回 403/404；不泄露 PB 数据 | P0 |

---

## 3.6 前端状态同步 / 冲突刷新 / 错误态展示

| ID | 模块 | 类型 | 前置条件 | 步骤 | 预期结果 | 优先级 |
|---|---|---|---|---|---|---|
| FE-001 | 前端轮询同步 | 正常 | 打开任务列表页；某任务后台会从 Running 变 Completed | 等待轮询周期 | UI 自动刷新为最新状态；无需手动刷新页面 | P0 |
| FE-002 | 前端冲突处理 | 异常/并发 | 页面持有旧 version；后端资源已被他处更新 | 在前端发起状态变更，后端返回 409 | 前端自动 invalidate/refetch；展示最新状态和提示信息 | P0 |
| FE-003 | 前端幂等保护 | 并发 | 打开任务详情页 | 用户快速双击 start/complete/cancel 按钮 | 按钮 loading/禁用；最多 1 次有效操作；无重复 toast/脏状态 | P0 |
| FE-004 | 前端错误态展示 | 异常 | 某任务后端进入 Error，带 error_message | 打开列表/详情页 | 页面显示 Error 状态与错误原因；可见可执行恢复动作（若支持） | P0 |
| FE-005 | 前端网络异常恢复 | 异常 | 模拟接口超时/短暂断网 | 在页面执行操作后网络失败，再恢复网络 | UI 给出错误提示/重试入口；恢复后与后端状态重新对齐 | P1 |
| FE-006 | 多标签页陈旧数据 | 并发 | Tab A 与 Tab B 同时打开同一任务 | Tab B 完成状态修改；回到 Tab A | Tab A 在 focus/轮询后刷新为最新状态；避免继续误操作 | P1 |
| FE-007 | 软删除后的页面行为 | 异常 | 用户停留在项目详情页；项目被他处软删除 | 触发后续查询/操作 | 页面收到 404/410 后自动跳转列表或给出明确提示；清理陈旧缓存 | P0 |
| FE-008 | 列表缓存失效 | 正常/异常 | 项目/任务/候选列表已加载 | 执行删除、状态变更、候选去重冲突等动作 | React Query 缓存正确失效；列表与详情一致；无需硬刷新 | P1 |

---

# 4. 建议的测试数据与测试环境

## 4.1 测试环境建议

### 后端环境
- Python 3.11+
- FastAPI
- SQLAlchemy
- MySQL 8.0 作为主验证库
- SQLite 作为兼容回归库

### 前端环境
- Node 18/20
- React 18 + TypeScript
- Chrome 最新版
- Firefox 最新版（至少做核心回归）

### 部署方式
- 建议使用 **Docker Compose** 拉起：
  - app-backend
  - app-frontend
  - mysql
  - mock-removebg
  - ssrf-redirect-server
  - ssrf-dns-lab（CoreDNS/dnsmasq）
  - object storage / local temp dir

### 外部服务 Mock
1. **remove.bg mock**
   - 成功返回
   - 失败返回 500
   - 超时返回
2. **rembg mock/monkeypatch**
   - 正常
   - 抛异常
   - 超时
3. **NumPy 后处理 mock**
   - 正常
   - 抛异常
4. **SSRF lab**
   - 公网假地址
   - 私网解析域名
   - 302 跳转到私网
   - metadata 地址探测

---

## 4.2 建议测试数据

### 账号
- `user_a / TokenA`
- `user_b / TokenB`
- `expired_user / ExpiredToken`
- `invalid_sig / InvalidToken`

### 项目
- `PA`：活跃项目
- `PB`：另一用户活跃项目
- `PDEL`：软删除项目

### 分类
- `Shoes`（PA）
- `Shoes`（PB，同名隔离验证）
- `DUP_CAT`（重复创建用）

### 会话线程
- `TH_A1`：属于 PA，确认 `project_id=PA`

### 候选
- `CAN_A1`：属于 PA
- `CAN_B1`：属于 PB

### 任务
- 每种状态各准备 1~2 条
- 并发测试建议准备可重复 reset 的任务数据集
- 任务带 `version` 字段便于 CAS 验证

### 图片样本
- 正常 JPG / PNG
- 带透明通道 PNG
- 损坏图片
- 伪装文件
- 超大图片
- 超高分辨率图片
- EXIF 异常图片（可选）

### URL 样本
- 合法公网 https
- 非法 scheme
- localhost / 127.0.0.1
- 10.x / 172.16.x / 192.168.x
- 169.254.169.254
- DNS 解析到私网
- 302 跳转到私网
- IPv6 loopback / ULA

---

## 4.3 建议使用的工具
- **后端自动化**：pytest、pytest-asyncio、httpx、pytest-xdist
- **前端 E2E**：Playwright
- **Mock**：WireMock / MockServer / monkeypatch
- **安全辅助**：OWASP ZAP（做基础扫）、mitmproxy（观察请求）
- **并发**：locust 或自定义并发脚本
- **覆盖率**：pytest-cov

---

# 5. 推荐的测试执行顺序

建议按以下顺序执行，避免前置能力未验证就进入复杂场景：

## 阶段 0：环境检查 / Smoke
1. 数据库迁移成功
2. 前后端服务健康检查通过
3. 基础登录、列表页、创建项目可用
4. Mock 服务正常

## 阶段 1：P0 安全与数据一致性回归
优先执行所有已修复 P0 相关：
1. **API-008 ~ API-010**：认证授权
2. **PR-002 ~ PR-011**：项目隔离、软删除、唯一约束、thread project_id、candidate 越权
3. **TS-001 ~ TS-011**：状态机、CAS、幂等、失败恢复、并发
4. **CR-001 ~ CR-009**：SSRF 全链路
5. **IM-001 ~ IM-004**：图像处理成功/兜底/全失败/后处理异常

## 阶段 2：API 边界与异常
1. API-001 ~ API-007
2. 图像上传非法输入 IM-005 ~ IM-007

## 阶段 3：前端一致性与体验
1. FE-001 ~ FE-008
2. 重点验证冲突自动刷新、错误态展示、删除后页面行为

## 阶段 4：数据库兼容回归
1. 在 **MySQL** 完整跑 P0/P1
2. 在 **SQLite** 至少跑：
   - 基础 CRUD
   - 参数校验
   - 状态机核心路径
   - 前端基础 E2E
> 注：并发/CAS/唯一约束更建议以 MySQL 结果为主，SQLite 仅做兼容参考

## 阶段 5：回归收尾
1. 数据一致性检查
   - 是否有重复 candidate relation
   - 是否有非法 task state
   - 是否有软删除项目的可见脏数据
   - 是否有 orphan 临时文件
2. 日志检查
   - SSRF 是否有被阻断记录
   - 图像失败是否有完整错误栈
   - CAS 冲突是否有清晰日志

---

# 6. 建议的自动化优先级

## 必须进 CI 的 P0 自动化
- TS-001 ~ TS-011
- PR-002 ~ PR-011
- CR-001 ~ CR-009
- IM-001 ~ IM-004
- API-008 ~ API-010
- FE-001 ~ FE-004、FE-007

## 夜间构建建议覆盖
- 全量 API 边界
- 大图/异常图
- 多浏览器前端 E2E
- SQLite 兼容回归

---

# 7. 建议的通过标准（Exit Criteria）

建议本轮版本的发布门槛为：

1. **P0 用例 100% 通过**
2. **P1 用例通过率 ≥ 95%**
3. 无新增高危安全问题
4. 无数据一致性问题：
   - 无重复候选选择记录
   - 无非法任务状态
   - 无已软删项目残留可访问资源
5. 并发测试中：
   - 无重复任务领取
   - 无 CAS 覆盖写
   - 无前端冲突后错误展示
6. 图像处理失败场景中：
   - 无 worker 崩溃
   - 无临时文件泄漏
   - 错误状态可追踪

---

如果你愿意，我下一步可以继续给你输出两份落地文档之一：

1. **pytest / Playwright 自动化用例骨架**  
2. **Excel/测试管理系统可直接导入的测试用例表格格式（CSV风格）**

如果需要，我可以直接把这 56 条用例整理成 **更适合测试平台导入的标准表格格式**。