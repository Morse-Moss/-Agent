from __future__ import annotations

import base64
import io
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from PIL import Image

from .system_settings import GatewayRuntimeConfig

logger = logging.getLogger(__name__)

DEFAULT_SELLING_POINTS = ["耐腐蚀", "高强度", "规格齐全", "支持定制"]
DEFAULT_STYLE_KEYWORDS = ["工业简洁", "金属质感", "高级感"]

SELLING_POINT_ALIASES = [
    ("耐腐蚀", ["耐腐蚀", "防腐", "anti-corrosion", "corrosion resistant"]),
    ("高强度", ["高强度", "强度高", "high strength"]),
    ("规格齐全", ["规格齐全", "规格丰富", "full specs"]),
    ("支持定制", ["支持定制", "可定制", "customizable", "custom"]),
]

STYLE_KEYWORD_ALIASES = [
    ("工业简洁", ["工业", "工业感", "industrial", "简洁", "clean"]),
    ("金属质感", ["金属", "金属质感", "metal", "texture", "质感"]),
    ("高级感", ["高级", "高级感", "premium"]),
    ("深色", ["深色", "暗色", "dark"]),
    ("明亮", ["明亮", "bright"]),
    ("科技感", ["科技", "科技感", "tech"]),
    ("极简", ["极简", "minimal"]),
]

PRODUCT_NAME_ALIASES = [
    ("广告材料铝单板", ["铝单板", "aluminum panel", "aluminium panel"]),
    ("广告材料铝型材", ["铝型材", "aluminum profile", "aluminium profile"]),
    ("广告材料铝方通", ["铝方通"]),
    ("广告材料铝板", ["铝板", "aluminum sheet", "aluminium sheet"]),
    ("广告材料铝材", ["广告材料铝材", "广告材料", "铝材", "aluminum", "aluminium"]),
]

VISUAL_HINT_ALIASES = [
    ("深色背景", ["深色", "暗色", "dark"]),
    ("明亮背景", ["明亮", "bright"]),
    ("工业车间场景", ["车间", "工厂", "factory"]),
    ("材料展厅场景", ["展厅", "showroom"]),
    ("建筑装饰场景", ["建筑", "幕墙", "外立面"]),
    ("极简棚拍场景", ["棚拍", "工作室", "studio", "纯背景"]),
]

QWEN_IMAGE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
ZHUPU_CHAT_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
ZHUPU_IMAGE_URL = "https://open.bigmodel.cn/api/paas/v4/images/generations"

DIRECT_GENERATE_KEYWORDS = [
    "开始生成",
    "开始出图",
    "直接生成",
    "请直接生成",
    "现在开始生成",
    "生成吧",
    "确认生成",
    "可以生成",
    "好 生成",
    "那就生成",
    "生成主图",
    "出图",
    "做一版",
    "做一张",
    "来一版",
    "生成一版",
    "重新生成",
    "再生成",
    "重做",
    "start generate",
    "generate now",
    "please generate",
]

MODIFICATION_GENERATE_KEYWORDS = [
    "改一版",
    "调整",
    "换成",
    "改成",
    "背景换",
    "再来一版",
    "继续修改",
]

DISCUSSION_KEYWORDS = [
    "先别出图",
    "先不出图",
    "先不要生成",
    "暂不生成",
    "先聊",
    "先讨论",
    "先整理方向",
    "先确认方向",
    "先帮我梳理",
    "先总结一下",
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
        text = (description or "").strip()
        if self._has_real_llm():
            try:
                return self._summarize_brand_with_llm(text)
            except Exception:
                logger.exception("LLM brand summarization failed, falling back to local")
        return self._summarize_brand_locally(text)

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
        snapshot["page_type"] = (
            guide_fields.get("page_type")
            or snapshot.get("page_type")
            or project_defaults.get("page_type")
            or "main_image"
        )
        snapshot["platform"] = (
            guide_fields.get("platform")
            or snapshot.get("platform")
            or project_defaults.get("platform")
            or "taobao"
        )

        if self._has_real_llm():
            try:
                return self._plan_generation_with_llm(
                    message=message,
                    guide_fields=guide_fields,
                    brand_context=brand_context,
                    previous_snapshot=snapshot,
                    project_defaults=project_defaults,
                    user_turns=user_turns,
                )
            except Exception:
                logger.exception("LLM plan_generation failed, falling back to local")

        return self._plan_generation_locally(
            message=message,
            guide_fields=guide_fields,
            brand_context=brand_context,
            previous_snapshot=snapshot,
            project_defaults=project_defaults,
            user_turns=user_turns,
        )

    def message_requests_generation(self, message: str, *, has_previous_version: bool = False) -> bool:
        text = self._normalize_free_text(message)
        if not text or self._prefers_discussion(text):
            return False
        if any(keyword in text for keyword in DIRECT_GENERATE_KEYWORDS):
            return True
        if has_previous_version and any(keyword in text for keyword in MODIFICATION_GENERATE_KEYWORDS):
            return True
        if "生成" in text and any(token in text for token in ["现在", "开始", "直接", "请", "帮我", "主图", "一版", "图片"]):
            return True
        if "出图" in text and any(token in text for token in ["现在", "开始", "直接", "请", "帮我", "主图", "一版"]):
            return True
        return False

    def render_background(self, snapshot: dict[str, Any], size: tuple[int, int]) -> Image.Image | None:
        try:
            return self.call_image_provider(snapshot, size)
        except Exception:
            return None

    def test_llm_provider(self) -> str:
        provider_name = (self.runtime_config.llm_provider or "local_demo").strip().lower()
        if provider_name == "local_demo":
            return "当前使用本地兜底模式，未调用外部 LLM。"

        payload = self._chat_completion(
            messages=[
                {"role": "system", "content": "你是一个连通性测试助手。请只返回一句中文：LLM 连接成功。"},
                {"role": "user", "content": "请返回测试结果。"},
            ],
            temperature=0.1,
        )
        reply = self._extract_text_from_chat_payload(payload).strip()
        if not reply:
            raise RuntimeError("LLM 没有返回可用文本。")
        return reply

    def call_image_provider(self, snapshot: dict[str, Any], size: tuple[int, int]) -> Image.Image | None:
        provider_name = (self.runtime_config.image_provider or "local_demo").strip().lower()
        if provider_name == "local_demo":
            return None
        if provider_name == "qwen_image":
            return self._render_qwen_image_background(snapshot, size)
        if provider_name == "zhipu_image":
            return self._render_zhipu_image_background(snapshot, size)
        if provider_name == "generic_http":
            return self._render_generic_http_background(snapshot, size)
        if provider_name == "fal_flux":
            return self._render_fal_flux_background(snapshot, size)
        if provider_name == "gpt_image":
            return self._render_gpt_image_background(snapshot, size)
        raise RuntimeError(f"暂不支持的图片 Provider：{provider_name}")

    def _summarize_brand_with_llm(self, description: str) -> dict[str, Any]:
        payload = self._chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "请根据品牌描述返回 JSON，字段固定为 style_summary 和 recommended_keywords。"
                        "只返回 JSON，不要添加解释。"
                    ),
                },
                {"role": "user", "content": f"品牌描述：{description or '暂无描述'}"},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        data = self._parse_json_text(self._extract_text_from_chat_payload(payload))
        style_summary = str(data.get("style_summary", "")).strip()
        keywords = self._normalize_style_keywords(data.get("recommended_keywords"))
        if not style_summary:
            raise RuntimeError("LLM 没有返回 style_summary。")
        return {"style_summary": style_summary, "recommended_keywords": keywords[:5] or DEFAULT_STYLE_KEYWORDS}

    def _summarize_brand_locally(self, description: str) -> dict[str, Any]:
        keywords: list[str] = []
        for keyword in ["工业简洁", "金属质感", "支持定制", "耐腐蚀", "稳定供货", "高强度"]:
            if keyword in description or len(keywords) < 3:
                keywords.append(keyword)

        return {
            "style_summary": (
                "品牌整体适合简洁、工业化、偏金属质感的表达方式，"
                f"重点突出材质、稳定供货与定制能力。参考描述：{description or '暂无描述'}"
            ),
            "recommended_keywords": self._unique_keep_order(keywords)[:5] or DEFAULT_STYLE_KEYWORDS,
        }

    def _plan_generation_with_llm(
        self,
        *,
        message: str,
        guide_fields: dict[str, Any],
        brand_context: DemoBrandContext,
        previous_snapshot: dict[str, Any],
        project_defaults: dict[str, Any],
        user_turns: int,
    ) -> dict[str, Any]:
        payload = self._chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是电商美工 Agent 的对话规划器。请根据用户聊天、品牌信息和已有版本快照返回 JSON。"
                        "字段固定为 should_clarify, should_generate, questions, assistant_reply, "
                        "product_name, selling_points, style_keywords, title_text, prompt_summary。"
                        "questions 最多 2 条，selling_points 最多 2 条，style_keywords 最多 3 条。"
                        "如果信息不足，should_clarify=true 且 should_generate=false。"
                        "如果只是继续讨论方向，should_clarify=false 且 should_generate=false，并返回 assistant_reply。"
                        "只有在用户明确要求开始生成，或者信息已经完整且适合直接出图时，should_generate 才能为 true。"
                        "默认优先继续对话，不要因为用户发了一条普通消息就直接生成。"
                        "assistant_reply 必须是自然中文，适合直接显示在聊天区。"
                        "prompt_summary 必须是中文，用于图片模型理解创作方向，并尽量避免画面中自动出现文字。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "user_message": message,
                            "guide_fields": guide_fields,
                            "brand_context": brand_context.__dict__,
                            "previous_snapshot": previous_snapshot,
                            "project_defaults": project_defaults,
                            "user_turns": user_turns,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        data = self._parse_json_text(self._extract_text_from_chat_payload(payload))
        return self._build_plan_result(
            data=data,
            message=message,
            guide_fields=guide_fields,
            brand_context=brand_context,
            previous_snapshot=previous_snapshot,
            project_defaults=project_defaults,
        )

    def _plan_generation_locally(
        self,
        *,
        message: str,
        guide_fields: dict[str, Any],
        brand_context: DemoBrandContext,
        previous_snapshot: dict[str, Any],
        project_defaults: dict[str, Any],
        user_turns: int,
    ) -> dict[str, Any]:
        candidate_product = (
            guide_fields.get("product_name")
            or self._extract_product_name(message)
            or previous_snapshot.get("product_name")
            or project_defaults.get("product_name")
            or "广告材料铝材"
        )

        questions: list[str] = []
        if not message.strip() and user_turns <= 1:
            questions.append("这次想做什么类型的页面？例如淘宝主图、详情页模块图或品牌 Banner。")
        if candidate_product == "广告材料铝材" and user_turns <= 1 and len(message.strip()) < 8:
            questions.append("能否告诉我更具体的产品名称？比如铝单板、铝型材、铝方通或铝板。")

        selling_points = self._extract_selling_points(message)
        style_keywords = self._extract_style_keywords(message)
        visual_hints = self._extract_visual_hints(message)
        merged_style_keywords = self._unique_keep_order(style_keywords + visual_hints)
        resolved_selling_points = self._normalize_selling_points(
            selling_points
            or guide_fields.get("selling_points")
            or previous_snapshot.get("selling_points")
            or DEFAULT_SELLING_POINTS[:2]
        )[:2]
        resolved_style_keywords = self._normalize_style_keywords(
            merged_style_keywords
            or guide_fields.get("style_keywords")
            or previous_snapshot.get("style_keywords")
            or DEFAULT_STYLE_KEYWORDS
        )[:3]

        should_generate = self._should_generate_now(
            message=message,
            has_questions=bool(questions),
            has_previous_version=bool(previous_snapshot.get("title_text") or previous_snapshot.get("prompt_summary")),
        )

        data = {
            "should_clarify": bool(questions),
            "should_generate": should_generate,
            "questions": questions,
            "assistant_reply": self._build_chat_reply(
                message=message,
                should_generate=should_generate,
                should_clarify=bool(questions),
                product_name=candidate_product,
                selling_points=resolved_selling_points,
                style_keywords=resolved_style_keywords,
            ),
            "product_name": candidate_product,
            "selling_points": resolved_selling_points,
            "style_keywords": resolved_style_keywords,
            "title_text": self._make_title(candidate_product, resolved_selling_points),
            "prompt_summary": self._build_prompt_summary(
                product_name=candidate_product,
                selling_points=resolved_selling_points,
                style_keywords=resolved_style_keywords,
                brand_context=brand_context,
                user_message=message,
            ),
        }
        return self._build_plan_result(
            data=data,
            message=message,
            guide_fields=guide_fields,
            brand_context=brand_context,
            previous_snapshot=previous_snapshot,
            project_defaults=project_defaults,
        )

    def _build_plan_result(
        self,
        *,
        data: dict[str, Any],
        message: str,
        guide_fields: dict[str, Any],
        brand_context: DemoBrandContext,
        previous_snapshot: dict[str, Any],
        project_defaults: dict[str, Any],
    ) -> dict[str, Any]:
        product_name = (
            self._extract_product_name(str(data.get("product_name", "")))
            or guide_fields.get("product_name")
            or previous_snapshot.get("product_name")
            or project_defaults.get("product_name")
            or "广告材料铝材"
        )
        selling_points = self._normalize_selling_points(
            data.get("selling_points")
            or guide_fields.get("selling_points")
            or previous_snapshot.get("selling_points")
            or DEFAULT_SELLING_POINTS[:2]
        )[:2]
        style_keywords = self._normalize_style_keywords(
            data.get("style_keywords")
            or guide_fields.get("style_keywords")
            or previous_snapshot.get("style_keywords")
            or brand_context.recommended_keywords
            or DEFAULT_STYLE_KEYWORDS
        )[:3]
        questions = self._normalize_questions(data.get("questions"))[:2]
        should_clarify = bool(data.get("should_clarify")) and bool(questions)
        should_generate = bool(data.get("should_generate")) and not should_clarify
        if self._prefers_discussion(message):
            should_clarify = False
            should_generate = False
            questions = []
        title_text = str(data.get("title_text", "")).strip() or self._make_title(product_name, selling_points)
        title_text = self._sanitize_title_text(title_text, product_name=product_name, selling_points=selling_points)
        prompt_summary = str(data.get("prompt_summary", "")).strip() or self._build_prompt_summary(
            product_name=product_name,
            selling_points=selling_points,
            style_keywords=style_keywords,
            brand_context=brand_context,
            user_message=message,
        )
        assistant_reply = str(data.get("assistant_reply", "")).strip() or self._build_chat_reply(
            message=message,
            should_generate=should_generate,
            should_clarify=should_clarify,
            product_name=product_name,
            selling_points=selling_points,
            style_keywords=style_keywords,
        )

        resolved_brief = {
            "product_name": product_name,
            "selling_points": selling_points,
            "style_keywords": style_keywords,
            "title_text": title_text,
            "prompt_summary": prompt_summary,
            "brand_name": brand_context.name,
            "brand_style_summary": brand_context.style_summary,
            "assistant_reply": assistant_reply,
            "should_generate": should_generate,
        }

        snapshot = dict(previous_snapshot)
        snapshot.update(
            {
                "page_type": guide_fields.get("page_type")
                or previous_snapshot.get("page_type")
                or project_defaults.get("page_type")
                or "main_image",
                "platform": guide_fields.get("platform")
                or previous_snapshot.get("platform")
                or project_defaults.get("platform")
                or "taobao",
                "product_name": product_name,
                "selling_points": selling_points,
                "style_keywords": style_keywords,
                "title_text": title_text,
                "prompt_summary": prompt_summary,
                "resolved_brief": resolved_brief,
                "clarify_questions": questions,
                "assistant_reply": assistant_reply,
                "should_generate": should_generate,
                "latest_user_message": message,
                "brand_name": brand_context.name,
                "brand_style_summary": brand_context.style_summary,
                "brand_keywords": brand_context.recommended_keywords,
                "llm_provider_used": (self.runtime_config.llm_provider or "local_demo").strip().lower(),
                "llm_model_used": self.runtime_config.llm_model or "",
                "image_provider_used": (self.runtime_config.image_provider or "local_demo").strip().lower(),
                "image_model_used": self.runtime_config.image_model or "",
            }
        )

        return {
            "should_clarify": should_clarify,
            "should_generate": should_generate,
            "questions": questions,
            "assistant_reply": assistant_reply,
            "snapshot": snapshot,
        }

    def _has_real_llm(self) -> bool:
        provider_name = (self.runtime_config.llm_provider or "local_demo").strip().lower()
        if provider_name == "local_demo":
            return False
        if provider_name == "zhipu_glm":
            return bool(self.runtime_config.llm_api_key)
        if provider_name == "codex_ai":
            return bool(self.runtime_config.llm_api_key and self.runtime_config.llm_api_url and self.runtime_config.llm_model)
        return False

    def _chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float = 0.3,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        provider_name = (self.runtime_config.llm_provider or "local_demo").strip().lower()
        if provider_name == "zhipu_glm":
            payload: dict[str, Any] = {
                "model": self.runtime_config.llm_model or "glm-4.7",
                "messages": messages,
                "temperature": temperature,
            }
            if response_format:
                payload["response_format"] = response_format
            return self._request_json(
                url=self.runtime_config.llm_api_url or ZHUPU_CHAT_URL,
                payload=payload,
                headers=self._build_auth_headers(self.runtime_config.llm_api_key, self.runtime_config.llm_api_key_header),
                timeout_seconds=self.runtime_config.llm_timeout_seconds,
            )

        if provider_name == "codex_ai":
            return self._chat_completion_codex(
                messages=messages,
                temperature=temperature,
                response_format=response_format,
            )

        raise RuntimeError(f"暂不支持的 LLM Provider：{provider_name}")

    def _chat_completion_codex(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float,
        response_format: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.runtime_config.llm_model or "gpt-5-codex",
            "input": self._to_responses_input(messages),
            "reasoning": {"effort": "high"},
            "temperature": temperature,
        }
        if response_format and response_format.get("type") == "json_object":
            payload["text"] = {"format": {"type": "json_object"}}

        headers = self._build_auth_headers(self.runtime_config.llm_api_key, self.runtime_config.llm_api_key_header)
        last_error: Exception | None = None
        for url in self._resolve_codex_responses_urls():
            try:
                return self._request_json(
                    url=url,
                    payload=payload,
                    headers=headers,
                    timeout_seconds=self.runtime_config.llm_timeout_seconds,
                )
            except RuntimeError as exc:
                if "HTTP 404" in str(exc):
                    last_error = exc
                    continue
                raise
        if last_error:
            raise last_error
        raise RuntimeError("codex_ai 未找到可用的 Responses API 路径。")

    def _resolve_codex_responses_urls(self) -> list[str]:
        raw_url = (self.runtime_config.llm_api_url or "").strip().rstrip("/")
        if not raw_url:
            raise RuntimeError("codex_ai 未配置 LLM API URL。")
        if raw_url.lower().endswith("/responses") or raw_url.lower().endswith("/v1/responses"):
            return [raw_url]
        return [raw_url + "/responses", raw_url + "/v1/responses"]

    def _render_qwen_image_background(self, snapshot: dict[str, Any], size: tuple[int, int]) -> Image.Image | None:
        if not self.runtime_config.image_api_key:
            raise RuntimeError("qwen_image 未配置图片 API Key。")

        content: list[dict[str, Any]] = []
        source_image_path = str(snapshot.get("source_image_path", "")).strip()
        if source_image_path:
            content.append({"text": "请把这张白底产品图作为参考，只理解产品主体和材质，不要自动添加文字。"})
            content.append({"image": self._resolve_local_image_url(source_image_path)})
        content.append({"text": self._build_image_prompt(snapshot)})

        payload = {
            "model": self.runtime_config.image_model or "qwen-image-2.0",
            "input": {"messages": [{"role": "user", "content": content}]},
            "parameters": {"negative_prompt": "不要文字，不要英文，不要字母，不要数字，不要水印，不要 logo"},
        }
        data = self._request_json(
            url=self._resolve_qwen_image_url(),
            payload=payload,
            headers=self._build_auth_headers(self.runtime_config.image_api_key, self.runtime_config.image_api_key_header),
            timeout_seconds=self.runtime_config.image_timeout_seconds,
        )
        return self._resize_if_needed(self._decode_image_payload(data), size)

    def _render_zhipu_image_background(self, snapshot: dict[str, Any], size: tuple[int, int]) -> Image.Image | None:
        if not self.runtime_config.image_api_key:
            raise RuntimeError("zhipu_image 未配置图片 API Key。")
        payload = {
            "model": self.runtime_config.image_model or "cogview-4-250304",
            "prompt": self._build_image_prompt(snapshot),
            "size": f"{size[0]}x{size[1]}",
            "watermark_enabled": False,
        }
        data = self._request_json(
            url=self._resolve_zhipu_image_url(),
            payload=payload,
            headers=self._build_auth_headers(self.runtime_config.image_api_key, self.runtime_config.image_api_key_header),
            timeout_seconds=self.runtime_config.image_timeout_seconds,
        )
        return self._resize_if_needed(self._decode_image_payload(data), size)

    def _render_generic_http_background(self, snapshot: dict[str, Any], size: tuple[int, int]) -> Image.Image | None:
        if not self.runtime_config.image_api_url:
            raise RuntimeError("generic_http 未配置图片 API URL。")
        payload = {
            "model": self.runtime_config.image_model or "",
            "prompt": self._build_image_prompt(snapshot),
            "width": size[0],
            "height": size[1],
        }
        data = self._request_json(
            url=self.runtime_config.image_api_url,
            payload=payload,
            headers=self._build_auth_headers(self.runtime_config.image_api_key, self.runtime_config.image_api_key_header),
            timeout_seconds=self.runtime_config.image_timeout_seconds,
        )
        return self._resize_if_needed(self._decode_image_payload(data), size)

    def _render_fal_flux_background(self, snapshot: dict[str, Any], size: tuple[int, int]) -> Image.Image | None:
        """Call fal.ai Flux API for image generation (queue-based async)."""
        if not self.runtime_config.image_api_key:
            raise RuntimeError("fal_flux 未配置图片 API Key。请在 fal.ai 获取 Key。")

        import time

        model_variant = (self.runtime_config.image_model or "schnell").strip().lower()
        model_map = {
            "schnell": "fal-ai/flux/schnell",
            "pro": "fal-ai/flux-pro",
            "dev": "fal-ai/flux/dev",
            "flux-2-pro": "fal-ai/flux-2-pro",
        }
        model_id = model_map.get(model_variant, model_variant)

        # Determine aspect ratio from size
        w, h = size
        if w > h:
            image_size = "landscape_16_9"
        elif h > w:
            image_size = "portrait_9_16"
        else:
            image_size = "square"

        submit_url = f"https://queue.fal.run/{model_id}"
        payload: dict[str, Any] = {
            "prompt": self._build_image_prompt(snapshot),
            "image_size": image_size,
            "num_images": 1,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Key {self.runtime_config.image_api_key}",
        }

        # Submit to queue
        submit_data = self._request_json(
            url=submit_url,
            payload=payload,
            headers=headers,
            timeout_seconds=self.runtime_config.image_timeout_seconds,
        )

        # If response has images directly (schnell is often sync)
        images = submit_data.get("images") or submit_data.get("data")
        if isinstance(images, list) and images:
            url = images[0].get("url") if isinstance(images[0], dict) else None
            if url:
                return self._resize_if_needed(self._download_image_from_url(url, self.runtime_config.image_timeout_seconds), size)

        # Queue-based: poll status_url
        status_url = submit_data.get("status_url") or submit_data.get("request_url")
        if not status_url:
            raise RuntimeError("fal.ai 未返回 status_url，无法轮询结果")

        poll_headers = {"Authorization": f"Key {self.runtime_config.image_api_key}"}
        for _ in range(60):  # max 60 polls, ~2 minutes
            time.sleep(2)
            req = request.Request(url=status_url, headers=poll_headers, method="GET")
            with request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            status = result.get("status", "")
            if status == "COMPLETED" or result.get("images"):
                images = result.get("images") or result.get("data", [])
                if isinstance(images, list) and images:
                    url = images[0].get("url") if isinstance(images[0], dict) else None
                    if url:
                        return self._resize_if_needed(
                            self._download_image_from_url(url, self.runtime_config.image_timeout_seconds), size
                        )
                raise RuntimeError("fal.ai 返回 COMPLETED 但无图片 URL")
            if status in ("FAILED", "CANCELLED"):
                raise RuntimeError(f"fal.ai 生成失败: {result.get('error', status)}")

        raise RuntimeError("fal.ai 生成超时（2分钟）")

    def _render_gpt_image_background(self, snapshot: dict[str, Any], size: tuple[int, int]) -> Image.Image | None:
        """Call OpenAI GPT-Image-1 API (or compatible proxy) for image generation."""
        if not self.runtime_config.image_api_key:
            raise RuntimeError("gpt_image 未配置图片 API Key。")

        base_url = (self.runtime_config.image_api_url or "").strip().rstrip("/")
        if not base_url:
            base_url = "https://api.openai.com/v1"
        url = base_url.rstrip("/")
        if not url.endswith("/images/generations"):
            url = url + "/images/generations"

        w, h = size
        size_str = "1024x1024"
        if w > h:
            size_str = "1536x1024"
        elif h > w:
            size_str = "1024x1536"

        payload = {
            "model": self.runtime_config.image_model or "gpt-image-1",
            "prompt": self._build_image_prompt(snapshot),
            "size": size_str,
            "quality": "medium",
            "n": 1,
        }
        headers = self._build_auth_headers(self.runtime_config.image_api_key, self.runtime_config.image_api_key_header)
        data = self._request_json(url=url, payload=payload, headers=headers, timeout_seconds=self.runtime_config.image_timeout_seconds)
        return self._resize_if_needed(self._decode_image_payload(data), size)
        product_name = str(snapshot.get("product_name") or "广告材料铝材")
        selling_points = "、".join(snapshot.get("selling_points", [])[:2]) or "耐腐蚀、高强度"
        style_keywords = "、".join(snapshot.get("style_keywords", [])[:3]) or "工业简洁、金属质感、高级感"
        prompt_summary = str(snapshot.get("prompt_summary") or "").strip()
        user_message = str(snapshot.get("latest_user_message") or "").strip()

        base_prompt = (
            f"{product_name} 电商主图底图，生成无字背景，不要水印，不要 logo。"
            f"整体风格偏 {style_keywords}，突出 {selling_points}。"
            "画面适合淘宝主图使用，主体展示区域明确，背景专业、简洁、偏建筑装饰材料行业。"
        )
        if prompt_summary:
            return f"{prompt_summary}。{base_prompt}"
        if user_message:
            return f"参考用户本轮描述：{user_message}。{base_prompt}"
        return base_prompt

    def _build_auth_headers(self, api_key: str | None, header_name: str | None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if not api_key:
            return headers
        normalized_header = (header_name or "Authorization").strip() or "Authorization"
        header_value = api_key
        if normalized_header.lower() == "authorization" and not api_key.lower().startswith("bearer "):
            header_value = f"Bearer {api_key}"
        headers[normalized_header] = header_value
        return headers

    def _request_json(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(url=url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Provider request failed with HTTP {exc.code}: {raw}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Provider request failed: {exc.reason}") from exc

    def _resolve_qwen_image_url(self) -> str:
        raw_url = (self.runtime_config.image_api_url or "").strip()
        if not raw_url:
            return QWEN_IMAGE_URL
        if "services/aigc/multimodal-generation/generation" in raw_url:
            return raw_url
        return raw_url.rstrip("/") + "/services/aigc/multimodal-generation/generation"

    def _resolve_zhipu_image_url(self) -> str:
        raw_url = (self.runtime_config.image_api_url or "").strip()
        if not raw_url:
            return ZHUPU_IMAGE_URL
        if raw_url.endswith("/images/generations"):
            return raw_url
        if raw_url.endswith("/api/paas/v4"):
            return raw_url + "/images/generations"
        return raw_url

    def _resolve_local_image_url(self, source_image_path: str) -> str:
        return f"http://127.0.0.1:8000/storage/{source_image_path.lstrip('/')}"

    def _resize_if_needed(self, image: Image.Image, size: tuple[int, int]) -> Image.Image:
        if image.size == size:
            return image
        resized = image.resize(size, Image.LANCZOS)
        image.close()
        return resized

    def _download_image_from_url(self, url: str, timeout_seconds: int) -> Image.Image:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise RuntimeError(f"Unsupported URL scheme: {parsed.scheme}")
        if parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"):
            # Allow local URLs only for source image references from our own server
            if "/storage/" not in parsed.path:
                raise RuntimeError("Blocked download from local/private address")
        # Block private IP ranges (10.x, 172.16-31.x, 192.168.x)
        import ipaddress
        try:
            ip = ipaddress.ip_address(parsed.hostname or "")
            if ip.is_private and "/storage/" not in parsed.path:
                raise RuntimeError("Blocked download from private IP address")
        except ValueError:
            pass  # hostname is a domain name, not an IP

        max_size = 50 * 1024 * 1024  # 50MB limit
        req = request.Request(url=url, headers={"User-Agent": "ecom-art-agent/0.4"})
        with request.urlopen(req, timeout=timeout_seconds) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_size:
                raise RuntimeError(f"Image too large: {content_length} bytes")
            raw = response.read(max_size + 1)
            if len(raw) > max_size:
                raise RuntimeError("Image exceeds 50MB size limit")
        return Image.open(io.BytesIO(raw)).convert("RGBA")

    def _decode_image_payload(self, payload: dict[str, Any]) -> Image.Image:
        data_items = payload.get("data")
        if isinstance(data_items, list) and data_items:
            item = data_items[0]
            if isinstance(item, dict):
                if item.get("b64_json"):
                    return self._decode_base64_image(item["b64_json"])
                if item.get("url"):
                    return self._download_image_from_url(item["url"], self.runtime_config.image_timeout_seconds)

        output = payload.get("output")
        if isinstance(output, dict):
            choices = output.get("choices")
            if isinstance(choices, list) and choices:
                message = choices[0].get("message", {})
                content = message.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("image"):
                            return self._download_image_from_url(item["image"], self.runtime_config.image_timeout_seconds)
                        if isinstance(item, dict) and item.get("image_url"):
                            return self._download_image_from_url(item["image_url"], self.runtime_config.image_timeout_seconds)
                        if isinstance(item, dict) and item.get("b64_json"):
                            return self._decode_base64_image(item["b64_json"])

        for key in ("image", "image_url", "url"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return self._download_image_from_url(value, self.runtime_config.image_timeout_seconds)

        if isinstance(payload.get("b64_json"), str):
            return self._decode_base64_image(payload["b64_json"])

        raise RuntimeError("Image provider response did not contain a supported image field")

    def _decode_base64_image(self, raw_value: str) -> Image.Image:
        return Image.open(io.BytesIO(base64.b64decode(raw_value))).convert("RGBA")

    def _extract_text_from_chat_payload(self, payload: dict[str, Any]) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        output = payload.get("output")
        if isinstance(output, list):
            parts: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("text"):
                            parts.append(str(part["text"]))
                elif isinstance(content, str) and content.strip():
                    parts.append(content)
            if parts:
                return "\n".join(parts)

        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if isinstance(item, dict) and item.get("text"):
                        parts.append(str(item["text"]))
                    elif isinstance(item, str):
                        parts.append(item)
                return "\n".join(part for part in parts if part)

        if isinstance(output, dict):
            choices = output.get("choices")
            if isinstance(choices, list) and choices:
                message = choices[0].get("message", {})
                content = message.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts = [str(item.get("text")) for item in content if isinstance(item, dict) and item.get("text")]
                    return "\n".join(parts)

        content = payload.get("content")
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("text"):
                    parts.append(str(item["text"]))
            if parts:
                return "\n".join(parts)
        if isinstance(content, str):
            return content
        return ""

    def _to_responses_input(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for item in messages:
            role = item.get("role") or "user"
            content = item.get("content", "")
            if isinstance(content, list):
                text_parts: list[str] = []
                for part in content:
                    if isinstance(part, dict) and part.get("text"):
                        text_parts.append(str(part["text"]))
                    elif isinstance(part, str):
                        text_parts.append(part)
                content = "\n".join(text_parts)
            result.append({"role": role, "content": [{"type": "input_text", "text": str(content)}]})
        return result

    def _parse_json_text(self, raw_text: str) -> dict[str, Any]:
        text = raw_text.strip()
        if not text:
            raise RuntimeError("LLM returned empty content")
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()
        return json.loads(text)

    def _extract_product_name(self, message: str) -> str:
        text = self._normalize_free_text(message)
        for canonical, aliases in PRODUCT_NAME_ALIASES:
            if any(alias.lower() in text for alias in aliases):
                return canonical
        return ""

    def _extract_selling_points(self, message: str) -> list[str]:
        text = self._normalize_free_text(message)
        result: list[str] = []
        for canonical, aliases in SELLING_POINT_ALIASES:
            if any(alias.lower() in text for alias in aliases):
                result.append(canonical)
        return self._unique_keep_order(result)[:2]

    def _extract_style_keywords(self, message: str) -> list[str]:
        text = self._normalize_free_text(message)
        result: list[str] = []
        for canonical, aliases in STYLE_KEYWORD_ALIASES:
            if any(alias.lower() in text for alias in aliases):
                result.append(canonical)
        return self._unique_keep_order(result)[:3]

    def _extract_visual_hints(self, message: str) -> list[str]:
        text = self._normalize_free_text(message)
        result: list[str] = []
        for canonical, aliases in VISUAL_HINT_ALIASES:
            if any(alias.lower() in text for alias in aliases):
                result.append(canonical)
        return self._unique_keep_order(result)

    def _normalize_questions(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return self._unique_keep_order([str(item).strip() for item in value if str(item).strip()])

    def _normalize_selling_points(self, value: Any) -> list[str]:
        values = [value] if isinstance(value, str) else (value if isinstance(value, list) else [])
        result: list[str] = []
        for item in values:
            text = str(item).strip()
            if not text:
                continue
            lowered = text.lower()
            matched = next(
                (
                    canonical
                    for canonical, aliases in SELLING_POINT_ALIASES
                    if text == canonical or any(alias.lower() in lowered for alias in aliases)
                ),
                None,
            )
            result.append(matched or text)
        return self._unique_keep_order(result)[:2] or DEFAULT_SELLING_POINTS[:2]

    def _normalize_style_keywords(self, value: Any) -> list[str]:
        values = [value] if isinstance(value, str) else (value if isinstance(value, list) else [])
        result: list[str] = []
        for item in values:
            text = str(item).strip()
            if not text:
                continue
            lowered = text.lower()
            matched = next(
                (
                    canonical
                    for canonical, aliases in STYLE_KEYWORD_ALIASES
                    if text == canonical or any(alias.lower() in lowered for alias in aliases)
                ),
                None,
            )
            result.append(matched or text)
        return self._unique_keep_order(result)[:3] or DEFAULT_STYLE_KEYWORDS

    def _make_title(self, product_name: str, selling_points: list[str]) -> str:
        main_points = selling_points[:2] or ["耐腐蚀", "支持定制"]
        return f"{product_name} | {' / '.join(main_points)}"

    def _sanitize_title_text(self, raw_title: str, *, product_name: str, selling_points: list[str]) -> str:
        title = (raw_title or "").strip()
        if not title:
            return self._make_title(product_name, selling_points)
        if self._contains_latin_letters(title):
            return self._make_title(product_name, selling_points)
        if len(title) > 28:
            return self._make_title(product_name, selling_points)
        return re.sub(r"\s+", " ", title)

    def _build_prompt_summary(
        self,
        *,
        product_name: str,
        selling_points: list[str],
        style_keywords: list[str],
        brand_context: DemoBrandContext,
        user_message: str,
    ) -> str:
        points = "、".join(selling_points[:2] or DEFAULT_SELLING_POINTS[:2])
        styles = "、".join(style_keywords[:3] or DEFAULT_STYLE_KEYWORDS)
        base = (
            f"{product_name} 电商主图创作，画面无字，整体风格偏 {styles}，"
            f"突出 {points}，用于淘宝主图，强调专业与转化感。"
        )
        if user_message.strip():
            return f"{base} 用户本轮补充：{user_message.strip()}"
        if brand_context.style_summary:
            return f"{base} 品牌风格参考：{brand_context.style_summary}"
        return base

    def _should_generate_now(self, *, message: str, has_questions: bool, has_previous_version: bool) -> bool:
        if has_questions:
            return False
        text = self._normalize_free_text(message)
        if not text:
            return False
        if self._prefers_discussion(text):
            return False
        return self.message_requests_generation(text, has_previous_version=has_previous_version)

    def _prefers_discussion(self, message: str) -> bool:
        text = self._normalize_free_text(message)
        return any(keyword in text for keyword in DISCUSSION_KEYWORDS)

    def _build_chat_reply(
        self,
        *,
        message: str,
        should_generate: bool,
        should_clarify: bool,
        product_name: str,
        selling_points: list[str],
        style_keywords: list[str],
    ) -> str:
        if should_clarify or should_generate:
            return ""
        points = "、".join(selling_points[:2]) or "默认卖点"
        styles = "、".join(style_keywords[:3]) or "简洁清晰"
        if (message or "").strip():
            return (
                f"我先不直接出图，先帮你把方向收一下：产品是 {product_name}，"
                f"卖点偏 {points}，整体风格偏 {styles}。"
                "如果方向没问题，你可以直接回复“开始生成”；如果还想细化，也可以继续补充画面氛围、构图和品牌感。"
            )
        return "我已经进入对话创作模式。你可以先告诉我产品、卖点和风格，我会判断是继续追问还是开始生成。"

    def _unique_keep_order(self, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = value.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def _normalize_free_text(self, value: str) -> str:
        text = unicodedata.normalize("NFKC", value or "")
        translation = str.maketrans(
            {
                "，": " ",
                "。": " ",
                "！": " ",
                "？": " ",
                "：": " ",
                "；": " ",
                "（": " ",
                "）": " ",
                "、": " ",
                "/": " ",
                "\\": " ",
                "|": " ",
                "\n": " ",
                "\r": " ",
                "\t": " ",
            }
        )
        text = text.translate(translation).lower()
        return re.sub(r"\s+", " ", text).strip()

    def _contains_latin_letters(self, value: str) -> bool:
        return bool(re.search(r"[a-zA-Z]{3,}", value or ""))

    # ------------------------------------------------------------------
    # v0.5: Multi-platform copy generation
    # ------------------------------------------------------------------

    def generate_multi_platform_copy(
        self,
        *,
        product_name: str,
        scene_description: str = "",
        selling_points: list[str] | None = None,
        platforms: list[str] | None = None,
    ) -> dict[str, str]:
        """Generate marketing copy for multiple social media platforms.

        Returns dict mapping platform name to copy text.
        """
        target_platforms = platforms or ["Instagram", "TikTok", "Facebook", "X", "Pinterest"]
        points_text = "、".join(selling_points) if selling_points else "高品质"

        # Try LLM first
        if self.runtime_config and self.runtime_config.llm_provider not in ("local_demo", ""):
            try:
                return self._generate_copy_with_llm(
                    product_name=product_name,
                    scene_description=scene_description,
                    points_text=points_text,
                    platforms=target_platforms,
                )
            except Exception:
                logger.exception("LLM copy generation failed, using template fallback")

        # Template fallback
        result: dict[str, str] = {}
        for platform in target_platforms:
            result[platform] = self._template_copy(platform, product_name, scene_description, points_text)
        return result

    def _generate_copy_with_llm(
        self,
        *,
        product_name: str,
        scene_description: str,
        points_text: str,
        platforms: list[str],
    ) -> dict[str, str]:
        """Use LLM to generate platform-specific copy."""
        platform_list = "、".join(platforms)
        system_prompt = (
            "你是一位专业的跨境电商社媒文案专家。根据产品信息，为每个平台生成适合的营销文案。"
            "每个平台的文案风格要符合该平台的用户习惯。"
            "返回JSON格式：{\"平台名\": \"文案内容\"}"
        )
        user_prompt = (
            f"产品：{product_name}\n"
            f"场景：{scene_description}\n"
            f"卖点：{points_text}\n"
            f"目标平台：{platform_list}\n"
            f"请为每个平台生成一段营销文案（含hashtag），返回JSON。"
        )

        reply = self._chat_completion(system_prompt, user_prompt)
        if reply:
            import json
            try:
                return json.loads(reply)
            except json.JSONDecodeError:
                logger.warning("LLM returned non-JSON copy, using as-is")

        return {p: reply or "" for p in platforms}

    def _template_copy(self, platform: str, product_name: str, scene: str, points: str) -> str:
        """Generate template-based copy for a platform."""
        templates = {
            "Instagram": f"✨ {product_name} — {points}\n\n{scene}\n\n#homedecor #bathroom #design #interiordesign",
            "TikTok": f"🔥 {product_name} | {points} | {scene} #fyp #homedecor #bathroom",
            "Facebook": f"Discover our {product_name}! {points}. {scene}\n\nShop now 👉 Link in bio",
            "X": f"{product_name} — {points}. {scene} #design #bathroom",
            "Pinterest": f"{product_name} | {points} | {scene} | Modern Bathroom Ideas",
        }
        return templates.get(platform, f"{product_name} — {points}")
