"""Video generation gateway — provider abstraction for video APIs.

Supports generic_http_video provider. Uses ARQ for async processing.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class VideoGateway:
    """Abstraction layer for video generation providers."""

    def __init__(
        self,
        provider: str | None = None,
        api_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = provider
        self.api_url = api_url
        self.api_key = api_key
        self.model = model

    @property
    def is_configured(self) -> bool:
        if self.provider in ("fal_kling", "fal_wan"):
            return bool(self.provider and self.api_key)
        return bool(self.provider and self.api_url)

    _VALID_RESOLUTIONS = {"720p", "1080p", "4k"}
    _MAX_DURATION = 60
    _MAX_PROMPT_LENGTH = 500

    async def generate_video(
        self,
        *,
        prompt: str,
        image_url: str | None = None,
        duration_seconds: int = 5,
        orientation: str = "landscape",  # landscape / portrait
        resolution: str = "1080p",
    ) -> dict[str, Any]:
        """Generate a video. Returns dict with video_url, status, etc."""
        if not self.is_configured:
            return {
                "success": False,
                "error": "Video provider not configured. Set APP_VIDEO_PROVIDER and APP_VIDEO_API_URL.",
            }

        # Input validation
        if not prompt or not prompt.strip():
            return {"success": False, "error": "Prompt is required"}
        if len(prompt) > self._MAX_PROMPT_LENGTH:
            return {"success": False, "error": f"Prompt too long ({len(prompt)} chars). Max: {self._MAX_PROMPT_LENGTH}"}
        if duration_seconds < 1 or duration_seconds > self._MAX_DURATION:
            return {"success": False, "error": f"Duration must be 1-{self._MAX_DURATION} seconds"}
        if resolution not in self._VALID_RESOLUTIONS:
            return {"success": False, "error": f"Resolution must be one of: {self._VALID_RESOLUTIONS}"}
        if orientation not in ("landscape", "portrait"):
            return {"success": False, "error": "Orientation must be 'landscape' or 'portrait'"}

        if self.provider == "generic_http_video":
            return await self._call_generic_http(
                prompt=prompt,
                image_url=image_url,
                duration_seconds=duration_seconds,
                orientation=orientation,
                resolution=resolution,
            )
        if self.provider in ("fal_kling", "fal_wan"):
            return await self._call_fal_video(
                prompt=prompt,
                image_url=image_url,
                duration_seconds=duration_seconds,
                orientation=orientation,
                resolution=resolution,
            )

        return {"success": False, "error": f"Unknown video provider: {self.provider}"}

    async def _call_generic_http(self, **kwargs: Any) -> dict[str, Any]:
        """Call a generic HTTP video generation API."""
        try:
            import httpx

            payload = {
                "prompt": kwargs["prompt"],
                "duration": kwargs["duration_seconds"],
                "orientation": kwargs["orientation"],
                "resolution": kwargs["resolution"],
            }
            if kwargs.get("image_url"):
                payload["image_url"] = kwargs["image_url"]
            if self.model:
                payload["model"] = self.model

            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(self.api_url, json=payload, headers=headers)  # type: ignore[arg-type]
                resp.raise_for_status()
                data = resp.json()

            return {
                "success": True,
                "video_url": data.get("video_url") or data.get("url") or data.get("output"),
                "task_id": data.get("task_id"),
                "status": data.get("status", "completed"),
                "raw": data,
            }
        except Exception as exc:
            logger.exception("Video generation failed")
            return {"success": False, "error": str(exc)}

    async def _call_fal_video(self, **kwargs: Any) -> dict[str, Any]:
        """Call fal.ai video API (Kling or Wan 2.6) with queue-based async."""
        try:
            import httpx
            import asyncio

            model_map = {
                "fal_kling": "fal-ai/kling-video/v2.6/pro/image-to-video",
                "fal_wan": "wan/v2.6/image-to-video",
            }
            model_id = model_map.get(self.provider, self.model or model_map["fal_kling"])

            payload: dict[str, Any] = {"prompt": kwargs["prompt"]}
            if kwargs.get("image_url"):
                payload["image_url"] = kwargs["image_url"]
            payload["duration"] = min(kwargs.get("duration_seconds", 5), 10)
            if kwargs.get("orientation") == "portrait":
                payload["aspect_ratio"] = "9:16"
            else:
                payload["aspect_ratio"] = "16:9"

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Key {self.api_key}",
            }

            submit_url = f"https://queue.fal.run/{model_id}"
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(submit_url, json=payload, headers=headers)
                resp.raise_for_status()
                submit_data = resp.json()

            # Check if result is immediate
            if submit_data.get("video") or submit_data.get("video_url"):
                video_url = submit_data.get("video", {}).get("url") or submit_data.get("video_url")
                return {"success": True, "video_url": video_url, "status": "completed", "raw": submit_data}

            # Poll status_url
            status_url = submit_data.get("status_url") or submit_data.get("request_url")
            if not status_url:
                return {"success": False, "error": "fal.ai 未返回 status_url"}

            poll_headers = {"Authorization": f"Key {self.api_key}"}
            for _ in range(90):  # max ~3 minutes
                await asyncio.sleep(2)
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(status_url, headers=poll_headers)
                    result = resp.json()

                status = result.get("status", "")
                if status == "COMPLETED" or result.get("video"):
                    video = result.get("video", {})
                    video_url = video.get("url") if isinstance(video, dict) else result.get("video_url")
                    if video_url:
                        return {"success": True, "video_url": video_url, "status": "completed", "raw": result}
                    return {"success": False, "error": "fal.ai COMPLETED but no video URL"}
                if status in ("FAILED", "CANCELLED"):
                    return {"success": False, "error": f"fal.ai video failed: {result.get('error', status)}"}

            return {"success": False, "error": "fal.ai video generation timed out (3 min)"}

        except Exception as exc:
            logger.exception("fal.ai video generation failed")
            return {"success": False, "error": str(exc)}
