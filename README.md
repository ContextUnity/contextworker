# ContextWorker

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE.md)
[![Temporal](https://img.shields.io/badge/workflows-Temporal-purple.svg)](https://temporal.io/)

ContextWorker is the **Background Processing Engine** of the [ContextUnity](https://github.com/ContextUnity) ecosystem. Built on [Temporal](https://temporal.io/), it provides durable workflows, scheduled jobs, and sub-agent execution.

> **Worker contains NO business logic.** It provides infrastructure only.

---

## What is it for?

- **Durable Workflows** — Temporal processes that survive restarts and failures
- **Scheduled Jobs** — cron-based recurring tasks (harvesting, enrichment, sync)
- **gRPC Service** — trigger workflows from other services via ContextUnit protocol
- **Sub-Agent System** — isolated execution environments with Brain recording

---

## Quick Start

```bash
# Start gRPC service
export TEMPORAL_HOST="localhost:7233"
uv run python -m contextunity.worker

# Start Temporal worker
uv run python -m contextunity.worker --temporal

# Manage schedules
uv run python -m contextunity.worker.schedules create --tenant-id myproject

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
├── service.py               # gRPC WorkerService (3 RPCs)
├── schedules.py             # Temporal schedule management
├── core/
│   ├── registry.py          # WorkerRegistry, plugin discovery
│   └── worker.py            # Temporal client setup
├── engines/                 # Pluggable execution backends
│   ├── temporal_engine.py   # Temporal engine
│   └── huey_engine.py       # Huey engine
└── jobs/
    ├── orchestrator.py      # Job orchestration
    ├── retention.py         # Data retention policies
    └── scrum_master.py      # Automated task management
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TEMPORAL_HOST` | `localhost:7233` | Temporal server address |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace |
| `WORKER_PORT` | `50053` | gRPC server port |
| `BRAIN_ENDPOINT` | `localhost:50051` | Brain gRPC endpoint |
| `LOG_LEVEL` | `INFO` | Log level |

---

## Further Reading

- **Full Documentation**: [ContextWorker on Astro Site](../../docs/website/src/content/docs/worker/)
- **Agent Boundaries & Golden Paths**: [AGENTS.md](AGENTS.md)
- **Temporal Documentation**: [docs.temporal.io](https://docs.temporal.io/)

## License

This project is licensed under the terms specified in [LICENSE.md](LICENSE.md).
