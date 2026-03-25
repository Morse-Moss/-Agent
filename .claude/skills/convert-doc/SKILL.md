# /convert-doc — Markdown 转 Word 文档

将指定的 Markdown 文件转换为 Word (.docx) 格式。

## 规则
1. 询问用户要转换哪些 .md 文件
2. 每个 .md 文件生成一个独立的 .docx 文件（不要合并）
3. 使用 python-docx 库，不依赖 pandoc
4. 保留标题层级、加粗/斜体、列表、代码块格式
5. 输出文件保存在同目录下，文件名与源文件一致（仅扩展名不同）
6. 完成后列出所有生成的文件路径
