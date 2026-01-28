# ContextWorker — Full Documentation

**The Execution Layer of ContextUnity**

ContextWorker is the Temporal-based workflow engine. It provides infrastructure for background jobs, scheduled tasks, and durable workflow execution.

---

## Overview

ContextWorker is the **hands** of the ecosystem. It:
- Executes long-running workflows durably
- Schedules recurring jobs (harvesting, enrichment, sync)
- Discovers and registers activities from dependent packages
- Provides a unified entry point for all background processing

### Architecture Philosophy

Worker contains **infrastructure only**. Business logic lives in:
- **ContextCommerce** — Defines activities (harvester, sync)
- **ContextRouter** — Executes agent logic (gardener, matcher)

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            ContextWorker                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  src/contextworker/                                                        │
│  ├── __main__.py          ← CLI entry point                                │
│  ├── config.py            ← Pydantic settings                              │
│  ├── service.py           ← Temporal worker factory                        │
│  ├── registry.py          ← Module discovery                               │
│  ├── schedules.py         ← Temporal schedule management                   │
│  │                                                                         │
│  ├── core/                                                                 │
│  │   └── temporal.py      ← Temporal client setup                          │
│  │                                                                         │
│  ├── agents/              ← Agent wrappers (polling, triggers)             │
│  │   └── gardener.py      ← Gardener polling logic                         │
│  │                                                                         │
│  └── harvester/           ← Harvester orchestration                        │
│      ├── workflow.py      ← Main harvest workflow                          │
│      └── activities.py    ← Download, parse, store                         │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Module Discovery

Worker automatically discovers activities from installed packages:

```python
# src/contextworker/registry.py
DISCOVERY_PATHS = [
    "modules",                    # Local (when running from Commerce)
    "contextcommerce.modules",    # Pip installed
]

def discover_modules() -> list[ModuleInfo]:
    """Scan known paths for register_all functions."""
    for path in DISCOVERY_PATHS:
        try:
            module = import_module(path)
            if hasattr(module, "register_all"):
                yield module.register_all
        except ImportError:
            continue
```

### Registration Pattern

Commerce/Router modules register themselves:

```python
# contextcommerce/modules/__init__.py
def register_all(registry: WorkerRegistry):
    from .gardener import activities as gardener_activities
    from .matcher import activities as matcher_activities
    from .harvester import activities as harvester_activities
    
    registry.add_activities(gardener_activities)
    registry.add_activities(matcher_activities)
    registry.add_workflow(harvester_activities.HarvestWorkflow)
```

---

## Temporal Integration

### Client Setup

```python
from contextworker.core.temporal import get_temporal_client

client = await get_temporal_client(host="localhost:7233")
```

### Worker Configuration

```python
from temporalio.worker import Worker
from contextworker.registry import discover_modules

async def create_worker(client, task_queue: str):
    registry = WorkerRegistry()
    for register_fn in discover_modules():
        register_fn(registry)
    
    return Worker(
        client,
        task_queue=task_queue,
        workflows=registry.workflows,
        activities=registry.activities,
    )
```

---

## Workflows

### Harvester Workflow

End-to-end supplier data import:

```python
# src/contextworker/harvester/workflow.py
from temporalio import workflow
from datetime import timedelta

@workflow.defn
class HarvestWorkflow:
    @workflow.run
    async def run(self, supplier_id: str) -> HarvestResult:
        # Step 1: Download feed
        raw_data = await workflow.execute_activity(
            download_feed,
            supplier_id,
            start_to_close_timeout=timedelta(minutes=5),
        )
        
        # Step 2: Parse and transform
        products = await workflow.execute_activity(
            parse_products,
            raw_data,
            start_to_close_timeout=timedelta(minutes=10),
        )
        
        # Step 3: Store in database
        result = await workflow.execute_activity(
            store_products,
            products,
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

### Enrichment Workflow

AI-powered product classification:

```python
@workflow.defn
class EnrichmentWorkflow:
    @workflow.run
    async def run(self, product_ids: list[str]) -> EnrichmentResult:
        # Batch products for Router
        batches = chunk(product_ids, size=50)
        
        results = []
        for batch in batches:
            result = await workflow.execute_activity(
                classify_products,
                batch,
                start_to_close_timeout=timedelta(minutes=10),
            )
            results.append(result)
        
        return EnrichmentResult(
            processed=sum(r.processed for r in results),
            failed=sum(r.failed for r in results),
        )
```

---

## Activities

### Core Activities

```python
# src/contextworker/harvester/activities.py
from temporalio import activity

@activity.defn
async def download_feed(supplier_id: str) -> bytes:
    """Download supplier feed from configured URL."""
    supplier = await get_supplier(supplier_id)
    response = await httpx.get(supplier.feed_url)
    return response.content

@activity.defn
async def parse_products(raw_data: bytes, supplier_id: str) -> list[dict]:
    """Parse feed using supplier-specific transformer."""
    transformer = get_transformer(supplier_id)
    return transformer.parse(raw_data)

@activity.defn
async def store_products(products: list[dict], supplier_id: str) -> StoreResult:
    """Store products in Commerce database."""
    created, updated, errors = 0, 0, 0
    
    for product in products:
        try:
            obj, was_created = await upsert_dealer_product(
                supplier_id, product
            )
            if was_created:
                created += 1
            else:
                updated += 1
        except Exception as e:
            errors += 1
            activity.logger.error(f"Failed: {e}")
    
    return StoreResult(created=created, updated=updated, errors=errors)
```

---

## Schedule Management

### Creating Schedules

```python
from contextworker.schedules import ScheduleManager

manager = ScheduleManager(client)

# Create harvester schedule
await manager.create_schedule(
    schedule_id=f"harvest-{supplier_id}",
    workflow=HarvestWorkflow.run,
    args=[supplier_id],
    cron="0 */6 * * *",  # Every 6 hours
)

# Create enrichment schedule
await manager.create_schedule(
    schedule_id=f"gardener-{tenant_id}",
    workflow=EnrichmentWorkflow.run,
    args=[],
    cron="*/15 * * * *",  # Every 15 minutes
)
```

### CLI Commands

```bash
# Create default schedules
python -m contextworker.schedules create --tenant-id myproject

# List all schedules
python -m contextworker.schedules list

# Pause schedule
python -m contextworker.schedules pause harvest-camping-trade

# Unpause schedule
python -m contextworker.schedules unpause harvest-camping-trade

# Trigger immediately
python -m contextworker.schedules trigger harvest-camping-trade
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TEMPORAL_HOST` | Temporal server | `localhost:7233` |
| `DATABASE_URL` | PostgreSQL URL | Required |
| `PROJECT_DIR` | Config directory | `.` |
| `TENANT_ID` | Default tenant | `default` |
| `WORKER_TASK_QUEUE` | Queue name | `default` |
| `WORKER_MAX_CONCURRENT` | Parallel activities | `10` |

### Config Class

```python
from contextworker.config import WorkerConfig

config = WorkerConfig.from_env()
# Access: config.temporal, config.database, config.tenant_id
```

---

## Running

### Development

```bash
# Run worker (discovers modules)
python -m contextworker

# Run specific modules only
python -m contextworker --modules harvester gardener

# Custom Temporal host
python -m contextworker --temporal-host temporal.example.com:7233
```

### Production (Docker)

```yaml
# docker-compose.yml
services:
  temporal:
    image: temporalio/auto-setup:latest
    ports:
      - "7233:7233"

  worker:
    image: contextcommerce:latest
    command: python -m contextworker
    environment:
      - TEMPORAL_HOST=temporal:7233
      - DATABASE_URL=postgres://...
    deploy:
      replicas: 3  # Scale workers
```

---

## Agent Polling

### Gardener Polling

Periodically checks for unclassified products:

```python
# src/contextworker/agents/gardener.py
async def poll_for_unclassified(tenant_id: str) -> list[str]:
    """Query Commerce for products needing classification."""
    from contextcommerce.harvester.models import DealerProduct
    
    products = DealerProduct.objects.filter(
        enrichment_status="pending",
        tenant_id=tenant_id,
    ).values_list("id", flat=True)[:100]
    
    return list(products)

@activity.defn
async def run_gardener_batch(product_ids: list[str]) -> dict:
    """Call Router's Gardener agent."""
    from contextrouter.cortex.graphs.commerce.gardener import run_gardener
    return await run_gardener(product_ids)
```

---

## Testing

```bash
# Run all tests
uv run pytest

# With Temporal (requires running instance)
uv run pytest -m integration

# Mock Temporal
uv run pytest -m unit
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
                task_queue="test",
            )
            
            assert result.created > 0
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `__main__.py` | CLI entry point |
| `config.py` | Pydantic settings |
| `service.py` | Worker factory |
| `registry.py` | Module discovery |
| `schedules.py` | Schedule management |
| `harvester/workflow.py` | Main harvest workflow |

---

## Links

- **Documentation**: https://contextworker.dev
- **Repository**: https://github.com/ContextUnity/contextworker
- **Temporal Docs**: https://docs.temporal.io/

---

*Last updated: January 2026*
