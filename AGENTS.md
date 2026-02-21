# ContextWorker — Agent instructions

Action layer: Temporal job runner, scheduled tasks (cron), local Python sandboxing (Code Interpreter), and sub-agent execution loops.

**License Context**: This service operates under the **Apache 2.0 Open-Source License**.

## Navigation & Entry
- **Workspace**: `services/contextworker/`
- **Tests**: run `uv run --package contextworker pytest` from the monorepo root.

## Architecture Context (Current Code State)
- **Temporal Configuration (`core/worker.py`)**: Connects to the Temporal cluster establishing `Activity` and `Workflow` listener loops on configured task queues.
- **Workflow Registry (`core/registry.py`)**: Cross-service module discovery allowing external services (like Commerce) to inject their own Workflow definitions via Python module paths.
- **Schedules (`schedules.py`)**: Abstraction wrapper over `temporalio.client` enabling programmatic creation of recurring cron jobs linked inherently to Tenant identities.
- **gRPC Service (`service.py`)**: Exposes endpoints triggering Workflows or direct execution commands over the `WorkerServiceServicer`.
- **Sub-agents (`subagents/`)**: Includes the isolated Python compute sandbox enabling Router agents to dynamically write and execute Python scripts locally (`local_compute.py`), capturing execution traces synchronously into ContextBrain (`brain_integration.py`).

## Documentation Strategy
When modifying or extending this service, update documentation strictly across these boundaries:
1. **Technical Specifications**: `services/contextworker/contextworker-fulldoc.md`. Document any changes to Temporal worker configurations, subagent isolation environments, or registry mechanisms here.
2. **Public Website**: `docs/website/src/content/docs/worker/`. When publishing user-facing guidance on how to run isolated operations.
3. **Plans & Architecture**: `plans/worker/` and `plans/net/`.

## Rules specific to ContextWorker
- Ensure that Python compute sandboxing strictly enforces resource limits and filesystem isolation.
- When creating Temporal workflows, adhere to Temporal's determinism constraints (e.g., no raw threading or `datetime.now()` direct calls; use `workflow.now()`).


## AI Agent Rules (`rules/`)
ContextUnity uses strict AI assistant rules. You **MUST** review and adhere to the following rule files before modifying this service:
- `rules/global-rules.md` (General ContextUnity architecture and boundaries)
- `rules/contextworker-rules.md` (Specific constraints for the **contextworker** domain)
