# Contributing to ContextWorker

Thanks for contributing to **ContextWorker** — the execution layer of ContextUnity.

## Development Setup

```bash
cd contextworker
uv sync --dev
```

## Pre-commit

```bash
pre-commit install
pre-commit run --all-files
```

## Linting & Tests

```bash
uv run ruff check src/ --fix
uv run ruff format src/
uv run pytest tests/ -v
```

## Branching & PR Flow

### Branch naming

- **Features**: `feat/<short-topic>`
- **Fixes**: `fix/<short-topic>`
- **Chores**: `chore/<short-topic>`

### Merge strategy

- Prefer **Squash & merge** into `main`
- Use **Conventional Commits** style: `feat:`, `fix:`, `docs:`, etc.

### Releases

- Bump version in `pyproject.toml` (SemVer)
- Tag releases as `vX.Y.Z`

---

## Architecture Overview

```
src/contextworker/
├── __main__.py       # CLI entry point
├── config.py         # Pydantic settings (WorkerConfig)
├── registry.py       # Agent registry (@register decorator)
├── service.py        # gRPC WorkerService
├── schedules.py      # Temporal schedule management
│
├── core/
│   └── temporal.py   # Temporal client setup
│
├── agents/           # Background polling agents
│   ├── gardener.py   # Product enrichment polling
│   ├── harvester.py  # Harvest trigger agent
│   └── lexicon.py    # Lexicon sync agent
│
└── harvester/        # Harvester workflow (infrastructure)
    ├── workflow.py   # HarvestWorkflow definition
    └── activities.py # Download, parse, store
```

---

## Golden Path: Adding a Background Agent

Agents are long-running background processes that poll for work.

### Step 1: Create Agent Module

Create `src/contextworker/agents/myagent.py`:

```python
"""MyAgent - Background polling agent."""

import asyncio
import logging

from ..registry import register, BaseAgent

logger = logging.getLogger(__name__)


@register("myagent")
class MyAgent(BaseAgent):
    """Polls for pending items and processes them."""
    
    name = "myagent"
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.poll_interval = config.get("poll_interval", 60)
    
    async def run(self):
        """Main polling loop."""
        logger.info(f"Starting {self.name} agent")
        
        while self._running:
            try:
                # 1. Poll for work
                items = await self.poll_for_work()
                
                if items:
                    logger.info(f"Found {len(items)} items to process")
                    
                    # 2. Process items
                    for item in items:
                        await self.process_item(item)
                
                # 3. Wait before next poll
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"Error in {self.name}: {e}")
                await asyncio.sleep(self.poll_interval)
    
    async def poll_for_work(self) -> list:
        """Query for pending items."""
        # Import domain models here to avoid circular imports
        from contextcommerce.models import PendingItem
        
        return await PendingItem.objects.filter(
            status="pending"
        ).values_list("id", flat=True)[:100]
    
    async def process_item(self, item_id: str):
        """Process a single item."""
        # Your processing logic
        pass
```

### Step 2: Register in Registry

Update `src/contextworker/registry.py`:

```python
def _load_agents():
    try:
        from .agents import gardener  # noqa: F401
        from .agents import harvester  # noqa: F401
        from .agents import myagent  # noqa: F401  # Add this
    except ImportError as e:
        logger.warning(f"Some agents failed to load: {e}")
```

### Step 3: Test

```bash
# Run specific agent
python -m contextworker --agents myagent

# Verify registration
python -c "from contextworker.registry import list_agents; print(list_agents())"
```

---

## Golden Path: Adding a Temporal Workflow

Workflows are durable processes that survive restarts.

### Step 1: Create Workflow Module

Create `src/contextworker/workflows/myworkflow.py`:

```python
"""MyWorkflow - Durable business process."""

from datetime import timedelta
from temporalio import workflow, activity
from dataclasses import dataclass


@dataclass
class MyWorkflowInput:
    tenant_id: str
    item_ids: list[str]


@dataclass  
class MyWorkflowResult:
    processed: int
    failed: int


@activity.defn
async def fetch_items(item_ids: list[str]) -> list[dict]:
    """Activity: Fetch items from database."""
    # Activities can have side effects (DB, HTTP, etc.)
    from contextcommerce.models import Item
    return await Item.objects.filter(id__in=item_ids).values()


@activity.defn
async def process_batch(items: list[dict]) -> dict:
    """Activity: Process a batch of items."""
    processed, failed = 0, 0
    for item in items:
        try:
            # Your processing logic
            processed += 1
        except Exception:
            failed += 1
    return {"processed": processed, "failed": failed}


@workflow.defn
class MyWorkflow:
    """Durable workflow for batch processing."""
    
    @workflow.run
    async def run(self, input: MyWorkflowInput) -> MyWorkflowResult:
        # Step 1: Fetch items
        items = await workflow.execute_activity(
            fetch_items,
            input.item_ids,
            start_to_close_timeout=timedelta(minutes=5),
        )
        
        # Step 2: Process in batches
        batch_size = 50
        total_processed, total_failed = 0, 0
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            result = await workflow.execute_activity(
                process_batch,
                batch,
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=workflow.RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                ),
            )
            total_processed += result["processed"]
            total_failed += result["failed"]
        
        return MyWorkflowResult(
            processed=total_processed,
            failed=total_failed,
        )
```

### Step 2: Register in WorkerService

Update `src/contextworker/service.py`:

```python
elif workflow_type == "myworkflow":
    from .workflows.myworkflow import MyWorkflow
    
    handle = await client.start_workflow(
        MyWorkflow.run,
        args=[MyWorkflowInput(
            tenant_id=tenant_id,
            item_ids=unit.payload.get("item_ids", []),
        )],
        id=f"myworkflow-{tenant_id}",
        task_queue="myworkflow-tasks",
    )
```

### Step 3: Add Schedule (Optional)

Update `src/contextworker/schedules.py`:

```python
DEFAULT_SCHEDULES = [
    # ... existing ...
    ScheduleConfig(
        schedule_id="myworkflow-hourly",
        workflow_name="MyWorkflow",
        workflow_class=None,
        task_queue="myworkflow-tasks",
        cron="0 * * * *",  # Every hour
        args=[],
        description="Run MyWorkflow every hour",
    ),
]
```

---

## Golden Path: Adding a Schedule

Schedules run workflows on a cron basis.

### Step 1: Define Schedule Config

Update `src/contextworker/schedules.py`:

```python
DEFAULT_SCHEDULES = [
    # ... existing ...
    ScheduleConfig(
        schedule_id="my-schedule",
        workflow_name="MyWorkflow",
        workflow_class=None,  # Set at runtime
        task_queue="my-tasks",
        cron="*/30 * * * *",  # Every 30 minutes
        args=[],
        description="Run MyWorkflow every 30 minutes",
    ),
]
```

### Step 2: Create via CLI

```bash
# Create default schedules for tenant
python -m contextworker.schedules create --tenant-id myproject

# Or create individually
python -c "
from contextworker.schedules import create_schedule, ScheduleConfig
import asyncio

config = ScheduleConfig(
    schedule_id='custom-schedule',
    workflow_name='MyWorkflow',
    workflow_class=MyWorkflow,
    task_queue='my-tasks',
    cron='0 */6 * * *',
)
asyncio.run(create_schedule(None, config, 'myproject'))
"
```

### Step 3: Manage Schedules

```bash
# List all schedules
python -m contextworker.schedules list

# Pause schedule
python -m contextworker.schedules pause my-schedule

# Trigger immediately
python -m contextworker.schedules trigger my-schedule
```

---

## Architecture Rules

### ⚠️ Worker Is Infrastructure Only

**ContextWorker MUST NOT contain business logic:**

- ✅ **Worker does**: Temporal execution, scheduling, agent lifecycle, gRPC service
- ❌ **Worker does NOT**: Product transformation, taxonomy rules, pricing

**Business logic belongs in domain services:**
- Harvesting logic → `ContextCommerce`
- Enrichment logic → `ContextRouter`

### ContextUnit Protocol

All gRPC communication uses ContextUnit:

```python
from contextcore import ContextUnit

unit = ContextUnit(
    payload={"workflow_type": "harvest", "supplier_code": "..."},
    provenance=["commerce:api"],
)
```

### Configuration

All settings via `WorkerConfig` from `config.py`:

```python
# ❌ FORBIDDEN
host = os.environ.get("TEMPORAL_HOST")

# ✅ CORRECT
from contextworker.config import WorkerConfig
config = WorkerConfig()
host = config.temporal_host
```

---

## Testing

### Unit Tests (Mock Temporal)

```python
from temporalio.testing import WorkflowEnvironment

async def test_my_workflow():
    async with WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[MyWorkflow],
            activities=[fetch_items, process_batch],
        ):
            result = await env.client.execute_workflow(
                MyWorkflow.run,
                MyWorkflowInput(tenant_id="test", item_ids=["1", "2"]),
                task_queue="test",
            )
            assert result.processed > 0
```

### Integration Tests (Requires Temporal)

```bash
# Start Temporal
docker-compose up -d temporal

# Run integration tests
uv run pytest -m integration
```
