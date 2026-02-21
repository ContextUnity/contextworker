"""Local computation management for Worker."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class LocalComputeManager:
    """Manages local computation resources in Worker."""

    def __init__(self):
        self._available_models: Dict[str, bool] = {}
        self._model_clients: Dict[str, Any] = {}
        self._checked = False

    async def check_local_models(self) -> Dict[str, bool]:
        """Check which local models are available."""
        if self._checked:
            return self._available_models

        models = {
            "local/llama3.2": await self._check_ollama("llama3.2"),
            "local-vllm/llama": await self._check_vllm(),
            "rlm/gpt-5-mini": await self._check_rlm(),
        }

        self._available_models.update(models)
        self._checked = True

        logger.info(f"Local models available: {[k for k, v in models.items() if v]}")

        return models

    async def _check_ollama(self, model_name: str) -> bool:
        """Check if Ollama model is available."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://localhost:11434/api/tags",
                    timeout=2.0,
                )
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    return any(m.get("name", "").startswith(model_name) for m in models)
        except Exception:
            pass
        return False

    async def _check_vllm(self) -> bool:
        """Check if vLLM server is available."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://localhost:8000/health",
                    timeout=2.0,
                )
                return response.status_code == 200
        except Exception:
            pass
        return False

    async def _check_rlm(self) -> bool:
        """Check if RLM is available."""
        import importlib.util

        return importlib.util.find_spec("rlm") is not None

    async def get_local_model(
        self,
        model_key: str,
        config: Dict[str, Any],
    ) -> Any:
        """Get local model instance if available.

        Args:
            model_key: Model key (e.g., "local/llama3.2", "rlm/gpt-5-mini")
            config: Model configuration

        Returns:
            Model instance

        Raises:
            ValueError: If model is not available
        """
        # Check availability
        await self.check_local_models()

        if not self._available_models.get(model_key, False):
            raise ValueError(f"Local model {model_key} not available")

        # Return cached instance if available
        if model_key in self._model_clients:
            return self._model_clients[model_key]

        # Create new instance
        if model_key.startswith("local/") or model_key.startswith("local-vllm/"):
            from contextrouter.modules.models import model_registry

            model = model_registry.create_llm(
                model_key,
                config=config,
            )
            self._model_clients[model_key] = model
            return model

        elif model_key.startswith("rlm/"):
            from contextrouter.modules.models import model_registry

            # Extract base model from rlm/model_name
            model = model_registry.create_llm(
                model_key,
                config=config,
                environment="local",  # Use local RLM environment
            )
            self._model_clients[model_key] = model
            return model

        else:
            raise ValueError(f"Unknown local model key: {model_key}")

    def is_local_model_available(self, model_key: str) -> bool:
        """Check if a local model is available (synchronous check)."""
        return self._available_models.get(model_key, False)
