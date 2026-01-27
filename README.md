# ContextWorker

**Temporal Worker Infrastructure for ContextUnity**

ContextWorker provides the core infrastructure for running Temporal workflows. It does NOT contain business logic - modules are discovered from installed packages (e.g., ContextCommerce).

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

Modules register via `register_all(registry)` function.

## Docker Compose

```yaml
services:
  django:
    image: commerce:latest
    command: python manage.py runserver 0.0.0.0:8000
    
  worker:
    image: commerce:latest  # Same image!
    command: python -m contextworker
    deploy:
      replicas: 3  # Scale workers independently
      
  temporal:
    image: temporalio/auto-setup:latest
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TEMPORAL_HOST` | Temporal server address | `localhost:7233` |
| `DATABASE_URL` | PostgreSQL connection | - |
| `PROJECT_DIR` | Project config directory | `.` |
| `TENANT_ID` | Default tenant ID | `default` |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check src/
```

## License

MIT
