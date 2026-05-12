"""Shared provider models and errors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GeneratedImage:
    image_bytes: bytes
    mime_type: str
    provider: str
    model: str


class ProviderError(RuntimeError):
    """Raised when provider generation fails."""
