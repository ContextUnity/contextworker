# ContextWorker — Agent Instructions

Action layer: Temporal workflow execution, schedule registration, local tool execution, Router graph orchestration, and background job worker.

**Types & payloads:** [docs/architecture/type-boundaries.md](../../docs/architecture/type-boundaries.md)
**Code quality:** [docs/architecture/code-quality.md](../../docs/architecture/code-quality.md)

## Entry & Execution

Run from monorepo root (`contextunity/`) unless noted.

| Task | Command |
|------|---------|
| Workspace | `services/worker/` |
| Run gRPC | `uv run python -m contextunity.worker` |
| Run Temporal | `uv run python -m contextunity.worker --temporal` |
| Tests | `uv run --package contextunity-worker pytest services/worker/tests` |
| Lint | `cd services/worker && uv run ruff check src tests` |
| Types (worker scope) | `uv run basedpyright services/worker/src/contextunity/worker --warnings` |
| Monorepo gate | `uv run basedpyright --project pyrightconfig.json --warnings` |
| Engine import guard | `uv run --package contextunity-worker pytest services/worker/tests/test_engine_imports.py -q` |
| Core guards (shared types) | [type-boundaries.md §8.1](../../docs/architecture/type-boundaries.md) |

## Type hardening & skills

Use `from __future__ import annotations` when annotating with `TYPE_CHECKING` imports (see §8.1). Import envelope types from core — do not redefine.

| Trigger | Skill |
|---------|-------|
| Typing, JSON/gRPC, ContextUnit payloads, `dict[str, object]`, basedpyright | **`contract-boundaries`** (primary) → **`type-validation`** |
| Core config / exceptions | `core-contract-change` |
| Bug / regression | `diagnose` |
| Implementation loop | `tdd` |

Workflow: [/contract-boundaries](../../.agents/workflows/contract-boundaries.md). Monorepo: [AGENTS.md](../../AGENTS.md).

## Platform Invariants
Follow `packages/core/AGENTS.md` for proto, config, exception, and token rules. In this service:
- **Config**: use `SharedConfig` / Worker config models — no bare `os.getenv()` or `os.environ`.
- **Exceptions**: inherit `contextunity.core.exceptions.ContextUnityError`.
- **Crypto/tokens**: use `contextunity.core.token_utils` — no inline HMAC or encryption.

## Strict Boundaries & Sandboxing
1. **Infrastructure ONLY**: Worker provides workflow execution, task schedules, and queue management. It MUST NOT contain hardcoded domain business logic. Domain code must register its own workflows dynamically.
2. **Deterministic Workflows**: All code inside `@workflow.defn` decorated classes MUST be strictly deterministic.
   - **FORBIDDEN**: `datetime.now()`, `time.sleep()`, raw standard threads, random number generation (`random.random()`), filesystem access, network requests, or importing non-deterministic libraries.
   - **REQUIRED**: Use `workflow.now()`, `await workflow.sleep()`, and execute non-deterministic actions inside `@activity.defn` functions.
3. **Pydantic Configurations**: All dynamic schedules and workflow triggers pass configuration parameters validated via Pydantic schemas with `extra="forbid"`.
4. **ContextUnit Wrapper**: All gRPC triggers must accept inputs wrapped in the `ContextUnit` envelope.

## Temporal Activity Constraints
- **Activity Idempotency**: Since activities can fail and be retried, all activities MUST be idempotent (e.g. database upserts, idempotent API calls).
- **Execution Limits & Timeouts**: Every activity MUST specify an explicit `start_to_close_timeout` or `schedule_to_close_timeout`. Do not use infinite/default timeouts.
- **Activity Inputs**: Inputs/outputs of workflows and activities must be JSON-serializable dataclasses or Pydantic models.
