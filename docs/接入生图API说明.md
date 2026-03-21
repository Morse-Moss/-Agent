# 接入生图 API 说明

当前系统支持三种图片 Provider：

- `local_demo`：使用本地生成的渐变背景，适合离线演示
- `generic_http`：向你配置的 HTTP 接口发送通用 JSON 请求
- `openai_compatible`：向兼容 OpenAI Images 风格的接口发送请求

## 推荐接法

如果你的供应商接口不是完全固定的 OpenAI Images 格式，优先使用 `generic_http`。

设置页建议按下面顺序填写：

1. 保存 `Image API Key`
2. 保存 `Image Provider = generic_http`
3. 保存 `Image API URL`
4. 保存 `Image Model`
5. 保存 `Image Timeout Seconds`
6. 保存 `Image API Key Header`
7. 点击“测试生图 Provider”

如果你的供应商使用 `Authorization: Bearer <key>`，`Image API Key Header` 保持默认 `Authorization` 即可。  
如果供应商使用 `X-API-Key: <key>`，把这个字段改成 `X-API-Key`。

## 系统发送的请求

### generic_http

系统会向你填写的 `Image API URL` 发送 `POST` 请求，请求体大致如下：

```json
{
  "model": "your-model-name",
  "prompt": "Create a premium ecommerce background for a Taobao product image...",
  "negative_prompt": "text, watermark, logo, duplicate product, deformed product",
  "width": 1200,
  "height": 1200,
  "style_keywords": ["工业简洁", "金属质感"],
  "page_type": "main_image",
  "metadata": {
    "product_name": "广告材料铝材",
    "brand_name": "铝域精选",
    "selling_points": ["耐腐蚀", "支持定制"]
  }
}
```

### openai_compatible

系统会发送类似下面的 JSON：

```json
{
  "model": "gpt-image-1",
  "prompt": "Create a premium ecommerce background for a Taobao product image...",
  "size": "1024x1024"
}
```

## 系统可识别的返回格式

后端当前支持以下几种常见返回结构：

### 顶层 base64

```json
{
  "image_base64": "..."
}
```

### OpenAI 风格 b64_json

```json
{
  "data": [
    {
      "b64_json": "..."
    }
  ]
}
```

也支持：

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

### 嵌套 result

```json
{
  "result": {
    "image_base64": "..."
  }
}
```

### 直接返回图片二进制

如果接口直接返回 `image/png`、`image/jpeg` 等二进制内容，系统也能直接识别并使用。

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
- `_render_openai_compatible_background`
- `_decode_image_payload`
