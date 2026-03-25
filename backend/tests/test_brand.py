"""Brand profile API tests — GET 404, create, update."""
from __future__ import annotations


class TestBrandProfile:
    """Brand profile CRUD tests."""

    def test_get_brand_returns_profile(self, client, auth_headers):
        """GET /brand/profile should return a brand profile (seeded or created)."""
        # First ensure a brand exists via POST
        client.post(
            "/api/brand/profile",
            json={"name": "测试品牌", "description": "测试描述"},
            headers=auth_headers,
        )
        resp = client.get("/api/brand/profile", headers=auth_headers)
        assert resp.status_code == 200
        assert "name" in resp.json()

    def test_create_brand_succeeds(self, client, auth_headers):
        """POST /brand/profile should create a new brand profile."""
        payload = {
            "name": "测试品牌",
            "description": "高端卫浴品牌",
            "style_summary": "简约现代",
            "recommended_keywords": ["卫浴", "高端", "简约"],
        }
        resp = client.post("/api/brand/profile", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "测试品牌"
        assert data["description"] == "高端卫浴品牌"
        assert data["style_summary"] == "简约现代"
        assert "卫浴" in data["recommended_keywords"]
        assert "id" in data

    def test_update_brand_succeeds(self, client, auth_headers):
        """POST /brand/profile again should update the existing brand (upsert)."""
        # First create
        client.post(
            "/api/brand/profile",
            json={"name": "初始品牌", "description": "初始描述"},
            headers=auth_headers,
        )

        # Then update via the same endpoint
        updated_payload = {
            "name": "更新品牌",
            "description": "更新描述",
            "style_summary": "轻奢风格",
            "recommended_keywords": ["轻奢"],
        }
        resp = client.post("/api/brand/profile", json=updated_payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "更新品牌"
        assert data["description"] == "更新描述"
        assert data["style_summary"] == "轻奢风格"

        # Verify GET returns the updated version
        get_resp = client.get("/api/brand/profile", headers=auth_headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "更新品牌"
