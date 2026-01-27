import logging
import grpc
from contextcore import (
    worker_pb2,
    worker_pb2_grpc,
    ContextUnit,
)
from temporalio.client import Client
from .workflows import HarvesterImportWorkflow

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
        workflow_type = unit.payload.get("workflow_type", "HarvesterImportWorkflow")

        if workflow_type == "HarvesterImportWorkflow":
            url = unit.payload.get("url")
            supplier_id = unit.payload.get("supplier_id", "default")

            # Start workflow
            handle = await client.start_workflow(
                HarvesterImportWorkflow.run,
                url,
                id=f"harvest-{supplier_id}",
                task_queue="harvester-tasks",
            )

            unit.payload["workflow_id"] = handle.id
            unit.payload["run_id"] = handle.result_run_id
            return unit.to_protobuf(
                worker_pb2.context__unit__pb2
            )  # worker_pb2 uses context__unit__pb2 internally

        context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
        context.set_details(f"Unknown workflow type: {workflow_type}")
        return request

    async def GetTaskStatus(self, request, context):
        # Implementation for status tracking...
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        return request


async def serve(port: int = 50052, temporal_host: str = "localhost:7233"):
    server = grpc.aio.server()
    worker_pb2_grpc.add_WorkerServiceServicer_to_server(
        WorkerService(temporal_host=temporal_host), server
    )
    server.add_insecure_port(f"[::]:{port}")
    logger.info(f"Worker gRPC server starting on port {port}")
    await server.start()
    await server.wait_for_termination()
