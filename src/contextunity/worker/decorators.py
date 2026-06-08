"""gRPC error handling decorators for contextunity.worker."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import ParamSpec

from contextunity.core import contextunit_pb2
from contextunity.core.grpc_errors import grpc_error_handler as core_unary_handler
from contextunity.core.types import GrpcUnaryErrorResponseFactory
from contextunity.worker.helpers import worker_error_response_factory

P = ParamSpec("P")
ContextUnit = contextunit_pb2.ContextUnit
_WorkerErrorFactory = GrpcUnaryErrorResponseFactory[ContextUnit]


def grpc_error_handler(
    method: Callable[P, Coroutine[object, object, ContextUnit]],
) -> Callable[P, Coroutine[object, object, ContextUnit]]:
    """Wrap a unary gRPC method with the worker's error response factory."""
    factory: _WorkerErrorFactory = worker_error_response_factory
    return core_unary_handler(method, response_factory=factory)


__all__ = ["grpc_error_handler"]
