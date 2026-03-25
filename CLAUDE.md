# Project: 电商内容Agent

## 核心规则（必须遵守）

1. **重大操作需用户确认**：以下操作必须先告知用户并等待明确同意后才能执行：
   - 删除文件、分支、数据库表等破坏性操作
   - 下载、安装软件包或系统依赖
   - 从 plan 模式进入实施阶段（ExitPlanMode 后开始写代码前）
   - git push、创建 PR 等影响远程仓库的操作
   - 修改系统配置或环境变量
2. **中国网络环境**：安装包时优先使用国内镜像源（如 `https://pypi.tuna.tsinghua.edu.cn/simple`），避免直接访问被墙的服务。
3. **Python 优先**：生成文档（Word/PDF）时优先使用 python-docx，不依赖 pandoc 等外部工具。
4. **禁止伪造数据**：价格、性能参数、API 文档等事实性数据必须来自可验证的来源（官网、搜索结果）。不确定的数据标注"待验证"，不要编造。开发中同理：不确定的 API 接口、参数、返回值必须先查文档确认。

AI-driven e-commerce content generation platform. Users upload product images or competitor links, the system generates white-background cutouts, scene images, videos, and multi-platform marketing copy.

## Tech Stack
- **Frontend**: React 18 + TypeScript + Vite + Ant Design 5 + React Query (TanStack)
- **Backend**: FastAPI + SQLAlchemy + Pydantic + Pillow + NumPy
- **Database**: MySQL (default) / SQLite (fallback)
- **AI Providers**: LLM (zhipu_glm, codex_ai) + Image (qwen_image, zhipu_image, generic_http) + local_demo fallback

## Key Architecture

### Backend (`backend/app/`)
- `main.py` — FastAPI entry, CORS, SPA routing, logging setup
- `core/config.py` — Settings from env vars (`.env`)
- `core/security.py` — Fernet encryption for API keys, PBKDF2-600k password hashing, JWT tokens
- `models.py` — SQLAlchemy ORM: User, Project, Version, Asset, ChatMessage, BrandProfile, SystemSetting
- `schemas.py` — Pydantic request/response models
- `text_utils.py` — Shared `looks_broken_text()` utility (used by db.py and generation.py)
- `db.py` — Engine, session, schema init, seed data
- `api/routes/` — auth, projects, upload, brand, settings
- `api/dependencies.py` — `get_current_user()` JWT auth dependency
- `services/generation.py` — `ProjectService`: project CRUD, version management, generation orchestration. All db.commit() wrapped with try/except rollback.
- `services/model_gateway.py` — `ModelGateway`: LLM + image provider abstraction, prompt building, SSRF-protected image download
- `services/image_pipeline.py` — `ImagePipeline`: NumPy-vectorized background removal, composition, cross-platform font loading
- `services/storage.py` — `StorageService`: file I/O in uploads/processed/exports buckets
- `services/system_settings.py` — `SystemSettingsService`: API keys (Fernet-encrypted), provider config, presets

### Frontend (`frontend/src/`)
- `App.tsx` — Routes wrapped in ErrorBoundary + ConfigProvider
- `components/ErrorBoundary.tsx` — React class error boundary
- `components/AppShell.tsx` — Sidebar layout
- `lib/api.ts` — Typed API client with 30s timeout (AbortController)
- `lib/auth.ts` — localStorage token management
- `lib/types.ts` — All TypeScript interfaces
- `lib/version-utils.ts` — Shared `getVersionRunInfo()`
- `pages/CreatePage.tsx` — Main workspace (chat + upload + generation), uses useMemo for derived state
- `pages/ProjectsPage.tsx` — Project list with client-side pagination (12/page)
- `pages/ProjectDetailPage.tsx` — Version review/approve/reject/finalize/derive
- `pages/BrandPage.tsx` — Brand profile editor
- `pages/SettingsPage.tsx` — LLM/image provider configuration + presets

## Core Business Flow
1. Login (default: admin/admin123, WARNING logged on startup)
2. Upload product image → create project
3. Chat with agent → LLM plans generation or continues discussion
4. Generate: LLM prompt → image provider background → NumPy cutout → PIL composite
5. Version tree: review (approve/reject) → finalize → derive

## Recent Changes (2026-03-25)
Security: XOR→Fernet encryption, PBKDF2 600k iterations, SSRF protection, path traversal fix, startup warnings for default credentials.
Performance: NumPy vectorized cutout, batch status refresh, frontend pagination, useMemo.
Robustness: logging system, exception logging instead of silent swallow, PIL error handling, DB transaction rollback.
Architecture: shared text_utils.py + version-utils.ts, ErrorBoundary, typed API layer, cross-platform fonts.

## Default Credentials
- Username: `admin`, Password: `admin123` (env: APP_DEFAULT_ADMIN_USERNAME / APP_DEFAULT_ADMIN_PASSWORD)
- JWT Secret: `demo-secret-change-me` (env: APP_SECRET_KEY) — MUST change for production

## Running
- `start-app.cmd` — launches both frontend and backend
- Backend: `cd backend && uvicorn app.main:app --reload --port 8000`
- Frontend dev: `cd frontend && npm run dev` (port 5173)
- Production: backend serves frontend build from `frontend/dist/`
