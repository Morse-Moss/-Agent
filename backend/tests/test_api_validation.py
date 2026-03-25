"""API-001~010: API validation, authentication, and authorization tests."""
import pytest


class TestAuthentication:
    """API-008/009: Token validation."""

    def test_no_token_returns_401(self, client):
        resp = client.get("/api/projects")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        resp = client.get("/api/projects", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401

    def test_valid_token_works(self, client, auth_headers):
        resp = client.get("/api/categories", headers=auth_headers)
        assert resp.status_code == 200


class TestInputValidation:
    """API-001~007: Parameter validation."""

    # API-001: Missing required fields
    def test_create_task_missing_entry_type(self, client, auth_headers):
        resp = client.post("/api/tasks", json={}, headers=auth_headers)
        assert resp.status_code == 422

    # API-003: Malformed JSON
    def test_malformed_json(self, client, auth_headers):
        resp = client.post(
            "/api/tasks",
            content="not valid json{{{",
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    # API-004: Wrong parameter type
    def test_wrong_type_task_id(self, client, auth_headers):
        resp = client.get("/api/tasks/not-a-number", headers=auth_headers)
        assert resp.status_code == 422

    # API-005: Invalid enum value
    def test_invalid_entry_type(self, client, auth_headers):
        resp = client.post(
            "/api/tasks",
            json={"entry_type": "invalid_type"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    # API-001: Login with empty credentials
    def test_login_empty_username(self, client):
        resp = client.post("/api/auth/login", json={"username": "", "password": "test"})
        assert resp.status_code == 422

    def test_login_too_long_password(self, client):
        resp = client.post("/api/auth/login", json={"username": "a", "password": "x" * 200})
        assert resp.status_code == 422

    # API-002: Oversized message
    def test_generate_message_too_long(self, client, auth_headers):
        resp = client.post(
            "/api/projects/1/generate",
            json={"message": "x" * 3000},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestTaskNotFound:
    """404 for non-existent resources."""

    def test_get_nonexistent_task(self, client, auth_headers):
        resp = client.get("/api/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_advance_nonexistent_task(self, client, auth_headers):
        resp = client.post("/api/tasks/99999/advance", json={}, headers=auth_headers)
        assert resp.status_code == 404


class TestCategoryValidation:
    """Category CRUD validation."""

    def test_create_category_with_nonexistent_parent(self, client, auth_headers):
        resp = client.post(
            "/api/categories",
            json={"name": "Test", "parent_id": 99999},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_update_category_cycle_detection(self, client, auth_headers, seed_categories):
        cat = seed_categories[0]
        # Try to set parent_id to itself
        resp = client.put(
            f"/api/categories/{cat.id}",
            json={"parent_id": cat.id},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert "cycle" in resp.json()["detail"].lower()
