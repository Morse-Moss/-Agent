# /preflight-check — 环境预检

启动前自动检查开发环境是否就绪。

## 检查项（逐项执行，报告通过/失败）
1. Python 版本 ≥ 3.11 且在 PATH 中
2. pip 可用，backend/requirements.txt 中的核心包已安装
3. Node.js ≥ 18 且 npm 可用
4. frontend/node_modules 存在（否则提示 npm install）
5. MySQL 连接可用（或 SQLite 降级可用）
6. backend/.env 文件存在且包含必要配置
7. Redis 连接（可选，标记为 optional）
8. Qdrant 连接（可选，标记为 optional）

## 规则
- 每项检查用 Bash 执行，输出 ✓ 通过 或 ✗ 失败
- 失败项给出修复建议
- 可选项失败不阻塞，标注为"降级运行"
- 最后给出总结：几项通过/几项失败/几项可选跳过
