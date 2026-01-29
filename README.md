# ContextWorker

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE.md)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Temporal](https://img.shields.io/badge/workflows-Temporal-purple.svg)](https://temporal.io/)
[![GitHub](https://img.shields.io/badge/GitHub-ContextUnity-black.svg)](https://github.com/ContextUnity/contextworker)
[![Docs](https://img.shields.io/badge/docs-contextworker.dev-green.svg)](https://contextworker.dev)

> ⚠️ **Early Version**: This is an early version of ContextWorker. Documentation is actively being developed, and the API may change.

## What is ContextWorker?

ContextWorker is the **Background Processing Engine** of the [ContextUnity](https://github.com/ContextUnity) ecosystem. Built on [Temporal](https://temporal.io/), it provides:

- **Durable Workflows** — long-running processes that survive restarts and failures
- **Scheduled Jobs** — cron-based recurring tasks (harvesting, enrichment, sync)
- **gRPC Service** — trigger workflows from other services via ContextUnit protocol
- **Agent System** — polling-based background agents with registry pattern

Think of it as the **"Hands"** of the ecosystem — executing the work orchestrated by Router.

## Core Concepts

### Infrastructure Only

Worker contains **NO business logic**. It provides infrastructure for:
- Temporal workflow/activity execution
- Schedule management
- Agent lifecycle
- gRPC service for workflow triggers

**Business logic lives in domain packages:**
- Commerce harvesting → `ContextCommerce`
- AI enrichment → `ContextRouter`

### ContextUnit Protocol

All inter-service communication uses ContextUnit:

```python
from contextcore import ContextUnit

# Trigger workflow via gRPC
unit = ContextUnit(
    payload={
        "workflow_type": "harvest",
        "supplier_code": "camping-trade",
        "tenant_id": "myproject",
    },
    provenance=["commerce:trigger"],
)
```

> **What is gRPC?** [gRPC](https://grpc.io/) is a high-performance RPC framework using Protocol Buffers. It provides type-safe, efficient service-to-service communication with built-in streaming.

## Integration with ContextUnity

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ContextRouter                               │
│                     (The "Mind" — Orchestration)                    │
├─────────────────────────────────────────────────────────────────────┤
│  • Orchestrates AI agents (Gardener, Matcher)                       │
│  • Routes LLM requests                                              │
│  • Calls Worker to trigger workflows                                │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ triggers via gRPC
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         ContextWorker                               │
│                     (The "Hands" — Execution)                       │
├─────────────────────────────────────────────────────────────────────┤
│  • Executes durable Temporal workflows                              │
│  • Manages scheduled jobs (harvest, enrich, sync)                   │
│  • Runs background agents (polling loops)                           │
│  • Exposes gRPC service for workflow triggers                       │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ runs workflows defined in
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        ContextCommerce                              │
│                    (The "Store" — Domain Logic)                     │
├─────────────────────────────────────────────────────────────────────┤
│  • Defines harvester workflows/activities                           │
│  • Defines sync workflows (Horoshop, Prom)                          │
│  • Product catalog and taxonomy                                     │
└─────────────────────────────────────────────────────────────────────┘
```

| Service | Role | How Worker Uses It |
|---------|------|-------------------|
| **ContextCore** | Shared types, gRPC protos | worker.proto, ContextUnit |
| **ContextRouter** | AI orchestration | Executes Gardener/Matcher agents |
| **ContextCommerce** | E-commerce platform | Provides workflows/activities |
| **ContextBrain** | Knowledge storage | Taxonomy lookups via gRPC |

## Key Features

- **⚡ Temporal Integration** — durable, fault-tolerant workflow execution
- **📅 Schedule Management** — create, pause, trigger recurring jobs
- **🔌 Agent Registry** — `@register` decorator for background agents
- **📡 gRPC Service** — WorkerService for workflow triggers
- **📈 Scalable** — run multiple worker instances for parallel processing

## Architecture

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
    └── activities.py # Download, parse, store activities
```

## Quick Start

```bash
# Install
pip install contextworker

# Run worker (discovers agents automatically)
python -m contextworker

# Run specific agents
python -m contextworker --agents gardener harvester

# Create schedules for tenant
python -m contextworker.schedules create --tenant-id myproject
```

## Installation

```bash
# Standalone (infrastructure only)
pip install contextworker

# With Commerce modules (full stack)
pip install contextcommerce  # Includes contextworker as dependency
```

## Configuration

```bash
# Temporal
export TEMPORAL_HOST="localhost:7233"
export WORKER_TASK_QUEUE="default"
export WORKER_MAX_CONCURRENT="10"

# Database (for activities that access Commerce)
export DATABASE_URL="postgres://user:pass@localhost/db"

# Tenant
export TENANT_ID="default"
export PROJECT_DIR="."
```

## Documentation

- [Full Documentation](https://contextworker.dev) — complete guides and API reference
- [Technical Reference](./contextworker-fulldoc.md) — architecture deep-dive
- [Contributing Guide](./CONTRIBUTING.md) — Golden Paths for adding functionality
- [Temporal Docs](https://docs.temporal.io/) — workflow engine documentation

## Contributing

See our [Contributing Guide](./CONTRIBUTING.md) for:

- **Golden Path: Adding an Agent** — registry pattern, lifecycle
- **Golden Path: Adding a Workflow** — Temporal patterns, activities
- **Golden Path: Adding a Schedule** — cron configuration

## License

This project is licensed under the terms specified in [LICENSE.md](LICENSE.md).
