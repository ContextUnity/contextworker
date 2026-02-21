"""Data types for sub-agent results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Union

from contextcore import ContextUnit, Modality


class SubAgentDataType(str, Enum):
    """Types of data that sub-agents can produce."""

    TEXT = "text"  # Standard LLM response
    STREAMING_TEXT = "streaming_text"  # Streaming LLM response
    IMAGE = "image"  # Image generation/processing
    VIDEO = "video"  # Video generation/processing
    AUDIO = "audio"  # Audio generation/processing (TTS, STT)
    SPATIAL = "spatial"  # 3D/spatial data
    BINARY = "binary"  # Generic binary data
    JSON = "json"  # Structured JSON response
    CODE = "code"  # Generated code
    FILE = "file"  # File path or reference


@dataclass
class SubAgentResult:
    """Result from sub-agent execution."""

    subagent_id: str
    status: str  # completed, failed, streaming
    data_type: SubAgentDataType
    data: Union[str, bytes, Dict[str, Any], None] = None

    # For streaming
    stream_url: Optional[str] = None
    stream_token: Optional[str] = None

    # For files
    file_path: Optional[str] = None
    file_url: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Modality for ContextUnit
    modality: Modality = Modality.TEXT

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "subagent_id": self.subagent_id,
            "status": self.status,
            "data_type": self.data_type.value,
            "data": self.data,
            "stream_url": self.stream_url,
            "stream_token": self.stream_token,
            "file_path": self.file_path,
            "file_url": self.file_url,
            "metadata": self.metadata,
            "modality": self.modality.value,
        }

    def to_context_unit(self, isolation_context) -> ContextUnit:
        """Convert to ContextUnit for Brain storage."""
        from contextcore import ContextUnit

        payload = {
            "subagent_id": self.subagent_id,
            "status": self.status,
            "data_type": self.data_type.value,
        }

        # Add data based on type
        if self.data_type == SubAgentDataType.TEXT:
            payload["text"] = self.data
        elif self.data_type == SubAgentDataType.JSON:
            payload["json"] = self.data
        elif self.data_type == SubAgentDataType.CODE:
            payload["code"] = self.data
        elif self.data_type == SubAgentDataType.IMAGE:
            payload["image_url"] = self.file_url or self.file_path
            payload["modality"] = "image"
        elif self.data_type == SubAgentDataType.AUDIO:
            payload["audio_url"] = self.file_url or self.file_path
            payload["modality"] = "audio"
        elif self.data_type == SubAgentDataType.VIDEO:
            payload["video_url"] = self.file_url or self.file_path
            payload["modality"] = "video"
        elif self.data_type == SubAgentDataType.STREAMING_TEXT:
            payload["stream_url"] = self.stream_url
            payload["stream_token"] = self.stream_token

        if self.metadata:
            payload["metadata"] = self.metadata

        return ContextUnit(
            payload=payload,
            modality=self.modality,
            provenance=[f"subagent:{self.subagent_id}"],
            trace_id=isolation_context.trace_id,
        )
