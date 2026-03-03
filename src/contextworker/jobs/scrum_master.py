"""
Scrum Master Agent Workflow.
Generates project summaries using ContextRouter and ContextBrain.
"""

import logging

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from contextcore import context_unit_pb2

    from contextworker.core.worker_sdk import AgenticWorkflow

logger = logging.getLogger(__name__)


@workflow.defn
class ScrumMasterWorkflow(AgenticWorkflow):
    @workflow.run
    async def run(self, input_unit: context_unit_pb2.ContextUnit) -> context_unit_pb2.ContextUnit:
        logger.info("Starting ScrumMaster Workflow for %s", input_unit.unit_id)

        # 1. Fetch Issues from ContextPlaneSync
        # 2. Analyze them via ContextRouter
        # 3. Post summary to Slack / Telegram

        # Example prompt for router
        directive = "You are a Scrum Master. Please summarize the latest issues from the project and highlight blockers. Use the ContextPlaneSync tools."

        # Dispatch to Router
        response_unit = await self.execute_agent_loop(
            agent_id="scrum-master-v1",
            instructions=directive,
            input_unit=input_unit,
        )

        logger.info(f"Scrum Master summary generated: {response_unit.unit_id}")
        return response_unit
