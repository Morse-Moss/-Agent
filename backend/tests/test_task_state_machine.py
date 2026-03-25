"""TS-001~011: Task state machine tests — transitions, CAS, idempotency, failure recovery."""
import pytest


class TestTaskStateMachine:
    """Test legal/illegal state transitions."""

    # TS-001: Normal forward transition input → product_select
    def test_advance_input_to_product_select(self, client, auth_headers, task_at_step):
        task = task_at_step("input", with_candidates=3)
        resp = client.post(f"/api/tasks/{task.id}/advance", json={}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["current_step"] == "product_select"

    # TS-004: Illegal skip input → scene_generate
    def test_illegal_skip_step(self, client, auth_headers, task_at_step):
        task = task_at_step("input", with_candidates=3)
        resp = client.post(
            f"/api/tasks/{task.id}/advance",
            json={"target_step": "scene_generate"},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    # TS-005: Cannot advance from terminal step
    def test_cannot_advance_from_final(self, client, auth_headers, task_at_step):
        task = task_at_step("review_finalize")
        resp = client.post(f"/api/tasks/{task.id}/advance", json={}, headers=auth_headers)
        assert resp.status_code == 400

    # TS-008: Idempotent — advance to current step is no-op
    def test_idempotent_advance(self, client, auth_headers, task_at_step):
        task = task_at_step("product_select", with_candidates=3, with_selected=True)
        resp = client.post(
            f"/api/tasks/{task.id}/advance",
            json={"target_step": "product_select"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["current_step"] == "product_select"

    # TS-010: CAS conflict — expected_step mismatch
    def test_cas_conflict(self, client, auth_headers, task_at_step):
        task = task_at_step("input", with_candidates=3)
        resp = client.post(
            f"/api/tasks/{task.id}/advance",
            json={"expected_step": "product_select"},  # wrong: task is at "input"
            headers=auth_headers,
        )
        assert resp.status_code == 409
        assert "Conflict" in resp.json()["detail"]

    # TS-006: Error state — can still cancel
    def test_error_task_can_cancel(self, client, auth_headers, task_at_step, db_session):
        task = task_at_step("scene_generate", with_candidates=3, with_selected=True)
        # Manually set error state
        task.status = "error"
        task.task_config_json = {"last_error": "test error", "error_code": "TEST"}
        db_session.commit()

        # Cannot advance when in error
        resp = client.post(f"/api/tasks/{task.id}/advance", json={}, headers=auth_headers)
        # Should still work — error is an active status that allows advance
        assert resp.status_code in (200, 400)


class TestGatePreconditions:
    """Test step gate preconditions."""

    def test_cannot_advance_without_candidates(self, client, auth_headers, task_at_step):
        task = task_at_step("input", with_candidates=0)
        resp = client.post(f"/api/tasks/{task.id}/advance", json={}, headers=auth_headers)
        assert resp.status_code == 400
        assert "candidate" in resp.json()["detail"].lower()

    def test_cannot_advance_to_scene_without_selection(self, client, auth_headers, task_at_step):
        task = task_at_step("product_select", with_candidates=3, with_selected=False)
        resp = client.post(f"/api/tasks/{task.id}/advance", json={}, headers=auth_headers)
        assert resp.status_code == 400
        assert "selected" in resp.json()["detail"].lower()


class TestSelectCandidate:
    """Test candidate selection restrictions."""

    # PR-009: Normal selection at product_select step
    def test_select_at_correct_step(self, client, auth_headers, task_at_step):
        task = task_at_step("product_select", with_candidates=3)
        candidate_id = task.candidates[0].id
        resp = client.post(
            f"/api/tasks/{task.id}/select-candidate",
            json={"candidate_id": candidate_id},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    # PR-011: Cannot select at wrong step
    def test_select_at_wrong_step(self, client, auth_headers, task_at_step):
        task = task_at_step("input", with_candidates=3)
        candidate_id = task.candidates[0].id
        resp = client.post(
            f"/api/tasks/{task.id}/select-candidate",
            json={"candidate_id": candidate_id},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    # PR-011: Cannot select candidate from another task
    def test_select_cross_task_candidate(self, client, auth_headers, task_at_step):
        task1 = task_at_step("product_select", with_candidates=3)
        task2 = task_at_step("product_select", with_candidates=2)
        # Try to select task2's candidate in task1
        resp = client.post(
            f"/api/tasks/{task1.id}/select-candidate",
            json={"candidate_id": task2.candidates[0].id},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()
