# ContextWorker — Full Documentation

**The Execution Layer of ContextUnity**

ContextWorker is the Temporal-based workflow engine. It provides infrastructure for background jobs, scheduled tasks, and durable workflow execution using the ContextUnit protocol.

---

## Overview

ContextWorker is the **"Hands"** of the ecosystem:
- Executes long-running workflows durably via Temporal
- Manages scheduled jobs (harvesting, enrichment, sync)
- Provides gRPC service for workflow triggers from other services
- Runs background agents via registry pattern

### Architecture Philosophy

Worker contains **infrastructure only**. Business logic lives in:
- **ContextCommerce** — Defines harvester activities, sync logic
- **ContextRouter** — Executes AI agents (Gardener, Matcher)

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            ContextWorker                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  src/contextworker/                                                        │
│  ├── __main__.py          ← CLI entry point                                │
│  ├── config.py            ← Pydantic settings (WorkerConfig)               │
│  ├── registry.py          ← Agent registry (@register decorator)           │
│  ├── service.py           ← gRPC WorkerService                             │
│  ├── schedules.py         ← Temporal schedule management                   │
│  │                                                                         │
│  ├── core/                                                                 │
│  │   └── temporal.py      ← Temporal client setup                          │
│  │                                                                         │
│  ├── agents/              ← Background polling agents                      │
│  │   ├── gardener.py      ← Product enrichment polling                     │
│  │   ├── harvester.py     ← Harvest trigger agent                          │
│  │   └── lexicon.py       ← Lexicon sync agent                             │
│  │                                                                         │
│  └── harvester/           ← Harvester workflow (infrastructure)            │
│      ├── workflow.py      ← HarvestWorkflow definition                     │
│      └── activities.py    ← Download, parse, store activities              │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                     ┌───────────────┐
                     │   Temporal    │
                     │   Server      │
                     └───────────────┘
```

---

## Integration with ContextUnity

ContextWorker connects all services:

| Service | Role | How Worker Uses It |
|---------|------|-------------------|
| **ContextCore** | Shared types, gRPC protos | worker.proto, ContextUnit |
| **ContextRouter** | AI orchestration | Calls Gardener/Matcher graphs |
| **ContextCommerce** | E-commerce platform | Provides workflow activities |
| **ContextBrain** | Knowledge storage | Taxonomy lookups via gRPC |

### Communication Flow

```
Router → gRPC → Worker → Temporal → Activities → Commerce/Brain
```

All gRPC requests use ContextUnit protocol for provenance tracking.

---

## Agent Registry

Background agents register via decorator:

```python
from contextworker.registry import register, BaseAgent

@register("myagent")
class MyAgent(BaseAgent):
    name = "myagent"
    
    async def run(self):
        while self._running:
            items = await self.poll_for_work()
            for item in items:
                await self.process(item)
            await asyncio.sleep(60)
```

### Available Agents

| Agent | Purpose | Poll Interval |
|-------|---------|---------------|
| `gardener` | Enrich pending products | 5 min |
| `harvester` | Trigger supplier imports | 1 hour |
| `lexicon` | Sync terminology | 15 min |

### Running Agents

```bash
# Run all registered agents
python -m contextworker

# Run specific agents
python -m contextworker --agents gardener harvester
```

---

## gRPC Service

WorkerService handles workflow triggers from other services:

```python
# service.py
class WorkerService(worker_pb2_grpc.WorkerServiceServicer):
    async def StartWorkflow(self, request, context):
        unit = ContextUnit.from_protobuf(request)
        workflow_type = unit.payload.get("workflow_type")
        
        if workflow_type == "harvest":
            handle = await client.start_workflow(
                HarvestWorkflow.run,
                args=[supplier_code, tenant_id],
                task_queue="harvest-tasks",
            )
        # Return workflow ID
        unit.payload["workflow_id"] = handle.id
        return unit.to_protobuf()
```

### Supported Workflow Types

| Type | Description | Task Queue |
|------|-------------|------------|
| `harvest` | Supplier data import | `harvest-tasks` |
| `gardener` | Product enrichment | `gardener-tasks` |
| `sync` | Channel synchronization | `sync-tasks` |

---

## Schedule Management

### Default Schedules

```python
DEFAULT_SCHEDULES = [
    ScheduleConfig(
        schedule_id="harvester-daily",
        workflow_name="HarvestWorkflow",
        task_queue="harvest-tasks",
        cron="0 6 * * *",  # 6 AM daily
    ),
    ScheduleConfig(
        schedule_id="gardener-every-5min",
        workflow_name="GardenerWorkflow",
        task_queue="gardener-tasks",
        cron="*/5 * * * *",  # Every 5 minutes
    ),
]
```

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
    delete_schedule,
    ScheduleConfig,
)

# Create custom schedule
config = ScheduleConfig(
    schedule_id="my-custom-schedule",
    workflow_name="MyWorkflow",
    workflow_class=MyWorkflow,
    task_queue="my-tasks",
    cron="0 */6 * * *",  # Every 6 hours
)
await create_schedule(client, config, tenant_id="myproject")

# List all
schedules = await list_schedules(client)
```

---

## Workflows

### HarvestWorkflow

End-to-end supplier data import:

```python
@workflow.defn
class HarvestWorkflow:
    @workflow.run
    async def run(self, supplier_code: str, tenant_id: str) -> HarvestResult:
        # Step 1: Download feed
        raw_data = await workflow.execute_activity(
            download_feed,
            supplier_code,
            start_to_close_timeout=timedelta(minutes=5),
        )
        
        # Step 2: Parse products
        products = await workflow.execute_activity(
            parse_products,
            raw_data,
            supplier_code,
            start_to_close_timeout=timedelta(minutes=10),
        )
        
        # Step 3: Store in database
        result = await workflow.execute_activity(
            store_products,
            products,
            supplier_code,
            start_to_close_timeout=timedelta(minutes=5),
        )
        
        # Step 4: Trigger enrichment (optional)
        if result.new_products > 0:
            await workflow.start_child_workflow(
                EnrichmentWorkflow.run,
                result.product_ids,
            )
        
        return result
```

### Activity Pattern

```python
@activity.defn
async def download_feed(supplier_code: str) -> bytes:
    """Download supplier feed from configured URL."""
    supplier = await get_supplier(supplier_code)
    async with httpx.AsyncClient() as client:
        response = await client.get(supplier.feed_url)
        return response.content

@activity.defn
async def parse_products(raw_data: bytes, supplier_code: str) -> list[dict]:
    """Parse feed using supplier-specific transformer."""
    transformer = get_transformer(supplier_code)
    return transformer.parse(raw_data)
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TEMPORAL_HOST` | Temporal server address | `localhost:7233` |
| `DATABASE_URL` | PostgreSQL connection | Required |
| `PROJECT_DIR` | Config directory | `.` |
| `TENANT_ID` | Default tenant ID | `default` |
| `WORKER_TASK_QUEUE` | Task queue name | `default` |
| `WORKER_MAX_CONCURRENT` | Max parallel activities | `10` |

### Config Class

```python
from contextworker.config import WorkerConfig

config = WorkerConfig()
# Access: config.temporal_host, config.database_url, config.tenant_id
```

---

## Running

### Development

```bash
# Run all agents
python -m contextworker

# Run specific agents
python -m contextworker --agents gardener harvester

# Custom Temporal host
python -m contextworker --temporal-host temporal.example.com:7233

# Run gRPC service
python -m contextworker.service
```

### Production (Docker)

```yaml
services:
  temporal:
    image: temporalio/auto-setup:latest
    ports:
      - "7233:7233"
      - "8080:8080"  # Temporal UI

  worker:
    image: contextcommerce:latest
    command: python -m contextworker
    environment:
      - TEMPORAL_HOST=temporal:7233
      - DATABASE_URL=postgres://...
    deploy:
      replicas: 3  # Scale workers independently
```

---

## Testing

```bash
# Run all tests
uv run pytest

# Unit tests (mock Temporal)
uv run pytest -m unit

# Integration tests (requires Temporal)
uv run pytest -m integration
```

### Mocking Temporal

```python
from temporalio.testing import WorkflowEnvironment

async def test_harvest_workflow():
    async with WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[HarvestWorkflow],
            activities=[download_feed, parse_products, store_products],
        ):
            result = await env.client.execute_workflow(
                HarvestWorkflow.run,
                "test-supplier",
                "test-tenant",
                task_queue="test",
            )
            assert result.created >= 0
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `__main__.py` | CLI entry point, agent runner |
| `config.py` | Pydantic settings (WorkerConfig) |
| `registry.py` | Agent registry, BaseAgent class |
| `service.py` | gRPC WorkerService |
| `schedules.py` | Temporal schedule management |
| `core/temporal.py` | Temporal client setup |
| `agents/gardener.py` | Gardener polling agent |
| `harvester/workflow.py` | HarvestWorkflow definition |

---

## Links

- **Documentation**: https://contextworker.dev
- **Repository**: https://github.com/ContextUnity/contextworker
- **Temporal Docs**: https://docs.temporal.io/
- **Contributing**: [CONTRIBUTING.md](./CONTRIBUTING.md)

---

*Last updated: January 2026*
