# ContextWorker — Agent Instructions

Action layer: Temporal workflow execution, gRPC service, sub-agent sandbox, scheduled tasks, and module registry.

## Entry & Execution
- **Workspace**: `services/worker/`
- **Run gRPC**: `uv run python -m contextunity.worker`
- **Run Temporal**: `uv run python -m contextunity.worker --temporal`
- **Tests**: `uv run --package contextunity-worker pytest`
- **Lint**: `uv run ruff check .`

## Code Standards
You MUST adhere to [Code Standards](../../.agent/skills/code_standards/SKILL.md): 400-line limit, Pydantic strictness, `mise` sync, Ruff compliance.

## Architecture

```
src/contextunity/worker/
├── __main__.py              # Entrypoint
├── cli.py                   # CLI commands (Typer)
├── config.py                # WorkerConfig (Pydantic settings)
├── service.py               # gRPC WorkerService (StartWorkflow, GetTaskStatus, ExecuteCode)
├── server.py                # gRPC server setup
├── schedules.py             # Temporal schedule CRUD + CLI
├── schemas.py               # Request/response schemas
├── interceptors.py          # gRPC interceptors
│
├── core/
│   ├── registry.py          # WorkerRegistry, ModuleConfig, plugin discovery
│   ├── worker.py            # Temporal client setup, worker creation
│   ├── worker_sdk.py        # Worker SDK helpers
│   └── brain_token.py       # Brain token utilities
│
├── engines/                 # Execution backends
│   ├── base.py              # BaseEngine protocol
│   ├── temporal_engine.py   # Temporal workflow engine
│   └── huey_engine.py       # Huey task queue engine
│
└── jobs/
    ├── orchestrator.py      # Job orchestration
    ├── retention.py         # Data retention policies
    └── scrum_master.py      # Automated task management
```

## Strict Boundaries
- **Infrastructure ONLY**: Worker provides Temporal execution, scheduling, agent lifecycle, gRPC service. NO business logic.
- **Business logic belongs in domain packages**: Commerce harvesting → `contextunity.commerce`, AI enrichment → `contextunity.router`.
- **ContextUnit Protocol**: All gRPC communication uses `ContextUnit` envelope.
- **Config-First**: Use `WorkerConfig`. No direct `os.environ`.
- **Temporal Determinism**: No `datetime.now()`, no raw threading in workflows. Use `workflow.now()`.

## Execution Engines
Worker supports pluggable execution backends via `engines/`:
- **`TemporalEngine`** — Durable Temporal workflows (production)
- **`HueyEngine`** — Lightweight Huey task queue (simpler deployments)

Both implement `BaseEngine` protocol. Selected via configuration.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TEMPORAL_HOST` | `localhost:7233` | Temporal server address |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace |
| `WORKER_PORT` | `50053` | gRPC server port |
| `BRAIN_ENDPOINT` | `localhost:50051` | Brain gRPC endpoint |
| `LOG_LEVEL` | `INFO` | Log level |

## Dual-Mode Operation

| Mode | Command | Purpose |
|------|---------|---------|
| gRPC Service | `python -m contextunity.worker` | Receives workflow triggers from other services |
| Temporal Worker | `python -m contextunity.worker --temporal` | Executes registered workflows and activities |
| Specific Modules | `python -m contextunity.worker --temporal --modules harvest gardener` | Run only selected modules |

## Module Registry

```python
from contextunity.worker.core.registry import WorkerRegistry, ModuleConfig

registry = WorkerRegistry()
registry.register(ModuleConfig(
    name="harvest",
    queue="harvest-tasks",
    workflows=[HarvestWorkflow],
    activities=[download_feed, parse_products],
))
```

At startup with `--temporal`, the registry discovers modules from installed packages via `discover_plugins()`.


## Golden Paths

### Adding a Temporal Workflow
1. Create `workflows/myworkflow.py` with `@workflow.defn` class and `@activity.defn` functions
2. Use `@dataclass` for input/output (Temporal serialization)
3. Register in `service.py` `StartWorkflow` handler with `workflow_type` routing
4. Register in `WorkerRegistry` with module config
5. Add tests using `WorkflowEnvironment.start_time_skipping()`

### Adding a Background Agent
1. Create `agents/myagent.py` with `@register("myagent")` decorated `BaseAgent` subclass
2. Implement `run()` polling loop with `asyncio.sleep()` interval
3. Register import in `registry.py` `_load_agents()`
4. Test with `python -m contextunity.worker --agents myagent`

### Adding a Schedule
1. Add `ScheduleConfig` to `DEFAULT_SCHEDULES` in `schedules.py`
2. Create via CLI: `python -m contextunity.worker.schedules create --tenant-id myproject`
3. Manage: `python -m contextunity.worker.schedules list|pause|trigger|delete`

### Testing Workflows
```python
from temporalio.testing import WorkflowEnvironment
async def test_my_workflow():
    async with WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(env.client, task_queue="test", workflows=[MyWorkflow], activities=[...]):
            result = await env.client.execute_workflow(MyWorkflow.run, input, task_queue="test")
            assert result.processed > 0
```

## Further Reading
- [Astro Docs: ContextWorker](../../docs/website/src/content/docs/worker/)
- [Worker Operations Skill](../../.agent/skills/worker_ops/SKILL.md)
