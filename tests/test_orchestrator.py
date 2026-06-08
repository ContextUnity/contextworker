from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from contextunity.core.exceptions import ContextUnityError
from contextunity.core.manifest.models import ContextUnityProject
from contextunity.core.sdk.bootstrap.api import _resolve_toolkits
from contextunity.core.sdk.toolkit import FederatedToolkit, tool
from contextunity.core.sdk.tools import ToolRegistry, federated_tool
from contextunity.worker.core.registry import WorkerRegistry
from contextunity.worker.jobs import orchestrator


@pytest.fixture(autouse=True)
def _clean_registries():
    ToolRegistry.clear()
    yield
    ToolRegistry.clear()
    FederatedToolkit._registry.pop("WorkerToolkit", None)


class TestExecuteFederatedToolActivity:
    @pytest.mark.asyncio
    async def test_executes_registered_federated_tool_locally(self):
        @federated_tool("worker_sum")
        def worker_sum(a: int, b: int, *, ctx) -> dict:
            return {"sum": a + b, "tenant": ctx.caller_tenant}

        result = await orchestrator.execute_federated_tool("worker_sum", {"a": 2, "b": 4}, "tenant-a")
        assert result == {"sum": 6, "tenant": "tenant-a"}

    @pytest.mark.asyncio
    async def test_executes_toolkit_tool_locally(self):
        class WorkerToolkit(FederatedToolkit):
            @tool()
            async def toolkit_echo(self, value: str) -> dict[str, str]:
                return {"value": value, "tenant": self.ctx.caller_tenant}

        manifest = ContextUnityProject.model_validate(
            {
                "apiVersion": "contextunity/v1alpha6",
                "kind": "ContextUnityProject",
                "project": {"id": "proj", "name": "Project", "tenant": "tenant-a"},
                "services": {"router": {"enabled": True}},
                "router": {
                    "default_graph": "demo",
                    "toolkits": ["WorkerToolkit"],
                    "graph": {"demo": {"template": "yaml:demo"}},
                    "policy": {"models": {"llm": {"default": "openai/gpt-4o"}}},
                },
            }
        )
        _resolve_toolkits(manifest)

        result = await orchestrator.execute_federated_tool("toolkit_echo", {"value": "ok"}, "tenant-a")
        assert result == {"value": "ok", "tenant": "tenant-a"}

    @pytest.mark.asyncio
    async def test_missing_tool_fails_closed(self):
        with pytest.raises(ContextUnityError, match="Unknown federated tool.*'missing_tool'"):
            await orchestrator.execute_federated_tool("missing_tool", {}, "tenant-a")


class TestExecuteGraphActivity:
    @pytest.mark.asyncio
    async def test_execute_router_graph_uses_execute_agent(self):
        router = type("Router", (), {"execute_agent": AsyncMock(return_value={"ok": True})})()

        with patch.object(orchestrator, "RouterClient", return_value=router):
            result = await orchestrator.execute_router_graph("graph-a", {"x": 1}, "tenant-a")

        assert result == {"ok": True}
        router.execute_agent.assert_awaited_once_with(
            graph_name="graph-a",
            payload={"x": 1},
        )


class TestRegisterAll:
    def test_registers_tool_and_graph_workflows(self):
        registry = WorkerRegistry()
        orchestrator.register_all(registry)

        module = registry.get_module("orchestrator")
        assert module is not None
        workflow_names = {wf.__name__ for wf in module.workflows}
        activity_names = {activity.__name__ for activity in module.activities}

        assert workflow_names == {"ExecuteToolWorkflow", "ExecuteGraphWorkflow"}
        assert activity_names == {"execute_federated_tool", "execute_router_graph"}
