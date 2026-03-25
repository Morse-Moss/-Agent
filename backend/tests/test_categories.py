"""Category CRUD tests — create, subcategory, cycle detection, soft delete."""
from __future__ import annotations


class TestCategoryCreate:
    """Category creation tests."""

    def test_create_category_succeeds(self, client, auth_headers):
        """Creating a top-level category should return 200 with correct data."""
        resp = client.post(
            "/api/categories",
            json={"name": "马桶", "prompt_template": "马桶场景", "scene_keywords": ["卫浴"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "马桶"
        assert data["parent_id"] is None
        assert data["is_active"] is True
        assert data["prompt_template"] == "马桶场景"
        assert "卫浴" in data["scene_keywords"]

    def test_create_subcategory_succeeds(self, client, auth_headers, seed_categories):
        """Creating a child category with valid parent_id should succeed."""
        parent = seed_categories[0]
        resp = client.post(
            "/api/categories",
            json={"name": "台上盆", "parent_id": parent.id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["parent_id"] == parent.id
        assert data["name"] == "台上盆"


class TestCategoryCycleDetection:
    """Cycle detection on parent_id updates."""

    def test_self_reference_rejected(self, client, auth_headers, seed_categories):
        """Setting parent_id to the category's own id should be rejected."""
        cat = seed_categories[0]
        resp = client.put(
            f"/api/categories/{cat.id}",
            json={"parent_id": cat.id},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert "cycle" in resp.json()["detail"].lower()


class TestCategorySoftDelete:
    """Soft delete behavior."""

    def test_soft_delete_sets_inactive(self, client, auth_headers, db_session, seed_categories):
        """DELETE should set is_active=False, not physically remove the row."""
        from app.models import ProductCategory

        cat = seed_categories[0]
        resp = client.delete(f"/api/categories/{cat.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify in DB that is_active is False
        db_session.expire_all()
        deleted = db_session.get(ProductCategory, cat.id)
        assert deleted is not None, "Row should still exist after soft delete"
        assert deleted.is_active is False

    def test_soft_delete_reparents_children(self, client, auth_headers, db_session, seed_categories):
        """Deleting a parent should reparent its children to grandparent."""
        from app.models import ProductCategory

        parent = seed_categories[0]
        # Create a child under parent
        child_resp = client.post(
            "/api/categories",
            json={"name": "挂墙盆", "parent_id": parent.id},
            headers=auth_headers,
        )
        assert child_resp.status_code == 200
        child_id = child_resp.json()["id"]

        # Delete the parent
        resp = client.delete(f"/api/categories/{parent.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert "1 children reparented" in resp.json()["detail"]

        # Child should now point to parent's parent (None for top-level)
        db_session.expire_all()
        child = db_session.get(ProductCategory, child_id)
        assert child.parent_id == parent.parent_id
