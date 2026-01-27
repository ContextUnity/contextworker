# ContextWorker Rules

## Code Style

1. **Pydantic for Config**: All configuration classes must use Pydantic BaseModel or BaseSettings
2. **Async for I/O**: Database and HTTP operations must be async
3. **Type Hints**: All function signatures must have type hints
4. **Docstrings**: All public classes and functions must have docstrings

## Agent Rules

1. **Registry Pattern**: All agents must be registered with `@register("name")` decorator
2. **Idempotent**: Agent operations must be safe to retry
3. **Graceful Shutdown**: Agents must respect `self._running` flag
4. **Logging**: Use structured logging with agent name context

## Database Rules

1. **Read/Write Separation**: 
   - Brain DB: Read `gardener_pending`, Write `gardener_pending`
   - Commerce DB: Read only (`harvester_dealerproduct`)
2. **Transactions**: Use explicit transactions for multi-statement operations
3. **Connection Pooling**: Use async connection pools, not individual connections

## LLM Rules

1. **Model**: Default to `google/gemini-2.5-flash-lite`
2. **Batching**: Group items into batches (default 50) to reduce API calls
3. **Error Handling**: Log LLM errors, don't crash the agent
4. **Cost Tracking**: Router logs to Langfuse automatically

## Security Rules

1. **No Secrets in Code**: All credentials via environment variables
2. **ContextToken**: Use TokenBuilder for permission validation (when implemented)
3. **Least Privilege**: Worker should only have permissions it needs

## Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Agent name | lowercase_underscore | `gardener` |
| Agent class | PascalCaseAgent | `GardenerAgent` |
| Config class | PascalCaseConfig | `GardenerConfig` |
| Env variable | UPPERCASE_UNDERSCORE | `GARDENER_BATCH_SIZE` |
