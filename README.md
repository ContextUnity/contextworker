# ContextWorker

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE.md)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Temporal](https://img.shields.io/badge/workflows-Temporal-purple.svg)](https://temporal.io/)
[![GitHub](https://img.shields.io/badge/GitHub-ContextUnity-black.svg)](https://github.com/ContextUnity/contextworker)
[![Docs](https://img.shields.io/badge/docs-contextworker.dev-green.svg)](https://contextworker.dev)

> ⚠️ **Early Version**: This is an early version of ContextWorker. Documentation is actively being developed, and the API may change.

## What is ContextWorker?

ContextWorker is the **Temporal Worker Infrastructure** for ContextUnity. It provides the execution layer for durable workflows, scheduled jobs, and background processing.

**Important**: Worker contains **infrastructure only**. Business logic (harvesting, enrichment) is discovered from installed packages like ContextCommerce.

## Key Features

- **⚡ Durable Workflows** — Temporal-based execution survives restarts and failures
- **📅 Schedule Management** — Create, pause, and trigger recurring jobs
- **🔌 Module Discovery** — Automatically finds activities from installed packages
- **📈 Scalable** — Run multiple worker instances for parallel processing

## Installation

```bash
# Standalone (infrastructure only)
pip install contextworker

# With Commerce modules (full stack)
pip install contextcommerce  # Includes contextworker
```

## Usage

```bash
# Run workers (discovers modules automatically)
python -m contextworker

# Run specific modules only
python -m contextworker --modules harvester gardener

# With custom Temporal host
python -m contextworker --temporal-host temporal.example.com:7233
```

### Schedule Management

```bash
# Create default schedules for a tenant
python -m contextworker.schedules create --tenant-id myproject

# List all schedules
python -m contextworker.schedules list

# Pause/unpause a schedule
python -m contextworker.schedules pause gardener-every-5min-myproject
python -m contextworker.schedules unpause gardener-every-5min-myproject

# Trigger immediately
python -m contextworker.schedules trigger harvest-camping-trade
```

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ContextCommerce                            │
│                                                               │
│  modules/                                                     │
│    harvester/   - Vendor data import                          │
│    gardener/    - Product enrichment                          │
│    sync/        - Channel sync (Horoshop, Prom)               │
│                                                               │
└──────────────────────────────────────────────────────────────┘
                            │
                            │ depends on
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    ContextWorker                              │
│                                                               │
│  core/                                                        │
│    registry.py  - Module discovery                            │
│    worker.py    - Temporal worker factory                     │
│                                                               │
│  schedules.py   - Temporal schedule management                │
│  __main__.py    - CLI entry point                             │
│                                                               │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │   Temporal    │
                    │   Server      │
                    └───────────────┘
```

## Module Discovery

Worker discovers modules by trying to import from known packages:

1. `modules` (when running from Commerce directory)
2. `contextcommerce.modules` (when pip installed)

Modules register via `register_all(registry)` function:

```python
# contextcommerce/modules/__init__.py
def register_all(registry: WorkerRegistry):
    from .gardener import activities as gardener
    from .harvester import activities as harvester
    
    registry.add_activities(gardener)
    registry.add_workflow(harvester.HarvestWorkflow)
```

## Docker Compose

```yaml
services:
  temporal:
    image: temporalio/auto-setup:latest
    ports:
      - "7233:7233"
      - "8080:8080"  # UI

  django:
    image: commerce:latest
    command: python manage.py runserver 0.0.0.0:8000
    
  worker:
    image: commerce:latest  # Same image!
    command: python -m contextworker
    environment:
      - TEMPORAL_HOST=temporal:7233
      - DATABASE_URL=postgres://...
    deploy:
      replicas: 3  # Scale workers independently
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TEMPORAL_HOST` | Temporal server address | `localhost:7233` |
| `DATABASE_URL` | PostgreSQL connection | - |
| `PROJECT_DIR` | Project config directory | `.` |
| `TENANT_ID` | Default tenant ID | `default` |
| `WORKER_TASK_QUEUE` | Queue name | `default` |

## Documentation

- [Full Documentation](https://contextworker.dev) — complete guides and API reference
- [Technical Reference](./contextworker-fulldoc.md) — architecture deep-dive
- [Temporal Docs](https://docs.temporal.io/) — workflow engine documentation

## ContextUnity Ecosystem

ContextWorker is part of the [ContextUnity](https://github.com/ContextUnity) platform:

| Service | Role | Documentation |
|---------|------|---------------|
| **ContextCore** | Shared types and gRPC contracts | [contextcore.dev](https://contextcore.dev) |
| **ContextBrain** | Semantic knowledge store | [contextbrain.dev](https://contextbrain.dev) |
| **ContextRouter** | AI agent orchestration | [contextrouter.dev](https://contextrouter.dev) |
| **ContextCommerce** | E-commerce platform | [contextcommerce.dev](https://contextcommerce.dev) |

## Development

```bash
# Install with dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Run linting
uv run ruff check src/
```

## License

This project is licensed under the terms specified in [LICENSE.md](LICENSE.md).
