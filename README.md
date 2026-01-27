# ContextWorker

High-performance Temporal Worker for ContextUnity ecosystem.

## Overview

ContextWorker provides distributed, durable task orchestration using [Temporal](https://temporal.io/). It handles long-running workflows for data processing, content generation, and other asynchronous operations across the ContextUnity platform.

## Features

- **Durable Workflows**: Workflows survive process crashes and restarts
- **Activity Retries**: Automatic retries with exponential backoff
- **Distributed Execution**: Scale workers across multiple machines
- **Observability**: Built-in monitoring and tracing with ContextCore logging
- **Type Safety**: Full type annotations for all workflows and activities
- **Centralized Logging**: Automatic trace_id propagation from ContextUnit

## Architecture

ContextWorker follows Temporal's workflow/activity pattern:

- **Workflows**: Orchestrate business logic, define execution order, handle timeouts
- **Activities**: Execute individual units of work (HTTP calls, DB operations, etc.)

### Agent Architecture

ContextWorker runs **Agent Daemons** - long-running processes that poll queues and execute tasks.

**Registered Agents:**

| Agent | Description | Mode |
|-------|-------------|------|
| `gardener` | Taxonomy classification via LLM | Polling |
| `harvester` | Stock import workflows | Temporal |
| `lexicon` | Content research & generation | Polling |

### Temporal Workflows (Harvester)

- `HarvesterImportWorkflow`: Imports vendor data through fetch → parse → stage pipeline

### Activities

**Basic Activities:**
- `fetch_vendor_data`: Fetch raw data from vendor URLs
- `parse_raw_payload`: Parse vendor payloads into structured items
- `update_staging_buffer`: Insert/update items in staging database

**Advanced Activities:**
- `process_product_images`: Download, resize, and optimize product images
- `generate_seo_content`: Generate SEO metadata using LLM

## Installation

```bash
pip install contextworker
```

Or with dependencies:

```bash
pip install contextworker[temporal]
```

## Usage

### Starting the Worker

```python
from contextworker import main
import asyncio

asyncio.run(main())
```

Or via command line:

```bash
python -m contextworker
```

### Environment Variables

- `TEMPORAL_HOST`: Temporal server address (default: `localhost:7233`)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `SERVICE_NAME`: Service name for observability (default: `contextworker`)
- `SERVICE_VERSION`: Service version
- `OTEL_ENABLED`: Enable OpenTelemetry (true/false)
- `OTEL_ENDPOINT`: OpenTelemetry collector endpoint

### Running a Workflow

```python
from temporalio.client import Client
from contextworker.workflows import HarvesterImportWorkflow

async def import_vendor_data():
    client = await Client.connect("localhost:7233")
    result = await client.execute_workflow(
        HarvesterImportWorkflow.run,
        "https://vendor.com/data.xml",
        id="import-123",
        task_queue="harvester-tasks",
    )
    print(result)

import asyncio
asyncio.run(import_vendor_data())
```

## Development

### Prerequisites

- Python 3.12+
- Temporal server (local or remote)
- `temporalio` package

### Running Tests

```bash
pytest tests/
```

### Type Checking

```bash
mypy src/contextworker
```

## Logging

ContextWorker uses ContextCore's centralized logging system. Logging is automatically configured in `worker.py`:

```python
# Logging is set up automatically in main()
from contextcore import setup_logging, load_shared_config_from_env

config = load_shared_config_from_env()
setup_logging(config=config, service_name="contextworker")
```

### Using Loggers

```python
from contextcore import get_context_unit_logger
from contextcore import ContextUnit

logger = get_context_unit_logger(__name__)

# Log with ContextUnit (trace_id automatically included)
unit = ContextUnit(payload={"workflow_id": "123"})
logger.info("Starting workflow", unit=unit)
```

All logs automatically include `trace_id` and `unit_id` for full observability. See [ContextCore Logging Guide](https://contextcore.dev/guides/logging) for details.

## Integration with ContextUnity

ContextWorker integrates with other ContextUnity services:

- **ContextRouter**: For LLM-based content generation activities
- **ContextBrain**: For semantic search and knowledge retrieval
- **ContextCommerce**: For product data processing and catalog updates
- **ContextCore**: For centralized logging and configuration

## Workflow Patterns

### Sequential Execution

Activities run one after another:

```python
raw_data = await workflow.execute_activity(fetch_vendor_data, url)
items = await workflow.execute_activity(parse_raw_payload, raw_data)
count = await workflow.execute_activity(update_staging_buffer, items)
```

### Parallel Execution

Use `workflow.gather()` for parallel activities:

```python
results = await workflow.gather(
    workflow.execute_activity(process_images, image_urls),
    workflow.execute_activity(generate_seo, product_data),
)
```

### Error Handling

Temporal automatically retries activities on failure. Configure retry policies:

```python
await workflow.execute_activity(
    fetch_vendor_data,
    url,
    start_to_close_timeout=timedelta(minutes=5),
    retry_policy=RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_attempts=3,
    ),
)
```

## License

Apache 2.0

## Links

- [Temporal Documentation](https://docs.temporal.io/)
- [ContextUnity Architecture](../../docs/ContextUnity.md)
- [ContextCore](../contextcore/README.md)
