# 电商美工 Agent Demo

一个面向企业内部场景的电商美工 Agent Demo，聚焦“基于白底产品图和自然语言需求，生成可继续迭代的电商视觉版本”。

当前版本已经覆盖：

- 对话式创作工作台
- 白底图上传与主图生成
- 项目 / 版本 / 资产管理
- 审核、驳回、定稿与派生
- 品牌资料与风格总结
- LLM / 图片 Provider 配置与预设切换
- MySQL 迁移与单入口部署

## 适用场景

- 企业内部电商美工辅助
- 淘宝主图 Demo 演示
- 图像生成工作流原型
- 多模型配置与切换测试

## 核心流程

1. 登录系统
2. 上传白底产品图或直接输入创作需求
3. 在工作台与 Agent 聊天，确认方向
4. 生成版本并继续修改
5. 审核、定稿、派生新版本
6. 通过设置页切换 LLM / 图片模型

## 技术栈

- 前端：React + TypeScript + Vite + Ant Design
- 后端：FastAPI + SQLAlchemy + Pillow
- 数据库：MySQL
- 文件存储：本地磁盘
- 模型接入：统一 Model Gateway

## 当前已支持的模型能力

- LLM Provider：`local_demo`、`codex_ai`、`zhipu_glm`
- 图片 Provider：`local_demo`、`qwen_image`、`zhipu_image`
- 设置页支持保存和切换模型预设，避免反复手填整套参数

## 快速启动

### 开发模式

分别启动前后端：

```bat
start-backend.cmd
start-frontend.cmd
```

访问：

```text
http://127.0.0.1:5173
```

### 单入口模式

由后端统一托管前端页面和 `/api`：

```bat
start-app.cmd
```

访问：

```text
http://127.0.0.1:8000
```

## 默认账号

- 用户名：`admin`
- 密码：`admin123`

正式部署前请修改默认管理员密码，并替换 `APP_SECRET_KEY`。

## 目录说明

- `frontend/`：前端代码
- `backend/`：后端代码
- `docs/guides/`：公开使用文档
- `scripts/dev/`：开发和检查脚本
- `scripts/ops/`：数据库、恢复、迁移和运维脚本
- 根目录 `*.cmd`：常用启动入口

## 文档入口

- [文档导航](docs/README.md)
- [使用说明](docs/guides/使用说明.md)
- [接入生图 API 说明](docs/guides/接入生图API说明.md)
- [部署与迁移说明](docs/guides/部署与迁移说明.md)
- [接口示例](docs/guides/api-examples.http)

## 说明

- 仓库默认不提交运行时数据、环境变量、生成图片、本地数据库和交付用 Word 成品。
- 迁移到新电脑时，需要同时恢复数据库和 `backend/storage/` 资产目录，不能只复制代码。
