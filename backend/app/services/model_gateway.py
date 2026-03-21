from __future__ import annotations

import base64
import io
import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from PIL import Image

from ..core.config import settings
from .system_settings import GatewayRuntimeConfig

DEFAULT_SELLING_POINTS = ["耐腐蚀", "高强度", "规格齐全", "支持定制"]
DEFAULT_STYLE_KEYWORDS = ["工业简洁", "金属质感", "高级感"]
SELLING_POINT_ALIASES = [
    ("耐腐蚀", ["耐腐蚀", "corrosion resistant", "anti-corrosion"]),
    ("高强度", ["高强度", "high strength"]),
    ("规格齐全", ["规格齐全", "full specs", "full specification"]),
    ("支持定制", ["支持定制", "customizable", "custom", "made to order"]),
]
STYLE_KEYWORD_ALIASES = [
    ("高级感", ["高级感", "高级", "premium"]),
    ("简洁", ["简洁", "clean"]),
    ("工业感", ["工业感", "工业", "industrial"]),
    ("金属质感", ["金属质感", "金属", "metal", "texture", "质感"]),
    ("科技感", ["科技感", "科技", "tech"]),
    ("明亮", ["明亮", "bright"]),
    ("深色", ["深色", "dark"]),
    ("极简", ["极简", "minimal"]),
]
KNOWN_STYLE_KEYWORDS = [
    "高级",
    "简洁",
    "工业",
    "金属",
    "科技",
    "质感",
    "明亮",
    "深色",
    "极简",
    "premium",
    "clean",
    "industrial",
    "metal",
    "tech",
    "texture",
    "bright",
    "dark",
    "minimal",
]
ALUMINUM_HINT_TERMS = [
    "铝材",
    "广告材料",
    "铝板",
    "铝单板",
    "铝型材",
    "铝方通",
    "金属板材",
    "aluminum",
    "aluminium",
    "metal",
    "panel",
    "profile",
    "sheet",
    "material",
]
PRODUCT_NAME_ALIASES = [
    ("广告材料铝单板", ["铝单板", "aluminum panel", "aluminium panel"]),
    ("广告材料铝型材", ["铝型材", "aluminum profile", "aluminium profile"]),
    ("广告材料铝方通", ["铝方通"]),
    ("广告材料铝板", ["铝板", "aluminum sheet", "aluminium sheet"]),
    ("广告材料铝材", ["广告材料铝材", "广告材料", "铝材", "aluminum", "aluminium", "metal material"]),
]
VISUAL_HINT_ALIASES = [
    ("深色背景", ["深色", "暗色", "dark"]),
    ("明亮背景", ["明亮", "bright"]),
    ("工业车间场景", ["车间", "工厂", "厂房", "factory"]),
    ("材料展厅场景", ["展厅", "showroom"]),
    ("建筑装饰场景", ["建筑", "外立面", "幕墙"]),
    ("极简棚拍场景", ["棚拍", "工作室", "studio", "纯背景"]),
    ("斜切构图", ["斜切", "斜向", "diagonal"]),
    ("产品特写", ["特写", "近景", "close-up"]),
]


@dataclass
class DemoBrandContext:
    name: str
    description: str
    style_summary: str
    recommended_keywords: list[str]


class ModelGateway:
    def __init__(self, runtime_config: GatewayRuntimeConfig | None = None) -> None:
        self.runtime_config = runtime_config or GatewayRuntimeConfig()

    def summarize_brand(self, description: str) -> dict[str, Any]:
        keywords = []
        source_text = description or ""
        for keyword in ["工业简洁", "金属质感", "支持定制", "耐腐蚀", "稳定供货", "高强度"]:
            if keyword in source_text or len(keywords) < 3:
                keywords.append(keyword)
        deduped = list(dict.fromkeys(keywords))[:5]
        return {
            "style_summary": f"品牌整体更适合简洁、工业化、偏金属质感的表达方式，重点突出材质、稳定供货与定制能力。参考描述：{description}",
            "recommended_keywords": deduped or DEFAULT_STYLE_KEYWORDS,
        }

    def plan_generation(
        self,
        *,
        message: str,
        guide_fields: dict[str, Any],
        brand_context: DemoBrandContext,
        previous_snapshot: dict[str, Any] | None,
        project_defaults: dict[str, Any],
        user_turns: int,
    ) -> dict[str, Any]:
        snapshot = dict(previous_snapshot or {})
        snapshot["page_type"] = guide_fields.get("page_type") or snapshot.get("page_type") or project_defaults.get("page_type") or "main_image"
        snapshot["platform"] = guide_fields.get("platform") or snapshot.get("platform") or project_defaults.get("platform") or "taobao"

        product_name = (
            self._normalize_product_name(guide_fields.get("product_name"))
            or self._normalize_product_name(snapshot.get("product_name"))
            or self._normalize_product_name(project_defaults.get("product_name"))
            or self._extract_product_name(message)
        )
        selling_points = (
            self._normalize_selling_points(guide_fields.get("selling_points"))
            or self._extract_selling_points(message)
            or self._normalize_selling_points(snapshot.get("selling_points"))
            or []
        )
        style_keywords = (
            self._normalize_style_keywords(guide_fields.get("style_keywords"))
            or self._extract_style_keywords(message)
            or self._normalize_style_keywords(snapshot.get("style_keywords"))
            or []
        )

        questions: list[str] = []
        should_clarify = False
        if not message.strip() and user_turns <= 1:
            questions.append("你希望这张图主要表现什么内容？")
            should_clarify = True

        if not selling_points:
            selling_points = DEFAULT_SELLING_POINTS[:2]
        if not style_keywords:
            merged_keywords = list(brand_context.recommended_keywords or []) + DEFAULT_STYLE_KEYWORDS
            style_keywords = list(dict.fromkeys(merged_keywords))[:3]

        resolved_product_name = product_name or snapshot.get("product_name") or project_defaults.get("product_name") or "广告材料铝材"
        snapshot.update(
            {
                "product_name": resolved_product_name,
                "selling_points": selling_points[:2],
                "style_keywords": style_keywords[:3],
                "brand_name": brand_context.name,
                "brand_description": brand_context.description,
                "brand_style_summary": brand_context.style_summary,
                "recommended_keywords": brand_context.recommended_keywords,
                "latest_user_message": message,
                "title_text": self._build_title(resolved_product_name, selling_points[:2]),
                "image_provider_used": self.runtime_config.image_provider,
            }
        )

        return {
            "should_clarify": should_clarify,
            "questions": questions[:2],
            "snapshot": snapshot,
        }

    def render_background(self, snapshot: dict[str, Any], size: tuple[int, int]) -> Image.Image | None:
        try:
            return self.call_image_provider(snapshot, size)
        except Exception:
            return None

    def call_image_provider(self, snapshot: dict[str, Any], size: tuple[int, int]) -> Image.Image | None:
        provider_name = (self.runtime_config.image_provider or "local_demo").strip().lower()
        if provider_name == "local_demo":
            return None
        if not self.runtime_config.image_api_url:
            raise RuntimeError("未配置图片生成接口地址")

        if provider_name == "openai_compatible":
            return self._render_openai_compatible_background(snapshot, size)
        if provider_name == "generic_http":
            return self._render_generic_http_background(snapshot, size)
        if provider_name == "qwen_image":
            return self._render_qwen_image_background(snapshot, size)
        raise RuntimeError(f"不支持的图片 Provider: {provider_name}")

    def _render_openai_compatible_background(self, snapshot: dict[str, Any], size: tuple[int, int]) -> Image.Image:
        payload = {
            "model": self.runtime_config.image_model or "gpt-image-1",
            "prompt": self._build_background_prompt(snapshot),
            "size": self._format_openai_size(size),
        }
        response_payload = self._post_json(self.runtime_config.image_api_url or "", payload)
        return self._decode_image_payload(response_payload)

    def _render_generic_http_background(self, snapshot: dict[str, Any], size: tuple[int, int]) -> Image.Image:
        payload = {
            "model": self.runtime_config.image_model or "demo-main-image",
            "prompt": self._build_background_prompt(snapshot),
            "negative_prompt": self._build_negative_prompt(),
            "width": size[0],
            "height": size[1],
            "style_keywords": snapshot.get("style_keywords", []),
            "page_type": snapshot.get("page_type", "main_image"),
            "metadata": {
                "product_name": snapshot.get("product_name", ""),
                "brand_name": snapshot.get("brand_name", ""),
                "selling_points": snapshot.get("selling_points", []),
            },
        }
        response_payload = self._post_json(self.runtime_config.image_api_url or "", payload)
        return self._decode_image_payload(response_payload)

    def _render_qwen_image_background(self, snapshot: dict[str, Any], size: tuple[int, int]) -> Image.Image:
        payload = {
            "model": self.runtime_config.image_model or "qwen-image-2.0",
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": self._build_qwen_message_content(snapshot),
                    }
                ]
            },
            "parameters": {
                "negative_prompt": self._build_negative_prompt(),
                "prompt_extend": False,
                "watermark": False,
                "size": self._format_qwen_size(size),
            },
        }
        response_payload = self._post_json(self._normalize_qwen_image_url(self.runtime_config.image_api_url or ""), payload)
        return self._decode_image_payload(response_payload)

    def _normalize_qwen_image_url(self, url: str) -> str:
        normalized = url.rstrip("/")
        if normalized.endswith("/api/v1"):
            return normalized + "/services/aigc/multimodal-generation/generation"
        return normalized

    def _post_json(self, url: str, payload: dict[str, Any]) -> Any:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        api_key = self.runtime_config.image_api_key
        header_name = self.runtime_config.image_api_key_header or "Authorization"
        if api_key:
            if header_name.lower() == "authorization" and not api_key.lower().startswith("bearer "):
                headers[header_name] = f"Bearer {api_key}"
            else:
                headers[header_name] = api_key

        request_obj = request.Request(url=url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(request_obj, timeout=self.runtime_config.image_timeout_seconds) as response:
                content_type = response.headers.get_content_type()
                response_body_bytes = response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"图片接口返回 HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"图片接口请求失败: {exc.reason}") from exc

        if content_type.startswith("image/"):
            return response_body_bytes
        response_body = response_body_bytes.decode("utf-8")
        return json.loads(response_body)

    def _decode_image_payload(self, payload: Any) -> Image.Image:
        if isinstance(payload, bytes):
            return Image.open(io.BytesIO(payload)).convert("RGBA")
        if isinstance(payload, str):
            return self._decode_image_string(payload)
        if isinstance(payload, list) and payload:
            return self._decode_image_payload(payload[0])
        if isinstance(payload, dict):
            if payload.get("image") is not None:
                return self._decode_image_payload(payload["image"])
            if payload.get("image_url") is not None:
                return self._decode_image_payload(payload["image_url"])
            if payload.get("image_base64"):
                return self._image_from_base64(payload["image_base64"])
            if payload.get("b64_json"):
                return self._image_from_base64(payload["b64_json"])
            if payload.get("url"):
                return self._image_from_url(payload["url"])
            if isinstance(payload.get("content"), list) and payload["content"]:
                return self._decode_image_payload(payload["content"])
            if isinstance(payload.get("data"), list) and payload["data"]:
                return self._decode_image_payload(payload["data"][0])
            if isinstance(payload.get("message"), dict):
                return self._decode_image_payload(payload["message"])
            if isinstance(payload.get("choices"), list) and payload["choices"]:
                return self._decode_image_payload(payload["choices"][0])
            if isinstance(payload.get("output"), dict):
                return self._decode_image_payload(payload["output"])
            if isinstance(payload.get("result"), dict):
                return self._decode_image_payload(payload["result"])
        raise RuntimeError("图片接口返回结果里没有识别到可用图片字段")

    def _decode_image_string(self, value: str) -> Image.Image:
        normalized = value.strip()
        if normalized.startswith("http://") or normalized.startswith("https://"):
            return self._image_from_url(normalized)
        if normalized.startswith("data:image/"):
            return self._image_from_base64(normalized)
        if len(normalized) > 64:
            try:
                return self._image_from_base64(normalized)
            except Exception:
                pass
        raise RuntimeError("图片接口返回了字符串，但不是可用的图片 URL 或 base64 数据")

    def _image_from_base64(self, raw_value: str) -> Image.Image:
        cleaned = raw_value
        if "," in cleaned and cleaned.strip().startswith("data:"):
            cleaned = cleaned.split(",", 1)[1]
        binary = base64.b64decode(cleaned)
        return Image.open(io.BytesIO(binary)).convert("RGBA")

    def _image_from_url(self, url: str) -> Image.Image:
        sanitized_url = self._sanitize_url(url)
        request_obj = request.Request(url=sanitized_url, method="GET")
        with request.urlopen(request_obj, timeout=self.runtime_config.image_timeout_seconds) as response:
            binary = response.read()
        return Image.open(io.BytesIO(binary)).convert("RGBA")

    def _sanitize_url(self, url: str) -> str:
        parts = parse.urlsplit(url)
        safe_path = parse.quote(parse.unquote(parts.path), safe="/-._~")
        safe_query = parse.quote(parse.unquote(parts.query), safe="=&%-._~")
        return parse.urlunsplit((parts.scheme, parts.netloc, safe_path, safe_query, parts.fragment))

    def _build_background_prompt(self, snapshot: dict[str, Any]) -> str:
        user_request = str(snapshot.get("latest_user_message", "")).strip()
        product_name = str(snapshot.get("product_name", "")).strip()
        style_keywords = [str(item) for item in snapshot.get("style_keywords", []) if str(item).strip()]
        selling_points = [str(item) for item in snapshot.get("selling_points", []) if str(item).strip()]
        has_reference_image = bool(str(snapshot.get("source_image_path", "")).strip())

        context_lines: list[str] = []
        if product_name and product_name not in user_request:
            context_lines.append(f"产品类目：{product_name}")
        context_lines.append("优先遵循用户在聊天中的自然语言需求")
        if has_reference_image:
            if style_keywords:
                context_lines.append(f"可参考画面风格：{'、'.join(style_keywords)}")
            context_lines.append("整体输出适合淘宝电商主图或电商场景图")
            context_lines.append("请为后续产品主体摆放和中文文案叠加留出合适空间")
            if selling_points:
                context_lines.append(f"请通过材质、结构和场景氛围体现这些产品特征：{'、'.join(selling_points)}")
        else:
            if style_keywords:
                context_lines.append(f"画面风格可参考：{'、'.join(style_keywords)}")
            context_lines.append("请直接生成完整的商品主视觉，突出产品主体和材质表现")
            context_lines.append("这是无字主图底图，不是最终海报成稿")
            context_lines.append("不要做成海报排版，不要生成说明文字、标题条、贴纸、标签或大段文案")
            if selling_points:
                context_lines.append(f"请通过产品材质、结构和工艺细节自然体现这些特征：{'、'.join(selling_points)}，不要把它们写成文字")
        context_lines.append("默认不要生成文字、水印或 logo，除非用户明确要求")

        if not user_request:
            user_request = "请生成一张适合电商展示的产品场景图。"
        return user_request + "\n\n补充信息：\n- " + "\n- ".join(context_lines)

    def _build_qwen_message_content(self, snapshot: dict[str, Any]) -> list[dict[str, str]]:
        content: list[dict[str, str]] = []
        source_image_path = snapshot.get("source_image_path")
        if isinstance(source_image_path, str) and source_image_path.strip():
            data_url = self._image_file_to_data_url(source_image_path)
            if data_url:
                content.append({"image": data_url})
        content.append({"text": self._build_qwen_background_prompt(snapshot, bool(content))})
        return content

    def _build_qwen_background_prompt(self, snapshot: dict[str, Any], has_reference_image: bool) -> str:
        product_name = str(snapshot.get("product_name", "")).strip()
        style_keywords = self._normalize_style_keywords(snapshot.get("style_keywords"))
        selling_points = self._normalize_selling_points(snapshot.get("selling_points"))
        visual_hints = self._extract_visual_hints(str(snapshot.get("latest_user_message", "")))
        resolved_product_name = product_name or "广告材料铝材"

        lines: list[str] = []
        if has_reference_image:
            lines.append(f"请为{resolved_product_name}生成一张无字淘宝主图背景场景。")
            lines.append("已上传的图片仅用于理解产品材质、品类和形态特征，不要直接在画面中复制文字信息。")
            lines.append("背景需要适合后续摆放产品主体和中文文案，整体要干净、克制、像电商主图底图。")
            if style_keywords:
                lines.append(f"整体风格参考：{'、'.join(style_keywords)}。")
            if selling_points:
                lines.append(f"请通过材质、结构、工艺细节和场景氛围自然体现这些特征：{'、'.join(selling_points)}。")
        else:
            lines.append(f"请生成一张{resolved_product_name}的无字淘宝主图底图。")
            lines.append("主体要明确、真实、像工业材料商品摄影，不要做成海报封面。")
            lines.append("请重点表现产品本身、金属材质、结构细节和工业制造质感。")
            if style_keywords:
                lines.append(f"整体风格参考：{'、'.join(style_keywords)}。")
            if selling_points:
                lines.append(f"请通过产品材质、结构、工艺和使用场景自然体现这些特征：{'、'.join(selling_points)}。")
        if visual_hints:
            lines.append(f"附加视觉要求：{'、'.join(visual_hints)}。")
        lines.append("画面中绝对不要出现任何品牌名、标题、卖点、宣传语、标签、贴纸、说明文字。")
        lines.append("不要出现任何中文、英文、字母、数字、logo、水印、标题栏或大面积字块。")
        lines.append("如果需要体现品牌感，请通过构图、光线、配色和材质表现，不要直接写字。")
        return "\n".join(lines)

    def _build_negative_prompt(self) -> str:
        return "不要文字，不要中文，不要英文，不要字母，不要数字，不要标语，不要标签，不要贴纸，不要图标说明，不要水印，不要logo"

    def _image_file_to_data_url(self, relative_path: str) -> str | None:
        absolute_path = Path(settings.storage_dir) / relative_path
        if not absolute_path.exists() or not absolute_path.is_file():
            return None
        mime_type, _ = mimetypes.guess_type(absolute_path.name)
        if not mime_type:
            mime_type = "image/png"
        binary = absolute_path.read_bytes()
        encoded = base64.b64encode(binary).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def _format_openai_size(self, size: tuple[int, int]) -> str:
        width, height = size
        if width == height:
            return "1024x1024"
        if width > height:
            return "1536x1024"
        return "1024x1536"

    def _format_qwen_size(self, size: tuple[int, int]) -> str:
        return f"{size[0]}*{size[1]}"

    def _extract_product_name(self, message: str) -> str | None:
        normalized_message = message.strip()
        lowered = normalized_message.lower()
        for label, aliases in PRODUCT_NAME_ALIASES:
            if any(alias in normalized_message or alias in lowered for alias in aliases):
                return label
        for name in ALUMINUM_HINT_TERMS:
            if name in lowered:
                return "广告材料铝材"
        return None

    def _extract_selling_points(self, message: str) -> list[str]:
        return self._normalize_alias_values(message, SELLING_POINT_ALIASES, 2)

    def _extract_style_keywords(self, message: str) -> list[str]:
        return self._normalize_alias_values(message, STYLE_KEYWORD_ALIASES, 3)

    def _build_title(self, product_name: str, selling_points: list[str]) -> str:
        if selling_points:
            return f"{product_name} {selling_points[0]}"
        return f"{product_name} 支持定制"

    def _normalize_product_name(self, raw_value: Any) -> str | None:
        if raw_value is None:
            return None
        text = str(raw_value).strip()
        if not text:
            return None
        lowered = text.lower()
        for label, aliases in PRODUCT_NAME_ALIASES:
            if any(alias in text or alias in lowered for alias in aliases):
                return label
        return text

    def _normalize_selling_points(self, raw_value: Any) -> list[str]:
        return self._normalize_alias_values(raw_value, SELLING_POINT_ALIASES, 2)

    def _normalize_style_keywords(self, raw_value: Any) -> list[str]:
        return self._normalize_alias_values(raw_value, STYLE_KEYWORD_ALIASES, 3)

    def _normalize_alias_values(
        self,
        raw_value: Any,
        alias_pairs: list[tuple[str, list[str]]],
        limit: int,
    ) -> list[str]:
        if raw_value is None:
            return []
        if isinstance(raw_value, str):
            candidates = [raw_value]
        elif isinstance(raw_value, list):
            candidates = [str(item) for item in raw_value]
        else:
            candidates = [str(raw_value)]

        result: list[str] = []
        for candidate in candidates:
            text = candidate.strip()
            if not text:
                continue
            lowered = text.lower()
            mapped_label = next(
                (
                    label
                    for label, aliases in alias_pairs
                    if any(alias in text or alias in lowered for alias in aliases)
                ),
                None,
            )
            if mapped_label:
                result.append(mapped_label)
                continue
            if self._contains_cjk(text):
                result.append(text)
        return list(dict.fromkeys(result))[:limit]

    def _contains_cjk(self, text: str) -> bool:
        return any("\u4e00" <= char <= "\u9fff" for char in text)

    def _extract_visual_hints(self, message: str) -> list[str]:
        return self._normalize_alias_values(message, VISUAL_HINT_ALIASES, 3)
