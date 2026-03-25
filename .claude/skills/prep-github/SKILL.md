# /prep-github — GitHub 发布准备

准备项目推送到 GitHub。

## 步骤
1. 检查 .gitignore 是否覆盖敏感文件（.env、node_modules、__pycache__、storage/、data/）
2. 检查是否有硬编码的密钥、密码、API key（排除 .env.example 中的占位符）
3. 确认 README.md 存在且内容合理
4. 运行 git status 查看未提交的变更
5. 列出建议的 commit message

## 规则
- 只做检查和建议，不自动 commit 或 push
- 发现敏感信息立即警告用户
- 所有操作完成后等待用户确认再执行任何 git 命令
