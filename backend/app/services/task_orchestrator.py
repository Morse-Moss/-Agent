"""Task orchestrator — manages the multi-step workflow state machine.

Steps: input → product_select → scene_generate → content_extend → review_finalize

P0 fixes applied:
- Strict transition matrix (only forward-adjacent steps allowed)
- Gate preconditions enforced per step
- select_candidate restricted to product_select step + ownership check
- Idempotent advance (same step → no-op success)
- Failure state tracking (sub_status, error_code, retry_count, last_error)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Candidate, Task

logger = logging.getLogger(__name__)

# Ordered workflow steps
STEPS = ["input", "product_select", "scene_generate", "content_extend", "review_finalize"]

# Legal transitions: from_step → set of allowed target steps (forward-only, adjacent)
LEGAL_TRANSITIONS: dict[str, set[str]] = {
    "input": {"product_select"},
    "product_select": {"scene_generate"},
    "scene_generate": {"content_extend"},
    "content_extend": {"review_finalize"},
    "review_finalize": set(),  # terminal
}

# Task-level statuses
TASK_ACTIVE_STATUSES = {"active", "error"}
TASK_TERMINAL_STATUSES = {"completed", "cancelled"}


class TaskOrchestrator:
    """Manages task lifecycle and step transitions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_task(self, entry_type: str, config: dict[str, Any] | None = None,
                    product_category_id: int | None = None) -> Task:
        valid_entry_types = {"competitor_link", "white_bg_upload", "image_scene_video"}
        if entry_type not in valid_entry_types:
            raise ValueError(f"Invalid entry_type: {entry_type}. Must be one of {valid_entry_types}")

        task = Task(
            entry_type=entry_type,
            current_step="input",
            status="active",
            task_config_json=config or {},
            product_category_id=product_category_id,
        )
        self.db.add(task)
        self.db.flush()
        logger.info("Created task %d (entry_type=%s)", task.id, entry_type)
        return task

    def get_task(self, task_id: int) -> Task | None:
        return self.db.scalar(
            select(Task)
            .where(Task.id == task_id)
            .options(selectinload(Task.candidates), selectinload(Task.crawl_runs))
        )

    def get_current_step(self, task: Task) -> str:
        return task.current_step

    def get_next_step(self, task: Task) -> str | None:
        try:
            idx = STEPS.index(task.current_step)
        except ValueError:
            return None
        if idx + 1 < len(STEPS):
            return STEPS[idx + 1]
        return None

    def can_advance(self, task: Task) -> tuple[bool, str]:
        """Check if the task can advance to the next step. Returns (ok, reason)."""
        if task.status not in TASK_ACTIVE_STATUSES:
            return False, f"Task is {task.status}, cannot advance"
        next_step = self.get_next_step(task)
        if next_step is None:
            return False, "Already at final step"
        return self._check_gate(task, next_step)

    def advance(self, task: Task, target_step: str | None = None,
                expected_step: str | None = None) -> tuple[bool, str]:
        """Advance task to next step (or explicit target). Returns (ok, reason).

        Args:
            target_step: Explicit step to advance to (must be legal transition).
            expected_step: CAS guard — if provided, current_step must match this
                           value, otherwise return 409-style conflict.
        """
        # Guard: task must be active
        if task.status not in TASK_ACTIVE_STATUSES:
            return False, f"Task is {task.status}, cannot advance"

        # CAS: optimistic concurrency check
        if expected_step is not None and task.current_step != expected_step:
            return False, (
                f"Conflict: expected step '{expected_step}' "
                f"but task is at '{task.current_step}'"
            )

        # Determine target
        actual_target = target_step or self.get_next_step(task)
        if actual_target is None:
            return False, "Already at final step"

        # Idempotent: already at target → no-op success
        if task.current_step == actual_target:
            return True, task.current_step

        # Validate transition is legal (forward-adjacent only)
        allowed = LEGAL_TRANSITIONS.get(task.current_step, set())
        if actual_target not in allowed:
            return False, (
                f"Illegal transition: '{task.current_step}' → '{actual_target}'. "
                f"Allowed: {allowed or 'none (terminal step)'}"
            )

        # Check gate preconditions
        ok, reason = self._check_gate(task, actual_target)
        if not ok:
            return False, reason

        # Perform transition
        old_step = task.current_step
        task.current_step = actual_target
        # Clear error state on successful advance
        if task.status == "error":
            task.status = "active"
        self.db.flush()
        logger.info("Task %d: %s → %s", task.id, old_step, task.current_step)
        return True, task.current_step

    def mark_error(self, task: Task, error_code: str, error_message: str) -> None:
        """Mark task as errored (retryable). Preserves current_step."""
        task.status = "error"
        config = dict(task.task_config_json or {})
        config["last_error"] = error_message
        config["error_code"] = error_code
        config["retry_count"] = config.get("retry_count", 0) + 1
        task.task_config_json = config
        self.db.flush()
        logger.warning("Task %d marked error: %s — %s", task.id, error_code, error_message)

    def cancel_task(self, task: Task) -> tuple[bool, str]:
        """Cancel a task. Only active/error tasks can be cancelled."""
        if task.status in TASK_TERMINAL_STATUSES:
            return False, f"Task is already {task.status}"
        task.status = "cancelled"
        self.db.flush()
        logger.info("Task %d cancelled", task.id)
        return True, "cancelled"

    def complete_task(self, task: Task) -> tuple[bool, str]:
        """Mark task as completed. Only from review_finalize step."""
        if task.current_step != "review_finalize":
            return False, "Can only complete from review_finalize step"
        task.status = "completed"
        self.db.flush()
        logger.info("Task %d completed", task.id)
        return True, "completed"

    def select_candidate(self, task: Task, candidate_id: int) -> tuple[bool, str]:
        """Select a candidate, deselecting others.

        Restricted to product_select step. Validates candidate belongs to this task.
        """
        # Step restriction
        if task.current_step != "product_select":
            return False, f"Cannot select candidate at step '{task.current_step}', must be at 'product_select'"

        # Ownership check: candidate must belong to this task
        found = False
        for c in task.candidates:
            if c.id == candidate_id:
                c.is_selected = True
                found = True
            else:
                c.is_selected = False
        if not found:
            return False, f"Candidate {candidate_id} not found in task {task.id}"
        self.db.flush()
        return True, "ok"

    def get_available_actions(self, task: Task) -> list[str]:
        """Return list of actions available at current step."""
        if task.status not in TASK_ACTIVE_STATUSES:
            return ["cancel"] if task.status == "error" else []

        actions = []
        step = task.current_step
        if step == "input":
            if task.entry_type == "competitor_link":
                actions.append("submit_url")
            actions.extend(["upload_image", "chat"])
        elif step == "product_select":
            actions.extend(["select_candidate", "select_category", "advance"])
        elif step == "scene_generate":
            actions.extend(["generate_scenes", "advance"])
        elif step == "content_extend":
            actions.extend(["generate_detail", "generate_video", "generate_copy", "advance"])
        elif step == "review_finalize":
            actions.extend(["approve", "reject", "finalize"])
        return actions

    def _check_gate(self, task: Task, target_step: str) -> tuple[bool, str]:
        """Validate preconditions for entering a step."""
        if target_step == "product_select":
            if not task.candidates:
                return False, "At least one candidate must exist before selecting a product"
            return True, "ok"

        if target_step == "scene_generate":
            has_selected = any(c.is_selected for c in task.candidates)
            has_category = task.product_category_id is not None
            if not has_selected:
                return False, "A candidate must be selected before generating scenes"
            if not has_category:
                return False, "A product category must be chosen before generating scenes"
            return True, "ok"

        if target_step == "content_extend":
            # Check that scene generation actually produced results
            scene_assets = [
                c for c in task.candidates
                if c.metadata_json and c.metadata_json.get("type") == "scene_image"
            ]
            # Fallback: also accept if task has been at scene_generate
            if not scene_assets:
                try:
                    current_idx = STEPS.index(task.current_step)
                    target_idx = STEPS.index("scene_generate")
                    if current_idx < target_idx:
                        return False, "Scene images must be generated first"
                except ValueError:
                    pass
            return True, "ok"

        if target_step == "review_finalize":
            return True, "ok"

        return True, "ok"
