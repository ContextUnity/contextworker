"""
Harvest Orchestrator for Worker.

Orchestrates the Fetch -> Transform -> Brain gRPC flow.
All DB operations go through Brain for security and tenant isolation.

This replaces the Django-based orchestrator in Commerce.
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from .suppliers import load_supplier_config, load_settings, load_all_suppliers

logger = logging.getLogger(__name__)


class HarvestOrchestrator:
    """
    Orchestrates the Fetch -> Transform -> Brain gRPC flow.

    Key differences from Commerce version:
    - ALL DB writes go through Brain gRPC (not direct PostgreSQL)
    - Brain verifies tokens and enforces tenant isolation
    - Uses project-specific fetchers/transformers from projects/{project}/harvester/
    - Designed to run in Worker or as Temporal workflow
    """

    def __init__(
        self,
        supplier_code: str,
        brain_url: str = "localhost:50051",
        tenant_id: str = "traverse",
    ):
        self.supplier_code = supplier_code
        self.brain_url = brain_url
        self.tenant_id = tenant_id
        self.supplier_config = None
        self.settings = None
        self._brain_client = None

    async def _get_brain_client(self):
        """Lazy Brain gRPC client."""
        if self._brain_client is None:
            from contextcore import BrainClient

            self._brain_client = BrainClient(self.brain_url)
        return self._brain_client

    async def run(self) -> Dict[str, Any]:
        """Run harvest for a supplier.

        Returns:
            Dict with results: {fetched, transformed, success, errors}
        """
        # Load configs
        if self.supplier_code != "all":
            self.supplier_config = load_supplier_config(self.supplier_code)
        self.settings = load_settings()

        logger.info(f"Starting harvest for {self.supplier_code}")

        if self.supplier_code == "all":
            return await self._run_all()

        return await self._run_single()

    async def _run_all(self) -> Dict[str, Any]:
        """Run all suppliers."""
        suppliers = load_all_suppliers()
        results = {
            "total_suppliers": len(suppliers),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "suppliers": {},
        }

        for code in suppliers:
            self.supplier_code = code
            self.supplier_config = load_supplier_config(code)
            result = await self._run_single()
            results["suppliers"][code] = result

        results["finished_at"] = datetime.now(timezone.utc).isoformat()
        return results

    async def _run_single(self) -> Dict[str, Any]:
        """Run single supplier."""
        result = {
            "supplier": self.supplier_code,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "fetched": 0,
            "transformed": 0,
            "success": 0,
            "errors": [],
        }

        try:
            # 1. Get fetcher
            fetcher = self._get_fetcher()
            if not fetcher:
                result["errors"].append(f"No fetcher found for {self.supplier_code}")
                return result

            # 2. Fetch raw data
            raw_items = await fetcher.fetch()
            result["fetched"] = len(raw_items)

            # 3. Get transformer
            transformer = self._get_transformer()
            if not transformer:
                result["errors"].append(
                    f"No transformer found for {self.supplier_code}"
                )
                return result

            # 4. Transform and save via Brain gRPC
            success_count = 0
            for raw_item in raw_items:
                try:
                    data = transformer.transform(raw_item)
                    await self._save_product_via_brain(data)
                    success_count += 1
                except Exception as e:
                    result["errors"].append(f"Transform error: {e}")

            result["transformed"] = len(raw_items)
            result["success"] = success_count

        except Exception as e:
            result["errors"].append(f"Harvest error: {e}")
            logger.exception(f"Harvest failed for {self.supplier_code}")

        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"Harvest complete: {result}")
        return result

    def _get_fetcher(self):
        """Get fetcher for this supplier."""
        try:
            # Import from projects/{project}/harvester/fetchers/
            from fetchers import __all__ as fetcher_classes

            fetcher_name = f"{self.supplier_code.title().replace('_', '')}Fetcher"
            for cls_name in fetcher_classes:
                if cls_name.lower() == fetcher_name.lower():
                    module = __import__(
                        f"fetchers.{self.supplier_code}", fromlist=[cls_name]
                    )
                    return getattr(module, cls_name)()
        except ImportError as e:
            logger.warning(f"No fetcher for {self.supplier_code}: {e}")
        return None

    def _get_transformer(self):
        """Get transformer for this supplier."""
        try:
            # Import from projects/{project}/harvester/transformers/
            from transformers import __all__ as transformer_classes

            transformer_name = (
                f"{self.supplier_code.title().replace('_', '')}Transformer"
            )
            for cls_name in transformer_classes:
                if cls_name.lower() == transformer_name.lower():
                    module = __import__(
                        f"transformers.{self.supplier_code}", fromlist=[cls_name]
                    )
                    return getattr(module, cls_name)()
        except ImportError as e:
            logger.warning(f"No transformer for {self.supplier_code}: {e}")
        return None

    async def _save_product_via_brain(self, data: Dict[str, Any]) -> None:
        """Save transformed product via Brain gRPC.

        Brain handles:
        - Token verification
        - Tenant isolation
        - PostgreSQL writes
        """
        brain = await self._get_brain_client()

        sku = data.pop("sku")

        # Upsert dealer product via Brain
        await brain.upsert_dealer_product(
            tenant_id=self.tenant_id,
            dealer_code=self.supplier_code,
            dealer_name=self.supplier_config.name,
            sku=sku,
            name=data.get("name", ""),
            category=data.get("category", ""),
            brand_name=data.get("brand_name", ""),
            quantity=data.get("quantity", 0),
            price_retail=data.get("price_retail"),
            currency=data.get("currency", "UAH"),
            params=data.get("extra_attrs", {}),
            status="raw",
        )

    async def close(self):
        """Close Brain connection."""
        if self._brain_client:
            await self._brain_client.close()
            self._brain_client = None


async def run_harvest(
    supplier_code: str,
    brain_url: str = "localhost:50051",
    tenant_id: str = "traverse",
) -> Dict:
    """Run harvest for a single supplier.

    CLI entry point.
    """
    orchestrator = HarvestOrchestrator(supplier_code, brain_url, tenant_id)
    try:
        return await orchestrator.run()
    finally:
        await orchestrator.close()


async def run_all_harvests(
    brain_url: str = "localhost:50051",
    tenant_id: str = "traverse",
) -> List[Dict]:
    """Run harvest for all configured suppliers."""
    orchestrator = HarvestOrchestrator("all", brain_url, tenant_id)
    try:
        result = await orchestrator.run()
        return result.get("suppliers", {})
    finally:
        await orchestrator.close()
