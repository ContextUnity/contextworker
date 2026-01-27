---
name: gardener_agent
description: AI agent for taxonomy classification of e-commerce products
---

# Gardener Agent Skill

## Purpose

The Gardener Agent enriches products with taxonomy, NER extraction, parameters, and technology detection using LLM. Updates results directly on `DealerProduct.enrichment` JSON field.

## Architecture (Current - 2026-01)

```
┌──────────────────────┐     ┌──────────────────────┐     ┌───────────────────┐
│  DealerProduct       │────▶│  Gardener Graph      │────▶│  DealerProduct    │
│  status=raw          │     │  (ContextRouter)     │     │  enrichment={}    │
│  enrichment.*.status │     └─────────┬────────────┘     └───────────────────┘
│       = pending      │               │
└──────────────────────┘               │
                                       ▼
                              ┌────────────────────┐
                              │  Knowledge Edges   │
                              │  (Brain DB)        │
                              └────────────────────┘
```

**Key Change from Legacy**: No longer uses `gardener_pending` queue. Enrichment status tracked per-task in `DealerProduct.enrichment` JSON field.

## Implementation Location

**Main file:** `contextrouter/src/contextrouter/cortex/graphs/gardener.py` (753 lines)

## Enrichment Tasks

| Task | Status | Description |
|------|--------|-------------|
| taxonomy | ✅ Done | category, color, size normalization |
| ner | ✅ Done | short_name, product_type, brand, model |
| params | ✅ Done | structured parameters extraction |
| tech | ✅ Done | technology extraction (Gore-Tex, Vibram) |
| kg | ✅ Done | Knowledge Graph relations |

## Data Model

**DealerProduct.enrichment** (JSON field):
```json
{
  "taxonomy": {"status": "done", "result": {"category": "outdoor.jackets", "color": "navy"}, "tokens": 50, "at": "..."},
  "ner": {"status": "done", "result": {"product_type": "Куртка", "brand": "Arcteryx", "model": "Beta AR"}, "tokens": 80},
  "params": {"status": "done", "result": {"material": "Gore-Tex", "weight_g": 450}},
  "tech": {"status": "done", "result": [{"name": "Gore-Tex Pro", "type": "membrane"}]},
  "kg": {"status": "done", "relations": [{"type": "USES", "target": "tech:gore-tex"}]}
}
```

**Status values**: `pending` | `done` | `error`

## LangGraph Flow

```python
class GardenerState(TypedDict):
    batch_size: int
    db_url: str
    tenant_id: str
    products: List[Product]
    taxonomy_results: List[EnrichmentResult]
    ner_results: List[EnrichmentResult]
    params_results: List[EnrichmentResult]
    tech_results: List[EnrichmentResult]
    kg_results: List[EnrichmentResult]
    total_tokens: int

# Graph flow
START → fetch_pending → classify_taxonomy → extract_ner → extract_params → extract_tech → update_kg → write_results → END
```

## Invocation

**As library (preferred):**
```python
from contextrouter.cortex.graphs.gardener import invoke_gardener, GardenerConfig

result = await invoke_gardener(
    config=GardenerConfig(
        db_url=os.environ["DATABASE_URL"],
        tenant_id="traverse",
        batch_size=50,
    )
)
# Returns: GardenerResult(products_updated=50, total_tokens=2500, duration_ms=3200)
```

**Via Worker scheduler:**
```python
# contextworker/harvester/scheduler.py triggers gardener on completion
```

## Database Access

Gardener uses **direct DB access** (not gRPC):
```python
async with await psycopg.AsyncConnection.connect(db_url) as conn:
    # Query harvester_dealer_product
    # Update enrichment field
    # Write to knowledge_edges
```

## Prompts

Located in `contextrouter/src/contextrouter/cortex/prompting/`:
- `gardener_taxonomy.txt`
- `gardener_ner.txt`
- `gardener_params.txt`
- `gardener_tech.txt`

## Monitoring

- **Langfuse**: LLM calls tracked automatically via Router
- **Logs**: `contextrouter.cortex.graphs.gardener`
- **Metrics**: `products_updated`, `total_tokens`, `duration_ms`

## Legacy (Deprecated)

The following are **deprecated** but may exist in DB:
- `gardener_pending` table (Migration 0002) - replaced by `DealerProduct.enrichment`
- `GardenerAgent` in `contextworker/agents/` - replaced by Router graph

