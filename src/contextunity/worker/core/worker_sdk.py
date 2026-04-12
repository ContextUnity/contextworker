"""
Agentic Workflow SDK — base class for AI agent workflows.

Provides the execute_agent_loop() helper for workflows that interact
with cu.router to run agents and tools.
"""

from __future__ import annotations

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    from contextunity.core import contextunit_pb2, get_contextunit_logger

logger = get_contextunit_logger(__name__)


@activity.defn
async def _call_router_agent(
    agent_id: str,
    instructions: str,
    input_payload: bytes,
) -> bytes:
    """Activity that calls cu.router to execute an agent.

    Runs outside the workflow sandbox so it can make gRPC calls.
    Returns serialized ContextUnit bytes.
    """
    from contextunity.core.sdk import RouterClient

    client = RouterClient()
    response = await client.execute_agent(
        agent_id=agent_id,
        instructions=instructions,
        input_payload=input_payload,
    )
    return response


class AgenticWorkflow:
    """Base class for Temporal workflows that orchestrate cu.router agents.

    Subclass and override ``run()`` with ``@workflow.run``.

    Usage::

        @workflow.defn
        class MyWorkflow(AgenticWorkflow):
            @workflow.run
            async def run(self, input_unit):
                return await self.execute_agent_loop(
                    agent_id="my-agent",
                    instructions="Do the thing",
                    input_unit=input_unit,
                )
    """

    async def execute_agent_loop(
        self,
        agent_id: str,
        instructions: str,
        input_unit: contextunit_pb2.ContextUnit,
    ) -> contextunit_pb2.ContextUnit:
        """Execute an agent loop via cu.router.

        Schedules a Temporal activity that makes the gRPC call to Router,
        keeping the workflow sandbox clean.
        """
        result_bytes = await workflow.execute_activity(
            _call_router_agent,
            args=[agent_id, instructions, input_unit.SerializeToString()],
            start_to_close_timeout=workflow.timedelta(minutes=5),
        )
        # Deserialize response bytes via conformant SDK method
        from contextunity.core import ContextUnit

        pydantic_unit = ContextUnit.from_protobuf_bytes(result_bytes, contextunit_pb2)
        return pydantic_unit.to_protobuf(contextunit_pb2)
