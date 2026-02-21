"""Sub-Agent Monitor for Worker."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SubAgentMonitor:
    """Monitors sub-agent execution."""

    def __init__(self):
        self._status_store: Dict[str, Dict[str, Any]] = {}

    async def get_status(self, subagent_id: str) -> Dict[str, Any]:
        """Get sub-agent status.

        Args:
            subagent_id: Sub-agent ID

        Returns:
            Status dictionary
        """
        return self._status_store.get(
            subagent_id,
            {
                "status": "unknown",
                "subagent_id": subagent_id,
            },
        )

    async def set_status(
        self,
        subagent_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Set sub-agent status.

        Args:
            subagent_id: Sub-agent ID
            status: Status (running, completed, failed)
            result: Result if completed
            error: Error if failed
        """
        self._status_store[subagent_id] = {
            "status": status,
            "subagent_id": subagent_id,
            "result": result,
            "error": error,
            "updated_at": time.time(),
        }

    async def monitor_subagent(
        self,
        subagent_id: str,
        timeout: int = 300,  # 5 minutes
    ) -> Dict[str, Any]:
        """Monitor sub-agent execution.

        Args:
            subagent_id: Sub-agent ID
            timeout: Timeout in seconds

        Returns:
            Status and result
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            status_info = await self.get_status(subagent_id)
            status = status_info.get("status")

            if status == "completed":
                return {
                    "status": "completed",
                    "result": status_info.get("result"),
                    "subagent_id": subagent_id,
                }

            elif status == "failed":
                return {
                    "status": "failed",
                    "error": status_info.get("error"),
                    "subagent_id": subagent_id,
                }

            elif status == "running":
                # Continue monitoring
                await asyncio.sleep(1)

            else:
                # Unknown status, wait a bit
                await asyncio.sleep(1)

        # Timeout
        await self.set_status(subagent_id, "timeout", error="Sub-agent execution timeout")
        return {
            "status": "timeout",
            "error": "Sub-agent execution timeout",
            "subagent_id": subagent_id,
        }

    async def cancel_subagent(self, subagent_id: str) -> None:
        """Cancel sub-agent execution.

        Args:
            subagent_id: Sub-agent ID
        """
        await self.set_status(subagent_id, "cancelled", error="Sub-agent cancelled")
        logger.info(f"Cancelled sub-agent {subagent_id}")
