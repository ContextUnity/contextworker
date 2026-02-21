"""RLM tool integration for sub-agents."""

from __future__ import annotations

import logging
from typing import Any, Dict

from .local_compute import LocalComputeManager
from .types import SubAgentDataType, SubAgentResult

logger = logging.getLogger(__name__)


class RLMSubAgent:
    """Sub-agent using RLM for local computation."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._rlm_model = None
        self._local_compute = LocalComputeManager()

    async def _get_rlm_model(self):
        """Get RLM model instance."""
        if self._rlm_model is None:
            # Check if RLM is available locally
            if await self._local_compute._check_rlm():
                logger.info("Using local RLM environment")
                self._rlm_model = await self._local_compute.get_local_model(
                    "rlm/gpt-5-mini",
                    config=self.config,
                )
            else:
                # Fallback to remote (Docker environment)
                logger.info("RLM not available locally, using Docker environment")
                from contextrouter.modules.models import model_registry

                self._rlm_model = model_registry.create_llm(
                    "rlm/gpt-5-mini",
                    config=self.config,
                    environment="docker",  # Use Docker environment
                )

        return self._rlm_model

    async def run(self, task: Dict[str, Any]) -> SubAgentResult:
        """Run RLM sub-agent.

        Args:
            task: Task dictionary with:
                - system: System prompt
                - prompt: User prompt
                - rlm_context: Optional RLM-specific context
                - subagent_id: Sub-agent ID

        Returns:
            SubAgentResult with text response
        """
        rlm_model = await self._get_rlm_model()

        # Build request
        from contextrouter.modules.models.types import ModelRequest, TextPart

        request = ModelRequest(
            system=task.get("system", ""),
            parts=[TextPart(text=task.get("prompt", ""))],
        )

        # Execute RLM
        response = await rlm_model.generate(request)

        # Determine if using local or remote
        is_local = await self._local_compute._check_rlm()

        return SubAgentResult(
            subagent_id=task.get("subagent_id", ""),
            status="completed",
            data_type=SubAgentDataType.TEXT,
            data=response.text,
            metadata={
                "rlm_environment": "local" if is_local else "docker",
                "model": response.raw_provider.model_name if hasattr(response, "raw_provider") else "unknown",
                "usage": response.usage.model_dump() if hasattr(response, "usage") else {},
            },
        )

    async def run_with_recording(
        self,
        task: Dict[str, Any],
        record_step: callable,
    ) -> SubAgentResult:
        """Run RLM sub-agent with step-by-step recording.

        Args:
            task: Task dictionary
            record_step: Function to record steps (step_name, result)

        Returns:
            SubAgentResult
        """
        # Record RLM initialization
        await record_step(
            "rlm_init",
            SubAgentResult(
                subagent_id=task.get("subagent_id", ""),
                status="running",
                data_type=SubAgentDataType.TEXT,
                data="Initializing RLM model",
            ),
        )

        # Record RLM execution
        await record_step(
            "rlm_execute",
            SubAgentResult(
                subagent_id=task.get("subagent_id", ""),
                status="running",
                data_type=SubAgentDataType.TEXT,
                data=f"Executing RLM with prompt: {task.get('prompt', '')[:100]}...",
            ),
        )

        # Execute RLM
        result = await self.run(task)

        # Record completion
        await record_step(
            "rlm_complete",
            result,
        )

        return result
