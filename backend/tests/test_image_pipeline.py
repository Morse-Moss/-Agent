"""IM-001~007: Image pipeline cutout fallback chain tests."""
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image
import io


class TestCutoutFallbackChain:
    """Test rembg → remove.bg → NumPy fallback chain."""

    def _make_test_image(self, tmp_path, color=(255, 255, 255)):
        """Create a simple test image file."""
        img = Image.new("RGBA", (100, 100), color)
        path = tmp_path / "test.png"
        img.save(path)
        return str(path)

    # IM-001: rembg succeeds
    @patch("app.services.image_pipeline.ImagePipeline._cutout_rembg")
    def test_rembg_success(self, mock_rembg):
        from app.services.image_pipeline import ImagePipeline
        from app.services.storage import StorageService

        mock_rembg.return_value = {"file_path": "processed/result.png", "width": 100, "height": 100}

        storage = MagicMock(spec=StorageService)
        pipeline = ImagePipeline(storage=storage)
        result = pipeline.cutout_with_provider("uploads/test.png", provider="rembg")

        assert result["file_path"] == "processed/result.png"
        mock_rembg.assert_called_once()

    # IM-002: rembg fails, falls back to NumPy
    @patch("app.services.image_pipeline.ImagePipeline._cutout_rembg")
    @patch("app.services.image_pipeline.ImagePipeline._remove_white_background")
    def test_rembg_fails_fallback_numpy(self, mock_numpy, mock_rembg):
        from app.services.image_pipeline import ImagePipeline
        from app.services.storage import StorageService

        mock_rembg.return_value = None  # rembg fails
        mock_numpy.return_value = {"file_path": "processed/numpy_result.png", "width": 100, "height": 100}

        storage = MagicMock(spec=StorageService)
        pipeline = ImagePipeline(storage=storage)
        result = pipeline.cutout_with_provider("uploads/test.png", provider="rembg")

        assert result["file_path"] == "processed/numpy_result.png"
        mock_rembg.assert_called_once()
        mock_numpy.assert_called_once()

    # IM-002: remove.bg fails, falls back to rembg, then NumPy
    @patch("app.services.image_pipeline.ImagePipeline._cutout_remove_bg")
    @patch("app.services.image_pipeline.ImagePipeline._cutout_rembg")
    @patch("app.services.image_pipeline.ImagePipeline._remove_white_background")
    def test_removebg_fails_chain(self, mock_numpy, mock_rembg, mock_removebg):
        from app.services.image_pipeline import ImagePipeline
        from app.services.storage import StorageService

        mock_removebg.return_value = None  # remove.bg fails
        mock_rembg.return_value = None  # rembg also fails
        mock_numpy.return_value = {"file_path": "processed/numpy.png", "width": 100, "height": 100}

        storage = MagicMock(spec=StorageService)
        pipeline = ImagePipeline(storage=storage)
        result = pipeline.cutout_with_provider("uploads/test.png", provider="remove_bg")

        assert result["file_path"] == "processed/numpy.png"
        mock_removebg.assert_called_once()
        mock_rembg.assert_called_once()
        mock_numpy.assert_called_once()

    # IM-003: All providers fail — NumPy is the final fallback
    @patch("app.services.image_pipeline.ImagePipeline._remove_white_background")
    def test_unknown_provider_falls_to_numpy(self, mock_numpy):
        from app.services.image_pipeline import ImagePipeline
        from app.services.storage import StorageService

        mock_numpy.return_value = {"file_path": "processed/fallback.png", "width": 100, "height": 100}

        storage = MagicMock(spec=StorageService)
        pipeline = ImagePipeline(storage=storage)
        result = pipeline.cutout_with_provider("uploads/test.png", provider="unknown_provider")

        assert result["file_path"] == "processed/fallback.png"
        mock_numpy.assert_called_once()


class TestVideoGatewayValidation:
    """Test video gateway input validation."""

    @pytest.mark.asyncio
    async def test_empty_prompt_rejected(self):
        from app.services.video_gateway import VideoGateway
        gw = VideoGateway(provider="generic_http_video", api_url="http://test.com")
        result = await gw.generate_video(prompt="", duration_seconds=5)
        assert not result["success"]
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_prompt_too_long(self):
        from app.services.video_gateway import VideoGateway
        gw = VideoGateway(provider="generic_http_video", api_url="http://test.com")
        result = await gw.generate_video(prompt="x" * 600, duration_seconds=5)
        assert not result["success"]
        assert "too long" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_duration(self):
        from app.services.video_gateway import VideoGateway
        gw = VideoGateway(provider="generic_http_video", api_url="http://test.com")
        result = await gw.generate_video(prompt="test", duration_seconds=100)
        assert not result["success"]
        assert "1-60" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_resolution(self):
        from app.services.video_gateway import VideoGateway
        gw = VideoGateway(provider="generic_http_video", api_url="http://test.com")
        result = await gw.generate_video(prompt="test", resolution="8k")
        assert not result["success"]
        assert "Resolution" in result["error"]


class TestStoragePathTraversal:
    """Test path traversal protection in StorageService."""

    def test_path_traversal_blocked(self):
        from app.services.storage import StorageService
        storage = StorageService()
        with pytest.raises(ValueError, match="Path traversal"):
            storage.absolute_path("../../etc/passwd")

    def test_normal_path_works(self):
        from app.services.storage import StorageService
        storage = StorageService()
        result = storage.absolute_path("uploads/test.png")
        assert "uploads" in str(result)
