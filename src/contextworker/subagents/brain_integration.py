"""Brain integration for sub-agent step recording."""

from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from contextcore import ContextToken


from .isolation import IsolationContext
from .types import SubAgentDataType, SubAgentResult

# Try to import SmartBrainClient from contextcore
try:
    from contextcore import SmartBrainClient

    BRAIN_AVAILABLE = True
except ImportError:
    BRAIN_AVAILABLE = False
    SmartBrainClient = None

logger = logging.getLogger(__name__)


class BrainIntegration:
    """Integration with Brain for episodic memory."""

    def __init__(
        self,
        brain_endpoint: str = "brain.contextunity.ts.net:50051",
        token: "ContextToken | None" = None,
    ):
        """Initialize BrainIntegration.

        Args:
            brain_endpoint: Brain gRPC endpoint
            token: Optional ContextToken for authorization
        """
        if not BRAIN_AVAILABLE:
            logger.warning("SmartBrainClient not available, Brain integration disabled")
            self.brain_client = None
        else:
            self.brain_client = SmartBrainClient(tenant_id=None, host=brain_endpoint, token=token)

    async def record_subagent_step(
        self,
        subagent_id: str,
        step_name: str,
        result: SubAgentResult,
        isolation_context: IsolationContext,
        parent_step_id: Optional[str] = None,
    ) -> str:
        """Record a sub-agent step in Brain episodic memory.

        Args:
            subagent_id: Sub-agent ID
            step_name: Name of the step
            result: Result from sub-agent
            isolation_context: Isolation context
            parent_step_id: Optional parent step ID

        Returns:
            Episode ID
        """
        episode_id = str(uuid.uuid4())

        # Format episode content
        content = self._format_episode_content(step_name, result)

        # Prepare metadata
        metadata = {
            "subagent_id": subagent_id,
            "step_name": step_name,
            "data_type": result.data_type.value,
            "status": result.status,
            "parent_step_id": parent_step_id,
            **result.metadata,
        }

        if not self.brain_client:
            logger.debug("Brain client not available, skipping step recording")
            return episode_id

        try:
            # Create ContextUnit for AddEpisode
            from contextcore import ContextUnit

            unit = ContextUnit(
                payload={
                    "user_id": isolation_context.subagent_id,  # Use subagent_id as user_id
                    "tenant_id": isolation_context.tenant_id or "default",
                    "session_id": isolation_context.session_id,
                    "content": content,
                    "metadata": metadata,
                },
                provenance=[f"subagent:{subagent_id}:step:{step_name}"],
                trace_id=isolation_context.trace_id,
            )

            # Call AddEpisode via gRPC with token
            if hasattr(self.brain_client, "_stub") and self.brain_client._stub:
                from contextcore import get_context_unit_pb2

                pb2 = get_context_unit_pb2()
                req = unit.to_protobuf(pb2)
                metadata = self.brain_client._get_metadata()  # Include token in metadata
                await self.brain_client._stub.AddEpisode(req, metadata=metadata)
                logger.info(f"Recorded step {step_name} for sub-agent {subagent_id} in Brain")
            else:
                logger.warning("Brain stub not available, skipping step recording")

        except Exception as e:
            logger.error(f"Failed to record step in Brain: {e}", exc_info=True)
            # Don't fail the sub-agent execution if Brain is unavailable

        return episode_id

    def _format_episode_content(self, step_name: str, result: SubAgentResult) -> str:
        """Format episode content for Brain."""
        if result.data_type == SubAgentDataType.TEXT:
            return f"[{step_name}] {result.data}"
        elif result.data_type == SubAgentDataType.JSON:
            return f"[{step_name}] {json.dumps(result.data, indent=2)}"
        elif result.data_type == SubAgentDataType.CODE:
            return f"[{step_name}] Generated code:\n{result.data}"
        elif result.data_type == SubAgentDataType.IMAGE:
            return f"[{step_name}] Generated image: {result.file_url or result.file_path}"
        elif result.data_type == SubAgentDataType.AUDIO:
            return f"[{step_name}] Generated audio: {result.file_url or result.file_path}"
        elif result.data_type == SubAgentDataType.VIDEO:
            return f"[{step_name}] Generated video: {result.file_url or result.file_path}"
        elif result.data_type == SubAgentDataType.STREAMING_TEXT:
            return f"[{step_name}] Streaming response: {result.stream_url}"
        else:
            return f"[{step_name}] {result.status}"
