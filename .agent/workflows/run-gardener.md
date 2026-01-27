---
description: How to run the Gardener taxonomy classification agent
---

# Run Gardener Agent

## Prerequisites

1. Brain DB running with tables:
   - `gardener_pending`
   - `catalog_taxonomy`

2. Commerce DB running with table:
   - `harvester_dealerproduct`

3. ContextRouter running or accessible

4. Environment configured:
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

## Steps

// turbo
1. Verify dependencies installed:
   ```bash
   cd /home/oleksii/Projects/cu/contextworker
   uv sync
   ```

// turbo
2. Check configuration:
   ```bash
   python -c "from contextworker.config import WorkerConfig; c = WorkerConfig.from_env(); print(f'Brain: {c.brain_database_url[:30]}...')"
   ```

3. Run the agent:
   ```bash
   python -m contextworker --agent gardener
   ```

4. Monitor logs for:
   - `Gardener starting. Poll: 60s, Batch: 50`
   - `Processed N items`
   - `Saved N proposals`

## Verify Results

// turbo
5. Check pending queue:
   ```bash
   psql $BRAIN_DATABASE_URL -c "SELECT count(*) as pending FROM gardener_pending WHERE status='pending'"
   ```

// turbo
6. Check proposals:
   ```bash
   psql $BRAIN_DATABASE_URL -c "SELECT item_type, raw_value, proposal FROM gardener_pending WHERE status='proposed' LIMIT 5"
   ```

## Stop

Press `Ctrl+C` to stop the agent gracefully.

## Troubleshooting

- **No items processing**: Check if `gardener_pending` has `status='pending'` items
- **LLM errors**: Check `CONTEXT_ROUTER_URL` and API key
- **DB connection errors**: Verify `BRAIN_DATABASE_URL` and `COMMERCE_DATABASE_URL`
