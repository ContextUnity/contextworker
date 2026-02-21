# ContextWorker — Full Documentation

**The Hands of ContextUnity** — Temporal-based durable workflow execution, gRPC service, sub-agent sandbox, and scheduled task infrastructure.

---

## Overview

ContextWorker is the **"Hands"** of the ecosystem:
- Provides gRPC service for workflow triggers and task status
- Manages Temporal workers via modular registry pattern
- Runs sub-agent tasks in logically isolated environments (**strict sandboxing is planned**, currently logical only)
- Manages scheduled jobs (harvesting, enrichment, sync)
- `ExecuteCode` RPC is planned but currently returns `UNIMPLEMENTED`

### Architecture Philosophy

Worker contains **infrastructure only**. Business logic lives in:
- **ContextCommerce** — Registers harvester workflows and activities
- **ContextRouter** — Executes AI agents (Gardener, Matcher)

Modules register themselves via the `WorkerRegistry` and are discovered at startup.

---

## Architecture

```
src/contextworker/
├── __main__.py          ← CLI: gRPC service (default) or --temporal worker
├── config.py            ← WorkerConfig (Pydantic settings)
├── service.py           ← gRPC WorkerService (StartWorkflow, GetTaskStatus, ExecuteCode)
├── schedules.py         ← Temporal schedule management (create/list/pause/delete)
│
├── core/
│   ├── registry.py      ← WorkerRegistry, ModuleConfig, plugin discovery
│   └── worker.py        ← Temporal client setup, worker creation and runner
│
├── subagents/           ← Sub-agent execution framework
│   ├── executor.py      ← SubAgentExecutor (orchestrator with Brain recording)
│   ├── isolation.py     ← IsolationManager, IsolationContext
│   ├── brain_integration.py ← BrainIntegration (step recording to Brain)
│   ├── local_compute.py ← LocalComputeAgent (sandboxed Python execution)
│   ├── rlm_tool.py      ← RLM tool integration
│   ├── monitor.py       ← Execution monitoring
│   └── types.py         ← SubAgentResult, SubAgentDataType
│
└── jobs/
    └── retention.py     ← Data retention policies and cleanup
```

---

## Dual-Mode Operation

Worker runs in two modes:

### 1. gRPC Service (default)

```bash
python -m contextworker
```

Starts the gRPC `WorkerService` that handles:
- `StartWorkflow` — Trigger Temporal workflows by type
- `GetTaskStatus` — Query workflow execution status
- `ExecuteCode` — **UNIMPLEMENTED** (returns `grpc.StatusCode.UNIMPLEMENTED`; sandboxed execution is planned)

### 2. Temporal Worker

```bash
# All discovered modules
python -m contextworker --temporal

# Specific modules only
python -m contextworker --temporal --modules harvest gardener
```

Starts Temporal workers for registered modules (workflows + activities).

---

## gRPC Service (`service.py`)

WorkerService handles workflow triggers and code execution from other services:

```python
class WorkerService(worker_pb2_grpc.WorkerServiceServicer):
    async def StartWorkflow(self, request, context):
        # Routes to appropriate Temporal workflow by workflow_type
        unit = parse_unit(request)
        workflow_type = unit.payload.get("workflow_type")
        # Supported: harvest, gardener, sync, etc.
        handle = await client.start_workflow(...)
        unit.payload["workflow_id"] = handle.id
        return unit.to_protobuf()

    async def GetTaskStatus(self, request, context):
        # Query workflow status by workflow_id
        ...

    async def ExecuteCode(self, request, context):
        # UNIMPLEMENTED — returns grpc.StatusCode.UNIMPLEMENTED
        # Sandboxed code execution is a planned feature
        ...
```

All requests use ContextUnit protocol for provenance tracking.

---

## Module Registry (`core/registry.py`)

Temporal workflow modules register via the `WorkerRegistry`:

```python
from contextworker.core.registry import WorkerRegistry, ModuleConfig

registry = WorkerRegistry()

# Register a module with its workflows and activities
registry.register(
    name="harvest",
    queue="harvest-tasks",
    workflows=[HarvestWorkflow],
    activities=[download_feed, parse_products, store_products],
)
```

### ModuleConfig

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Module name (e.g. "harvest") |
| `queue` | str | Temporal task queue |
| `workflows` | list | Workflow classes |
| `activities` | list | Activity functions |
| `enabled` | bool | Module enabled flag |

### Plugin Discovery

At startup with `--temporal`, the registry discovers modules from installed packages:

```python
registry.discover_plugins()
# Scans for register_all() functions in known module packages
```

---

## Sub-Agent Executor (`subagents/`)

The sub-agent framework provides execution with logical isolation and Brain recording.

> ⚠️ **Note:** Current isolation is **logical only** (via Redis prefixes and DB schemas). Strict runtime sandboxing (e.g., gVisor, containers) is a **planned feature** and not yet implemented. Do not execute untrusted code in this version.

```python
from contextworker.subagents.executor import SubAgentExecutor

executor = SubAgentExecutor(
    brain_endpoint="localhost:50051",
    token=context_token,
)

result = await executor.execute_subagent(
    subagent_id="agent-123",
    task={"code": "print('hello')"},
    agent_type="local_compute",
    isolation_context=IsolationContext(
        subagent_id="agent-123",
        tenant_id="myproject",
    ),
    config={"language": "python"},
    unit=context_unit,  # For security validation
)
```

### Components

| Module | Purpose |
|--------|---------|
| `executor.py` | Orchestrates execution with isolation + Brain recording |
| `isolation.py` | Resource limits, environment isolation |
| `brain_integration.py` | Records each step as an episode in Brain |
| `local_compute.py` | Sandboxed Python code execution |
| `rlm_tool.py` | RLM (Recursive Language Model) tool integration |
| `monitor.py` | Execution monitoring and resource tracking |
| `types.py` | SubAgentResult, SubAgentDataType enums |

### Security Validation

SubAgentExecutor validates ContextToken before execution:
- Checks token expiration
- Requires `worker:execute` permission
- Validates SecurityScopes for write access

---

## Schedule Management (`schedules.py`)

### CLI Commands

```bash
# Create default schedules for tenant
python -m contextworker.schedules create --tenant-id myproject

# List all schedules
python -m contextworker.schedules list

# Pause/unpause schedule
python -m contextworker.schedules pause gardener-every-5min-myproject
python -m contextworker.schedules unpause gardener-every-5min-myproject

# Trigger immediately
python -m contextworker.schedules trigger harvest-camping-trade

# Delete schedule
python -m contextworker.schedules delete my-schedule-id
```

### Programmatic API

```python
from contextworker.schedules import (
    create_schedule,
    list_schedules,
    pause_schedule,
    unpause_schedule,
    delete_schedule,
    ScheduleConfig,
)

config = ScheduleConfig(
    schedule_id="my-custom-schedule",
    workflow_name="MyWorkflow",
    task_queue="my-tasks",
    cron="0 */6 * * *",  # Every 6 hours
)
await create_schedule(client, config, tenant_id="myproject")
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TEMPORAL_HOST` | Temporal server address | `localhost:7233` |
| `TEMPORAL_NAMESPACE` | Temporal namespace | `default` |
| `BRAIN_ENDPOINT` | Brain gRPC endpoint | `localhost:50051` |
| `WORKER_PORT` | gRPC server port | `50053` |
| `LOG_LEVEL` | Log level | `INFO` |

### Config Class

```python
from contextworker.config import WorkerConfig

config = WorkerConfig()
# config.temporal_host, config.temporal_namespace, config.brain_endpoint, config.worker_port
```

---

## Integration with ContextUnity

| Service | Role | How Worker Uses It |
|---------|------|-------------------|
| **ContextCore** | Shared types, gRPC protos | worker.proto, ContextUnit, ContextToken |
| **ContextRouter** | AI orchestration | Calls Gardener/Matcher graphs |
| **ContextCommerce** | E-commerce platform | Registers harvest workflows as modules |
| **ContextBrain** | Knowledge storage | Sub-agent step recording, taxonomy lookups |

### Communication Flow

```
Router → gRPC → Worker → Temporal → Activities → Commerce/Brain
                  ↓
          SubAgentExecutor → Isolation → Brain (recording)
```

---

## Running

### Development

```bash
# gRPC service (default)
python -m contextworker

# Temporal worker
python -m contextworker --temporal

# Custom host
python -m contextworker --temporal --temporal-host temporal.example.com:7233
```

### Production (Docker)

```yaml
services:
  worker-grpc:
    image: contextworker:latest
    command: python -m contextworker
    environment:
      - TEMPORAL_HOST=temporal:7233
      - BRAIN_ENDPOINT=brain:50051

  worker-temporal:
    image: contextworker:latest
    command: python -m contextworker --temporal
    environment:
      - TEMPORAL_HOST=temporal:7233
    deploy:
      replicas: 3  # Scale workers independently
```

---

## Key Files Reference

| File | Lines | Purpose |
|------|-------|---------|
| `__main__.py` | ~100 | CLI: gRPC service or Temporal worker |
| `config.py` | ~50 | WorkerConfig (Pydantic settings) |
| `service.py` | ~450 | gRPC WorkerService (3 RPCs) |
| `schedules.py` | ~270 | Temporal schedule CRUD + CLI |
| `core/registry.py` | ~120 | WorkerRegistry, ModuleConfig, plugin discovery |
| `core/worker.py` | ~90 | Temporal client and worker runner |
| `subagents/executor.py` | ~280 | SubAgentExecutor with Brain recording |
| `subagents/isolation.py` | ~180 | IsolationManager, IsolationContext |
| `subagents/local_compute.py` | ~200 | Sandboxed Python execution |
| `jobs/retention.py` | ~270 | Data retention policies |

---

## Links

- **Documentation**: https://contextworker.dev
- **Repository**: https://github.com/ContextUnity/contextworker
- **Temporal Docs**: https://docs.temporal.io/

---

*Last updated: February 2026*


---

