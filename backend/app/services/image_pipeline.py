from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .model_gateway import ModelGateway
from .storage import StorageService

logger = logging.getLogger(__name__)


class ImagePipeline:
    def __init__(self, storage: StorageService, gateway: ModelGateway | None = None) -> None:
        self.storage = storage
        self.gateway = gateway

    def cutout_with_provider(self, source_image_path: str, provider: str = "rembg") -> dict[str, Any]:
        """Remove background using configured provider.

        Three-tier fallback: rembg (local) → remove.bg API → NumPy.
        """
        if provider == "rembg":
            result = self._cutout_rembg(source_image_path)
            if result:
                return result
            logger.warning("rembg failed, falling back to NumPy cutout")

        elif provider == "remove_bg":
            result = self._cutout_remove_bg(source_image_path)
            if result:
                return result
            logger.warning("remove.bg API failed, falling back to rembg")
            result = self._cutout_rembg(source_image_path)
            if result:
                return result
            logger.warning("rembg also failed, falling back to NumPy cutout")

        # Final fallback: NumPy
        return self._remove_white_background(source_image_path)

    def _cutout_rembg(self, source_image_path: str) -> dict[str, Any] | None:
        """Use rembg for local AI background removal."""
        try:
            from rembg import remove as rembg_remove
        except ImportError:
            logger.warning("rembg not installed, skipping")
            return None

        try:
            source_path = self.storage.absolute_path(source_image_path)
            with Image.open(source_path) as original:
                result_image = rembg_remove(original)
                return self.storage.save_image(result_image, bucket="processed")
        except Exception:
            logger.exception("rembg cutout failed for %s", source_image_path)
            return None

    def _cutout_remove_bg(self, source_image_path: str) -> dict[str, Any] | None:
        """Use remove.bg API for cloud background removal."""
        from ..core.config import settings

        api_key = settings.cutout_api_key
        api_url = settings.cutout_api_url or "https://api.remove.bg/v1.0/removebg"
        if not api_key:
            logger.warning("remove.bg API key not configured")
            return None

        try:
            import httpx
            source_path = self.storage.absolute_path(source_image_path)
            with open(source_path, "rb") as f:
                response = httpx.post(
                    api_url,
                    files={"image_file": f},
                    data={"size": "auto"},
                    headers={"X-Api-Key": api_key},
                    timeout=60,
                )
            response.raise_for_status()
            from io import BytesIO
            result_image = Image.open(BytesIO(response.content)).convert("RGBA")
            return self.storage.save_image(result_image, bucket="processed")
        except Exception:
            logger.exception("remove.bg API failed for %s", source_image_path)
            return None

    def generate_assets(
        self,
        *,
        snapshot: dict[str, Any],
        source_image_path: str | None,
    ) -> list[dict[str, Any]]:
        assets: list[dict[str, Any]] = []
        cutout_result: dict[str, Any] | None = None

        if source_image_path:
            source_width, source_height = self.storage.get_image_dimensions(source_image_path)
            assets.append(
                {
                    "file_path": source_image_path,
                    "asset_type": "source",
                    "width": source_width,
                    "height": source_height,
                }
            )
            # Use provider-based cutout (rembg → remove.bg → NumPy)
            from ..core.config import settings
            cutout_result = self.cutout_with_provider(source_image_path, provider=settings.cutout_provider)
            assets.append({**cutout_result, "asset_type": "cutout"})

        background_result = self._generate_background(snapshot)
        assets.append({**background_result, "asset_type": "background"})

        composite_result, final_result = self._compose_visual(
            snapshot=snapshot,
            background_path=background_result["file_path"],
            cutout_path=cutout_result["file_path"] if cutout_result else None,
        )
        assets.append({**composite_result, "asset_type": "composite"})
        assets.append({**final_result, "asset_type": "final_export"})
        return assets

    def _canvas_size(self, page_type: str) -> tuple[int, int]:
        if page_type == "banner":
            return 1920, 700
        if page_type == "detail_module":
            return 1240, 960
        return 1200, 1200

    def _generate_background(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        width, height = self._canvas_size(snapshot.get("page_type", "main_image"))
        if self.gateway:
            external_image = self.gateway.render_background(snapshot, (width, height))
            if external_image is not None:
                if external_image.size != (width, height):
                    resized_image = external_image.resize((width, height), Image.LANCZOS)
                    external_image.close()
                    external_image = resized_image
                result = self.storage.save_image(external_image, bucket="processed")
                external_image.close()
                return result

        palette = self._palette(snapshot.get("style_keywords", []))
        image = Image.new("RGBA", (width, height), palette[0])
        draw = ImageDraw.Draw(image)

        for index in range(height):
            ratio = index / max(height - 1, 1)
            color = tuple(
                int(palette[0][channel] * (1 - ratio) + palette[1][channel] * ratio)
                for channel in range(3)
            ) + (255,)
            draw.line([(0, index), (width, index)], fill=color)

        accent = palette[2] + (90,)
        draw.rounded_rectangle((60, 70, width - 60, height - 70), radius=48, outline=accent, width=3)
        draw.ellipse((width - 360, -90, width + 80, 350), fill=palette[3] + (80,))
        draw.polygon([(0, int(height * 0.72)), (int(width * 0.32), height), (0, height)], fill=palette[3] + (110,))

        result = self.storage.save_image(image, bucket="processed")
        image.close()
        return result

    def _remove_white_background(self, source_image_path: str) -> dict[str, Any]:
        source_path = self.storage.absolute_path(source_image_path)
        with Image.open(source_path).convert("RGBA") as original:
            arr = np.array(original, dtype=np.float32)
            r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
            brightness = (r + g + b) / 3.0
            spread = np.max(arr[:, :, :3], axis=2) - np.min(arr[:, :, :3], axis=2)

            # Fully transparent for near-white pixels
            mask_full = (brightness > 242) & (spread < 18)
            # Semi-transparent for bright pixels
            mask_semi = (~mask_full) & (brightness > 228)

            new_alpha = a.copy()
            new_alpha[mask_full] = 0
            semi_alpha = np.clip((255 - brightness[mask_semi]) * 6, 0, a[mask_semi])
            new_alpha[mask_semi] = semi_alpha

            arr[:, :, 3] = new_alpha
            result_image = Image.fromarray(arr.astype(np.uint8), "RGBA")
            return self.storage.save_image(result_image, bucket="processed")

    def _compose_visual(
        self,
        *,
        snapshot: dict[str, Any],
        background_path: str,
        cutout_path: str | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            background = Image.open(self.storage.absolute_path(background_path)).convert("RGBA")
        except Exception:
            logger.exception("Failed to open background image: %s", background_path)
            raise
        composite = background.copy()
        provider_name = str(snapshot.get("image_provider_used", "")).strip().lower()
        has_cutout = bool(cutout_path)
        use_provider_visual_directly = (not has_cutout) and provider_name not in {"", "local_demo"}

        if use_provider_visual_directly:
            reframed = self._reframe_provider_visual(composite)
            composite.close()
            composite = reframed

        if cutout_path:
            try:
                product = Image.open(self.storage.absolute_path(cutout_path)).convert("RGBA")
            except Exception:
                logger.exception("Failed to open cutout image: %s", cutout_path)
                raise
            product = self._fit_product(product, composite.size)
            shadow = self._build_shadow(product)
            paste_x = (composite.width - product.width) // 2
            paste_y = composite.height // 2 - product.height // 2 + 40
            composite.alpha_composite(shadow, (paste_x + 24, paste_y + 24))
            composite.alpha_composite(product, (paste_x, paste_y))
            product.close()
            shadow.close()
        elif not use_provider_visual_directly:
            self._draw_product_placeholder(composite, snapshot)

        composite_result = self.storage.save_image(composite, bucket="processed")

        final_image = composite.copy()
        if has_cutout or not use_provider_visual_directly:
            self._draw_copy(final_image, snapshot)
        final_result = self.storage.save_image(final_image, bucket="exports")

        background.close()
        composite.close()
        final_image.close()
        return composite_result, final_result

    def _reframe_provider_visual(self, image: Image.Image) -> Image.Image:
        width, height = image.size
        crop_left = int(width * 0.02)
        crop_right = width - crop_left
        crop_top = int(height * 0.30)
        crop_bottom = height
        if crop_right <= crop_left or crop_bottom <= crop_top:
            return image.copy()
        reframed = image.crop((crop_left, crop_top, crop_right, crop_bottom))
        return reframed.resize((width, height), Image.LANCZOS)

    def _fit_product(self, product: Image.Image, canvas_size: tuple[int, int]) -> Image.Image:
        max_width = int(canvas_size[0] * 0.52)
        max_height = int(canvas_size[1] * 0.52)
        scale = min(max_width / product.width, max_height / product.height, 1.0)
        new_size = (max(1, int(product.width * scale)), max(1, int(product.height * scale)))
        return product.resize(new_size, Image.LANCZOS)

    def _build_shadow(self, product: Image.Image) -> Image.Image:
        shadow = Image.new("RGBA", product.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(shadow)
        draw.rounded_rectangle((24, 24, product.width - 12, product.height - 12), radius=36, fill=(0, 0, 0, 90))
        return shadow.filter(ImageFilter.GaussianBlur(18))

    def _draw_product_placeholder(self, image: Image.Image, snapshot: dict[str, Any]) -> None:
        draw = ImageDraw.Draw(image)
        center_x = image.width // 2
        center_y = image.height // 2 + 30
        block_width = int(image.width * 0.38)
        block_height = int(image.height * 0.32)
        left = center_x - block_width // 2
        top = center_y - block_height // 2
        draw.rounded_rectangle((left, top, left + block_width, top + block_height), radius=38, fill=(228, 232, 237, 255))
        draw.rounded_rectangle(
            (left + 18, top + 18, left + block_width - 18, top + block_height - 18),
            radius=30,
            outline=(140, 148, 160, 255),
            width=4,
        )
        accent_font = self._load_font(36, bold=True)
        product_name = snapshot.get("product_name", "广告铝材")
        draw.text((left + 36, top + block_height // 2 - 20), product_name, font=accent_font, fill=(40, 54, 70, 255))

    def _draw_copy(self, image: Image.Image, snapshot: dict[str, Any]) -> None:
        draw = ImageDraw.Draw(image)
        brand_font = self._load_font(34, bold=True)
        title_font = self._load_font(54, bold=True)
        point_font = self._load_font(28, bold=False)

        brand_name = snapshot.get("brand_name", "品牌精选")
        title_text = self._trim_text(snapshot.get("title_text", ""), max_chars=18)
        selling_points = snapshot.get("selling_points", [])[:2]

        draw.rounded_rectangle((60, 52, 280, 104), radius=24, fill=(255, 255, 255, 110))
        draw.text((92, 64), brand_name, font=brand_font, fill=(30, 44, 58, 255))
        draw.text((72, 130), title_text, font=title_font, fill=(255, 255, 255, 255))

        base_x = 76
        base_y = 235
        for index, point in enumerate(selling_points):
            pill_top = base_y + index * 56
            pill_width = 210 + min(len(point), 8) * 18
            draw.rounded_rectangle((base_x, pill_top, base_x + pill_width, pill_top + 40), radius=20, fill=(255, 255, 255, 205))
            draw.text((base_x + 22, pill_top + 7), point, font=point_font, fill=(35, 48, 66, 255))

    def _trim_text(self, text: str, max_chars: int) -> str:
        normalized = text.strip()
        if len(normalized) <= max_chars:
            return normalized
        return normalized[: max_chars - 1] + "…"

    def _palette(self, style_keywords: list[str]) -> tuple[tuple[int, int, int], ...]:
        joined = "".join(style_keywords)
        if "深色" in joined or "高级" in joined:
            return (
                (25, 36, 48),
                (69, 86, 101),
                (196, 171, 116),
                (86, 102, 118),
            )
        if "清新" in joined or "科技" in joined:
            return (
                (229, 239, 245),
                (146, 186, 201),
                (65, 126, 151),
                (191, 218, 229),
            )
        return (
            (58, 74, 90),
            (112, 130, 146),
            (214, 190, 134),
            (143, 157, 170),
        )

    def _load_font(self, size: int, *, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        import platform

        candidates: list[str] = []
        system = platform.system()
        if system == "Windows":
            candidates = [
                "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/simhei.ttf",
                "C:/Windows/Fonts/simsun.ttc",
            ]
        elif system == "Darwin":
            candidates = [
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Medium.ttc",
                "/Library/Fonts/Arial Unicode.ttf",
            ]
        else:  # Linux
            candidates = [
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            ]

        for candidate in candidates:
            if Path(candidate).exists():
                try:
                    return ImageFont.truetype(candidate, size=size)
                except OSError:
                    continue
        return ImageFont.load_default()

    # ------------------------------------------------------------------
    # v0.5: Scene image generation (4 variants)
    # ------------------------------------------------------------------

    def generate_scene_images(
        self,
        *,
        snapshot: dict[str, Any],
        reference_image_path: str,
        category_keywords: list[str] | None = None,
        count: int = 4,
    ) -> list[dict[str, Any]]:
        """Generate multiple scene image variants using img2img.

        Uses category keywords to vary the scene context.
        """
        assets: list[dict[str, Any]] = []
        width, height = self._canvas_size(snapshot.get("page_type", "main_image"))
        base_keywords = category_keywords or snapshot.get("style_keywords", [])

        # Scene variations
        scene_variants = [
            "明亮现代风格",
            "温馨暖色调",
            "简约北欧风",
            "高级灰色调",
        ]

        for i in range(min(count, len(scene_variants))):
            variant_snapshot = {**snapshot}
            variant_snapshot["style_keywords"] = base_keywords + [scene_variants[i]]
            variant_snapshot["_scene_variant"] = scene_variants[i]

            bg_result = self._generate_background(variant_snapshot)

            # Compose with reference image
            cutout_result = self.cutout_with_provider(reference_image_path)
            composite_result, final_result = self._compose_visual(
                snapshot=variant_snapshot,
                background_path=bg_result["file_path"],
                cutout_path=cutout_result["file_path"],
            )
            assets.append({**final_result, "asset_type": "scene_image", "metadata_json": {"variant": scene_variants[i]}})

        return assets

    # ------------------------------------------------------------------
    # v0.5: Detail module image generation
    # ------------------------------------------------------------------

    def generate_detail_modules(
        self,
        *,
        snapshot: dict[str, Any],
        scene_image_path: str,
    ) -> list[dict[str, Any]]:
        """Generate detail page module images (selling points, specs, scene).

        Canvas width: 790px (Taobao detail page standard).
        """
        assets: list[dict[str, Any]] = []
        module_width = 790

        # Module 1: Selling points
        selling_points = snapshot.get("selling_points", ["高品质", "耐用", "美观"])[:4]
        sp_image = self._draw_selling_points_module(module_width, selling_points, snapshot)
        sp_result = self.storage.save_image(sp_image, bucket="exports")
        sp_image.close()
        assets.append({**sp_result, "asset_type": "detail_module", "metadata_json": {"module": "selling_points"}})

        # Module 2: Scene showcase (resize scene image to detail width)
        try:
            scene_img = Image.open(self.storage.absolute_path(scene_image_path))
            ratio = module_width / scene_img.width
            new_height = int(scene_img.height * ratio)
            scene_resized = scene_img.resize((module_width, new_height), Image.LANCZOS)
            scene_result = self.storage.save_image(scene_resized, bucket="exports")
            scene_img.close()
            scene_resized.close()
            assets.append({**scene_result, "asset_type": "detail_module", "metadata_json": {"module": "scene"}})
        except Exception:
            logger.exception("Failed to create scene detail module")

        return assets

    def _draw_selling_points_module(
        self, width: int, selling_points: list[str], snapshot: dict[str, Any]
    ) -> Image.Image:
        """Draw a selling points module image."""
        row_height = 120
        padding = 40
        height = padding * 2 + len(selling_points) * row_height + 80
        image = Image.new("RGB", (width, height), (255, 255, 255))
        draw = ImageDraw.Draw(image)

        title_font = self._load_font(36, bold=True)
        point_font = self._load_font(24, bold=False)

        # Title
        product_name = snapshot.get("product_name", "产品")
        draw.text((padding, padding), f"{product_name} · 核心卖点", font=title_font, fill=(30, 30, 30))

        # Selling points with icons
        y = padding + 80
        for idx, point in enumerate(selling_points):
            # Circle icon
            cx, cy = padding + 20, y + 20
            draw.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=(15, 61, 62))
            num_font = self._load_font(18, bold=True)
            draw.text((cx - 5, cy - 10), str(idx + 1), font=num_font, fill=(255, 255, 255))
            # Text
            draw.text((padding + 56, y + 6), point, font=point_font, fill=(60, 60, 60))
            # Separator
            if idx < len(selling_points) - 1:
                draw.line([(padding, y + row_height - 10), (width - padding, y + row_height - 10)], fill=(230, 230, 230), width=1)
            y += row_height

        return image
