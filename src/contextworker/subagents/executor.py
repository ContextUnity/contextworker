"""Sub-Agent Executor for Worker."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from contextcore import ContextToken, ContextUnit

from .brain_integration import BrainIntegration
from .isolation import IsolationContext, IsolationManager
from .types import SubAgentDataType, SubAgentResult

logger = logging.getLogger(__name__)


class SubAgentExecutor:
    """Executes sub-agents with isolation and Brain integration."""

    def __init__(
        self,
        brain_endpoint: str = "brain.contextunity.ts.net:50051",
        token: Optional[ContextToken] = None,
    ):
        """Initialize SubAgentExecutor.

        Args:
            brain_endpoint: Brain gRPC endpoint
            token: Optional ContextToken for authorization
        """
        self.isolation_manager = IsolationManager()
        self.brain_integration = BrainIntegration(brain_endpoint=brain_endpoint, token=token)
        self._agent_registry: Dict[str, Any] = {}

    async def execute_subagent(
        self,
        subagent_id: str,
        task: Dict[str, Any],
        agent_type: str,
        isolation_context: IsolationContext,
        config: Dict[str, Any],
        unit: Optional[ContextUnit] = None,
        token: Optional[ContextToken] = None,
    ) -> Dict[str, Any]:
        """Execute a sub-agent with full isolation and Brain recording.

        Args:
            subagent_id: Sub-agent ID
            task: Task to execute
            agent_type: Type of agent
            isolation_context: Isolation context
            config: Agent configuration
            unit: ContextUnit from gRPC request (for security validation)
            token: ContextToken for authorization (optional, extracted from unit if not provided)

        Returns:
            Execution result

        Raises:
            PermissionError: If token validation fails or insufficient permissions
        """
        logger.info(f"Executing sub-agent {subagent_id} (type: {agent_type})")

        # Security validation: Check ContextToken and SecurityScopes
        if unit:
            await self._validate_security(unit, token)

        # Record start step
        start_episode_id = await self.brain_integration.record_subagent_step(
            subagent_id=subagent_id,
            step_name="start",
            result=SubAgentResult(
                subagent_id=subagent_id,
                status="running",
                data_type=SubAgentDataType.TEXT,
                data=f"Starting sub-agent {subagent_id}",
            ),
            isolation_context=isolation_context,
        )

        # Create isolated environment
        isolated_env = await self.isolation_manager.create_isolated_environment(isolation_context)

        try:
            # Get agent instance
            agent = await self._get_agent_instance(
                agent_type=agent_type,
                config=config,
                isolation_context=isolation_context,
                isolated_env=isolated_env,
            )

            # Execute agent (with step recording)
            result = await self._execute_with_recording(
                agent=agent,
                task=task,
                subagent_id=subagent_id,
                isolation_context=isolation_context,
                parent_step_id=start_episode_id,
            )

            # Record completion step
            await self.brain_integration.record_subagent_step(
                subagent_id=subagent_id,
                step_name="complete",
                result=result,
                isolation_context=isolation_context,
                parent_step_id=start_episode_id,
            )

            logger.info(f"Sub-agent {subagent_id} completed successfully")

            return {
                "status": "completed",
                "result": result.to_dict(),
                "subagent_id": subagent_id,
            }

        except Exception as e:
            logger.error(f"Sub-agent {subagent_id} failed: {e}", exc_info=True)

            # Record error step
            await self.brain_integration.record_subagent_step(
                subagent_id=subagent_id,
                step_name="error",
                result=SubAgentResult(
                    subagent_id=subagent_id,
                    status="failed",
                    data_type=SubAgentDataType.TEXT,
                    data=str(e),
                ),
                isolation_context=isolation_context,
                parent_step_id=start_episode_id,
            )

            return {
                "status": "failed",
                "error": str(e),
                "subagent_id": subagent_id,
            }

        finally:
            # Cleanup isolated environment
            await self.isolation_manager.cleanup_isolated_environment(isolated_env)

    async def _execute_with_recording(
        self,
        agent: Any,
        task: Dict[str, Any],
        subagent_id: str,
        isolation_context: IsolationContext,
        parent_step_id: str,
    ) -> SubAgentResult:
        """Execute agent with step-by-step recording."""

        # If agent supports step recording, use it
        if hasattr(agent, "run_with_recording"):
            return await agent.run_with_recording(
                task=task,
                record_step=lambda step_name, result: self.brain_integration.record_subagent_step(
                    subagent_id=subagent_id,
                    step_name=step_name,
                    result=result,
                    isolation_context=isolation_context,
                    parent_step_id=parent_step_id,
                ),
            )

        # Otherwise, execute normally
        result_data = await agent.run(task)

        return SubAgentResult(
            subagent_id=subagent_id,
            status="completed",
            data_type=SubAgentDataType.TEXT,
            data=result_data if isinstance(result_data, (str, dict)) else str(result_data),
        )

    async def _get_agent_instance(
        self,
        agent_type: str,
        config: Dict[str, Any],
        isolation_context: IsolationContext,
        isolated_env: Any,
    ) -> Any:
        """Get agent instance.

        Args:
            agent_type: Type of agent
            config: Agent configuration
            isolation_context: Isolation context
            isolated_env: Isolated environment

        Returns:
            Agent instance
        """
        # Check registry first
        if agent_type in self._agent_registry:
            agent_class = self._agent_registry[agent_type]
            return agent_class(config=config)

        # Try to import from agents module
        try:
            from contextworker.registry import get_registry

            get_registry()
            # Look for agent in registry
            # For now, return a placeholder
            logger.warning(f"Agent type {agent_type} not found in registry, using placeholder")

            # Return placeholder agent
            return PlaceholderAgent(config=config, isolation_context=isolation_context)

        except Exception as e:
            logger.error(f"Failed to get agent instance: {e}")
            raise

    async def _validate_security(
        self,
        unit: ContextUnit,
        token: Optional[ContextToken] = None,
    ) -> None:
        """Validate ContextToken and SecurityScopes before execution.

        Args:
            unit: ContextUnit from gRPC request
            token: ContextToken (should be extracted from gRPC metadata, not from unit.payload)

        Raises:
            PermissionError: If validation fails
        """
        # Check if token is expired
        if token and token.is_expired():
            raise PermissionError("ContextToken has expired")

        # Check worker:execute permission
        if token and not token.has_permission("worker:execute"):
            raise PermissionError(
                f"ContextToken does not have 'worker:execute' permission. Token permissions: {token.permissions}"
            )

        # Check SecurityScopes if present
        if unit.security:
            if token:
                # Check write permission (execution is a write operation)
                if not token.can_write(unit.security):
                    raise PermissionError(f"ContextToken cannot write to SecurityScopes: {unit.security.write}")
            else:
                # No token but security scopes present - deny in production
                from contextcore.config import get_core_config

                config = get_core_config()
                if config.security.enabled:
                    raise PermissionError("Security scopes present but no ContextToken provided. Execution denied.")

        logger.debug("Security validation passed for sub-agent execution")

    def register_agent_type(self, agent_type: str, agent_class: Any) -> None:
        """Register an agent type.

        Args:
            agent_type: Type of agent
            agent_class: Agent class
        """
        self._agent_registry[agent_type] = agent_class
        logger.info(f"Registered agent type: {agent_type}")


class PlaceholderAgent:
    """Placeholder agent for testing."""

    def __init__(self, config: Dict[str, Any], isolation_context: IsolationContext):
        self.config = config
        self.isolation_context = isolation_context

    async def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Run placeholder agent."""
        logger.info(f"Placeholder agent running task: {task}")
        return {
            "message": "Placeholder agent executed",
            "task": task,
            "subagent_id": self.isolation_context.subagent_id,
        }
