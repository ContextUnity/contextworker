"""
gRPC Service for triggering Temporal workflows.

This service allows external systems (e.g., Commerce, Brain)
to trigger Worker workflows via gRPC.
"""

import logging
import grpc

from contextcore import (
    worker_pb2,
    worker_pb2_grpc,
    ContextUnit,
)
from temporalio.client import Client

logger = logging.getLogger(__name__)


class WorkerService(worker_pb2_grpc.WorkerServiceServicer):
    """gRPC Service that triggers Temporal workflows."""

    def __init__(self, temporal_host: str = "localhost:7233"):
        self.temporal_host = temporal_host
        self._client = None

    async def get_client(self):
        if self._client is None:
            self._client = await Client.connect(self.temporal_host)
        return self._client

    async def StartWorkflow(self, request, context):
        """Start a durable workflow process via Temporal."""
        logger.info("Received StartWorkflow request via gRPC")
        client = await self.get_client()

        unit = ContextUnit.from_protobuf(request)
        workflow_type = unit.payload.get("workflow_type")
        tenant_id = unit.payload.get("tenant_id", "default")

        # Import workflows dynamically
        if workflow_type == "harvest":
            from .modules.harvester import HarvestWorkflow
            
            supplier_code = unit.payload.get("supplier_code")
            handle = await client.start_workflow(
                HarvestWorkflow.run,
                args=[supplier_code, tenant_id],
                id=f"harvest-{supplier_code}-{tenant_id}",
                task_queue="harvest-tasks",
            )

        elif workflow_type == "gardener":
            from .modules.gardener import GardenerWorkflow
            
            batch_size = unit.payload.get("batch_size", 50)
            handle = await client.start_workflow(
                GardenerWorkflow.run,
                args=[tenant_id, batch_size],
                id=f"gardener-{tenant_id}",
                task_queue="gardener-tasks",
            )

        elif workflow_type == "sync":
            # Commerce module - may not be installed
            try:
                from modules.sync import SyncWorkflow
                
                channel = unit.payload.get("channel", "horoshop")
                handle = await client.start_workflow(
                    SyncWorkflow.run,
                    args=[channel, tenant_id],
                    id=f"sync-{channel}-{tenant_id}",
                    task_queue="sync-tasks",
                )
            except ImportError:
                context.set_code(grpc.StatusCode.UNAVAILABLE)
                context.set_details("Sync module not installed")
                return request

        else:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f"Unknown workflow type: {workflow_type}")
            return request

        unit.payload["workflow_id"] = handle.id
        unit.payload["run_id"] = handle.result_run_id
        return unit.to_protobuf(worker_pb2.context__unit__pb2)

    async def GetTaskStatus(self, request, context):
        """Get status of a running workflow."""
        # TODO: Implement status tracking
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        return request


async def serve(port: int = 50052, temporal_host: str = "localhost:7233"):
    """Start the gRPC server."""
    server = grpc.aio.server()
    worker_pb2_grpc.add_WorkerServiceServicer_to_server(
        WorkerService(temporal_host=temporal_host), server
    )
    server.add_insecure_port(f"[::]:{port}")
    logger.info(f"Worker gRPC server starting on port {port}")
    await server.start()
    await server.wait_for_termination()
