# 接入生图 API 说明

当前系统支持以下图片 Provider：

- `local_demo`：使用本地生成的渐变背景，适合离线演示和无额度验证
- `generic_http`：向你配置的通用 HTTP 接口发送 JSON 请求
- `qwen_image`：接入通义千问图片接口
- `zhipu_image`：接入智谱图片接口

## 推荐接法

如果你的供应商接口不是完全固定的标准格式，优先使用 `generic_http`。

设置页建议按下面顺序填写：

1. 保存 `Image API Key`
2. 保存 `Image Provider`
3. 保存 `Image API URL`
4. 保存 `Image Model`
5. 保存 `Image Timeout Seconds`
6. 保存 `Image API Key Header`
7. 点击“测试生图接口”

如果你的供应商使用 `Authorization: Bearer <key>`，`Image API Key Header` 保持默认 `Authorization` 即可。

如果供应商使用 `X-API-Key: <key>`，把这个字段改成 `X-API-Key`。

## 系统发送的请求

### generic_http

系统会向你填写的 `Image API URL` 发送 `POST` 请求，请求体大致如下：

```json
{
  "model": "your-model-name",
  "prompt": "Create a premium ecommerce background for a Taobao product image...",
  "width": 1200,
  "height": 1200
}
```

### qwen_image

系统会向千问图片接口发送多模态消息体：

```json
{
  "model": "qwen-image-2.0",
  "input": {
    "messages": [
      {
        "role": "user",
        "content": [
          { "text": "请生成适合淘宝主图的无字背景图" }
        ]
      }
    ]
  },
  "parameters": {
    "negative_prompt": "不要文字，不要英文，不要字母，不要数字，不要水印，不要 logo"
  }
}
```

如果当前回合带了白底产品图，系统会把参考图一起传入，帮助模型理解主体类型。

### zhipu_image

系统会向智谱图片接口发送如下 JSON：

```json
{
  "model": "cogview-4-250304",
  "prompt": "请生成适合淘宝主图的无字背景图",
  "size": "1200x1200"
}
```

## 系统可识别的返回格式

后端当前支持以下常见返回结构：

### `data[0].b64_json`

```json
{
  "data": [
    {
      "b64_json": "..."
    }
  ]
}
```

### 顶层 `b64_json`

```json
{
  "b64_json": "..."
}
```

### 顶层 URL

```json
{
  "url": "https://..."
}
```

### 千问消息结构

```json
{
  "output": {
    "choices": [
      {
        "message": {
          "content": [
            {
              "image": "https://..."
            }
          ]
        }
      }
    ]
  }
}
```

## 失败时的行为

- 如果外部生图接口调用成功，背景图会优先使用外部 API 返回结果。
- 如果接口超时、返回结构不匹配、Key 不正确或 URL 不可用，系统会自动回退到 `local_demo` 背景生成，不会阻断主流程。
- 产品主体合成、标题叠字、卖点叠字、审核和定稿流程不受影响。

## 如果你的返回结构不一致

大多数情况下不需要改代码，只需要通过设置页保存配置。

如果你的供应商返回结构和上述几种都不一致，再调整下面这个文件里的解析逻辑即可：

- `backend/app/services/model_gateway.py`

主要入口方法：

- `render_background`
- `_render_generic_http_background`
- `_render_qwen_image_background`
- `_render_zhipu_image_background`
- `_decode_image_payload`
