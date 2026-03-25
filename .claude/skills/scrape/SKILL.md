# /scrape — 网站数据爬取

用 Playwright 爬取指定网站的结构化数据。支持两种模式：无头模式（不需登录）和登录模式（需要用户扫码/输入密码）。

## 使用方式
```
/scrape <URL或平台名> [--login] [--items 关键词列表]
```
示例：
- `/scrape https://example.com/products` — 无头模式爬取
- `/scrape 淘宝 --login --items "RTX 4060 Ti, DDR5 32GB, B650M主板"` — 登录淘宝后批量搜索
- `/scrape 1688 --login --items "洗手盆 立柱"` — 登录1688后搜索商品

## 流程

### 模式一：无头模式（默认）
1. 用 Playwright headless 访问目标 URL
2. 等待页面加载 + 滚动触发懒加载
3. 用 page.evaluate() 提取结构化数据（标题、价格、图片等）
4. 输出 JSON 数据文件

### 模式二：登录模式（--login）
1. 用 Playwright 有头模式（headless=False）打开登录页
2. 在终端提示用户："请在浏览器中登录，完成后按 Enter"
3. 用 input() 等待用户确认（不要自动检测登录状态）
4. 登录后逐个搜索 --items 中的关键词
5. 每个关键词：访问搜索页 → 滚动加载 → 提取数据
6. 输出 JSON 数据文件

## 生成脚本规范
- 脚本保存到 `tools/scrape_<平台名>.py`
- 环境变量：`PLAYWRIGHT_BROWSERS_PATH=G:/playwright-browsers`
- User-Agent 使用真实 Chrome UA
- 每次翻页/搜索间隔 2-3 秒，避免触发反爬
- 提取失败时截图保存到 `reports/` 用于调试
- 数据输出到 `reports/<平台名>_prices.json`

## 数据输出格式
```json
{
  "搜索关键词": [
    {"title": "商品标题", "price": "¥xxx", "shop": "店铺名", "url": "链接"},
    ...
  ]
}
```

## 规则
- 生成脚本前先告知用户：目标平台、爬取项、预计耗时
- 脚本生成后提示用户手动运行（因为登录模式需要 GUI）
- 不在 Claude Code 内直接运行有头浏览器脚本
- 遵守网站 robots.txt，控制请求频率
- 登录凭证由用户在浏览器中输入，脚本不存储任何密码
