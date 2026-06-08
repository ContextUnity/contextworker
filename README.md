# ContextWorker

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE.md)
[![Temporal](https://img.shields.io/badge/workflows-Temporal-purple.svg)](https://temporal.io/)

ContextWorker is the **Background Processing Engine** of the [ContextUnity](https://github.com/ContextUnity) ecosystem. **Temporal** is the primary durable workflow backend; **Huey** (`engines/huey_engine.py`) supports lightweight local/Redis queues when Temporal is unavailable.

> **Worker contains NO business logic.** It provides infrastructure only.

---

## What is it for?

- **Durable Workflows** — Temporal processes that survive restarts and failures
- **Scheduled Jobs** — cron-based recurring tasks registered by project manifests or plugins
- **gRPC Service** — trigger workflows from other services via ContextUnit protocol
- **Orchestration** — durable execution of registered tools and Router graphs

---

## Quick Start

```bash
# Start gRPC service
export TEMPORAL_HOST="localhost:7233"
uv run python -m contextunity.worker

# Start Temporal worker
uv run python -m contextunity.worker --temporal

# Inspect schedules
uv run python -m contextunity.worker.schedules list

# Run tests
uv run --package contextunity-worker pytest
```

---

## Architecture

```
src/contextunity/worker/
├── __main__.py              # Entrypoint
├── cli.py                   # CLI commands (Typer)
├── config.py                # WorkerConfig (Pydantic)
├── service.py               # gRPC WorkerService (4 RPCs)
├── server.py                # gRPC server bootstrap
├── schemas.py               # Shared payload schemas
├── interceptors.py          # Worker permission interceptor
├── schedules.py             # Temporal schedule management
├── core/
│   ├── registry.py          # WorkerRegistry, plugin discovery
│   ├── worker.py            # Temporal client setup
│   ├── worker_sdk.py        # Worker-side helper utilities
│   └── brain_token.py       # Brain token helpers
├── engines/                 # Pluggable execution backends
│   ├── temporal_engine.py   # Temporal engine
│   └── huey_engine.py       # Huey engine
└── jobs/
    ├── orchestrator.py      # Generic local-tool / Router-graph orchestration
    └── retention.py         # Retention helpers (invoked explicitly)
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TEMPORAL_HOST` | `localhost:7233` | Temporal server address |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace |
| `WORKER_PORT` | `50052` | gRPC server port |
| `CU_BRAIN_GRPC_URL` | `localhost:50051` | Brain gRPC endpoint |
| `WORKER_MODULES` | `` | Extra worker module import paths |
| `WORKER_ENGINE` | `temporal` | Execution backend (`temporal` or `huey`) |
| `LOG_LEVEL` | `INFO` | Log level |

---

## Further Reading

- **Full Documentation**: [ContextWorker on Astro Site](../../website/src/content/docs/worker/)
- **Agent Boundaries & Golden Paths**: [AGENTS.md](AGENTS.md)
- **Temporal Documentation**: [docs.temporal.io](https://docs.temporal.io/)

## License

This project is licensed under the terms specified in [LICENSE.md](LICENSE.md).
