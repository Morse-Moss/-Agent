from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .model_gateway import ModelGateway
from .storage import StorageService


class ImagePipeline:
    def __init__(self, storage: StorageService, gateway: ModelGateway | None = None) -> None:
        self.storage = storage
        self.gateway = gateway

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
            cutout_result = self._remove_white_background(source_image_path)
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
            color = tuple(int(palette[0][channel] * (1 - ratio) + palette[1][channel] * ratio) for channel in range(3)) + (255,)
            draw.line([(0, index), (width, index)], fill=color)

        accent = palette[2] + (90,)
        draw.rounded_rectangle((60, 70, width - 60, height - 70), radius=48, outline=accent, width=3)
        draw.ellipse((width - 360, -90, width + 80, 350), fill=palette[3] + (80,))
        draw.polygon([(0, height * 0.72), (width * 0.32, height), (0, height)], fill=palette[3] + (110,))

        result = self.storage.save_image(image, bucket="processed")
        image.close()
        return result

    def _remove_white_background(self, source_image_path: str) -> dict[str, Any]:
        source_path = self.storage.absolute_path(source_image_path)
        with Image.open(source_path).convert("RGBA") as original:
            pixels = original.load()
            for y in range(original.height):
                for x in range(original.width):
                    red, green, blue, alpha = pixels[x, y]
                    brightness = (red + green + blue) / 3
                    if brightness > 242 and max(red, green, blue) - min(red, green, blue) < 18:
                        pixels[x, y] = (red, green, blue, 0)
                    elif brightness > 228:
                        new_alpha = max(0, min(alpha, int((255 - brightness) * 6)))
                        pixels[x, y] = (red, green, blue, new_alpha)

            return self.storage.save_image(original, bucket="processed")

    def _compose_visual(
        self,
        *,
        snapshot: dict[str, Any],
        background_path: str,
        cutout_path: str | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        background = Image.open(self.storage.absolute_path(background_path)).convert("RGBA")
        composite = background.copy()
        provider_name = str(snapshot.get("image_provider_used", "")).strip().lower()
        has_cutout = bool(cutout_path)
        use_provider_visual_directly = (not has_cutout) and provider_name not in {"", "local_demo"}
        if use_provider_visual_directly:
            reframed = self._reframe_provider_visual(composite)
            composite.close()
            composite = reframed

        if cutout_path:
            product = Image.open(self.storage.absolute_path(cutout_path)).convert("RGBA")
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
        draw.rounded_rectangle((left + 18, top + 18, left + block_width - 18, top + block_height - 18), radius=30, outline=(140, 148, 160, 255), width=4)
        accent_font = self._load_font(36, bold=True)
        draw.text((left + 36, top + block_height // 2 - 20), snapshot.get("product_name", "铝材"), font=accent_font, fill=(40, 54, 70, 255))

    def _draw_copy(self, image: Image.Image, snapshot: dict[str, Any]) -> None:
        draw = ImageDraw.Draw(image)
        brand_font = self._load_font(34, bold=True)
        title_font = self._load_font(54, bold=True)
        point_font = self._load_font(28, bold=False)

        brand_name = snapshot.get("brand_name", "品牌名")
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
        if "明亮" in joined or "科技" in joined:
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
        candidates = [
            "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
        ]
        for candidate in candidates:
            if Path(candidate).exists():
                try:
                    return ImageFont.truetype(candidate, size=size)
                except OSError:
                    continue
        return ImageFont.load_default()
