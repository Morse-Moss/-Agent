# 电商美工 Agent Demo

一个面向企业内部场景的电商美工 Agent Demo，聚焦“对白底产品图和自然语言需求进行理解，然后生成可继续迭代的电商视觉版本”。当前版本重点覆盖淘宝主图创作、版本记录、审核定稿、品牌资料管理和第三方生图 Provider 接入。

## 当前能力

- 对话式创作工作台
- 白底图上传与主图生成
- 项目 / 版本 / 资产结构管理
- 审核、驳回、定稿与派生
- 品牌资料与风格总结
- API Key 与 Provider 配置
- 单入口部署模式

## 技术栈

- 前端：React + TypeScript + Vite + Ant Design
- 后端：FastAPI + SQLAlchemy + Pillow
- 默认数据库：MySQL
- 文件存储：本地磁盘
- 模型接入：统一 Model Gateway

## 快速启动

### 开发模式

分别启动前后端：

```bat
start-backend.cmd
start-frontend.cmd
```

访问地址：

```text
http://127.0.0.1:5173
```

### 单入口模式

前端构建后由后端统一托管：

```bat
start-app.cmd
```

访问地址：

```text
http://127.0.0.1:8000
```

## 默认账号

- 用户名：`admin`
- 密码：`admin123`

正式部署前请务必修改默认管理员密码，并设置新的 `APP_SECRET_KEY`。

## 数据与目录

- 数据库连接：`backend/.env`
- 图片与生成资产目录：`backend/storage/`
- 前端项目：`frontend/`
- 后端项目：`backend/`
- 使用与部署文档：`docs/guides/`
- 内部源稿与进度记录：`docs/internal/`
- Word 交付文档：`docs/deliverables/`
- 启动脚本入口：根目录 `*.cmd`
- 分层脚本目录：`scripts/dev/`、`scripts/ops/`、`scripts/docs/`、`scripts/assets/`

## 文档导航

建议优先阅读这些文档：

- [文档导航](docs/README.md)
- [使用说明](docs/guides/使用说明.md)
- [接入生图 API 说明](docs/guides/接入生图API说明.md)
- [部署与迁移说明](docs/guides/部署与迁移说明.md)
- [接口示例](docs/guides/api-examples.http)

## 部署说明

当前默认使用 MySQL。如果只是为了快速演示或本地调试，也可以切换回 SQLite。

如果后续需要切换数据库：

1. 安装 `backend/requirements-mysql.txt`
2. 修改 `APP_DATABASE_URL`
3. 重新启动后端服务

## 说明

- 仓库默认不提交运行时数据、环境变量、生成图片和本地 Word 成品。
- 内部版本总结、PRD 源稿和阶段性过程文档默认本地保留，不作为公开仓库主内容。
