"""Agent decision router — wraps ModelGateway with task-aware context.

States: chat / clarify / ready / generate
Injects task context (current step, entry type, candidates) into LLM planning.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ..models import Task
from .model_gateway import ModelGateway

logger = logging.getLogger(__name__)


class AgentRouter:
    """Routes agent decisions based on task context."""

    def __init__(self, gateway: ModelGateway, db: Session) -> None:
        self.gateway = gateway
        self.db = db

    async def route(
        self,
        message: str,
        task: Task | None = None,
        guide_fields: dict[str, Any] | None = None,
        brand_context: dict[str, Any] | None = None,
        previous_snapshot: dict[str, Any] | None = None,
        project_defaults: dict[str, Any] | None = None,
        user_turns: int = 0,
    ) -> dict[str, Any]:
        """Make an agent decision, enriched with task context.

        Returns the same structure as gateway.plan_generation() plus
        a 'decision' field: chat / clarify / ready / generate.
        """
        # Build task context for the LLM
        task_context = self._build_task_context(task) if task else {}

        # Merge task context into guide_fields
        enriched_fields = dict(guide_fields or {})
        if task_context:
            enriched_fields["_task_context"] = task_context

        # Delegate to existing gateway
        plan = self.gateway.plan_generation(
            message=message,
            guide_fields=enriched_fields if enriched_fields else None,
            brand_context=brand_context,
            previous_snapshot=previous_snapshot,
            project_defaults=project_defaults,
            user_turns=user_turns,
        )

        # Determine decision state
        decision = self._classify_decision(plan, task)
        plan["decision"] = decision

        return plan

    def _build_task_context(self, task: Task) -> dict[str, Any]:
        """Extract relevant context from the task for LLM planning."""
        ctx: dict[str, Any] = {
            "entry_type": task.entry_type,
            "current_step": task.current_step,
            "status": task.status,
        }

        if task.product_category_id and task.product_category:
            ctx["category_name"] = task.product_category.name
            ctx["category_keywords"] = task.product_category.scene_keywords

        selected = [c for c in task.candidates if c.is_selected]
        if selected:
            ctx["selected_candidate"] = selected[0].file_path

        ctx["candidate_count"] = len(task.candidates)
        ctx["has_crawl_runs"] = len(task.crawl_runs) > 0

        return ctx

    def _classify_decision(self, plan: dict[str, Any], task: Task | None) -> str:
        """Classify the gateway plan into a decision state."""
        if plan.get("should_clarify"):
            return "clarify"
        if plan.get("should_generate"):
            return "generate"
        # If task is at a step that expects generation, mark as ready
        if task and task.current_step in ("scene_generate", "content_extend"):
            return "ready"
        return "chat"
