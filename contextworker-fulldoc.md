# ContextWorker: Automation & Orchestration

## Overview
ContextWorker is the **Task Runner**. It executes long-running jobs, schedules, and event-driven workflows.

## Architecture
- **Pattern**: Polling / Event-Loop / Scheduler.
- **Components**:
    - `scheduler.py`: Cron jobs (Harvest, Sync).
    - `agents/`: Wrappers for calling Router agents (e.g., Gardener polling).
    - `harvester/`: ETL orchestration logic for Commerce.

## Jobs
1.  **Harvester**: Fetch -> Transform -> Brain/Commerce.
2.  **Gardener Poll**: Check Brain for unclassified items -> Call Router.
3.  **Site Sync**: Sync inventory to Horoshop.

## Configuration
Controlled via `contextworker.config` (Pydantic).
