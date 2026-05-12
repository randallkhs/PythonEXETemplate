"""Background worker and data contracts for image generation tasks."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from .config import AppConfig
from .key_store import KeyStoreError, load_api_key
from .providers import GeminiImageProvider, OpenAIImageProvider
from .providers.base import ProviderError


@dataclass(frozen=True)
class GenerationRequest:
    provider: str
    prompt: str
    reference_image: Path
    output_dir: Path
    output_name: str
    size: str
    quality: str


@dataclass(frozen=True)
class GenerationResult:
    output_path: Path
    provider: str
    model: str
    elapsed_seconds: float


class GenerationWorker(QObject):
    """Runs image generation in a worker thread."""

    progress = Signal(dict)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, request: GenerationRequest, config: AppConfig) -> None:
        super().__init__()
        self.request = request
        self.config = config
        self._providers = {
            "openai": OpenAIImageProvider(),
            "gemini": GeminiImageProvider(),
        }

    @Slot()
    def run(self) -> None:
        try:
            start_time = time.monotonic()
            self._emit_progress(10, "Validating request...", stage="validate")
            self._validate_request()

            self._emit_progress(20, "Loading secure API key...", stage="load_key")
            api_key = load_api_key(self.request.provider)
            if not api_key:
                raise ProviderError(f"No API key saved for {self.request.provider}.")

            provider = self._providers[self.request.provider]
            expected_seconds = self.config.get_provider_avg_seconds(self.request.provider)
            network_started = time.monotonic()
            self._emit_progress(
                30,
                f"Generating image with {provider.model_name}...",
                stage="network_wait",
                network_started=network_started,
                network_expected=expected_seconds,
            )

            generated = provider.generate_from_reference(
                api_key=api_key,
                reference_image=self.request.reference_image,
                prompt=self.request.prompt,
                size=self.request.size,
                quality=self.request.quality,
            )

            self._emit_progress(85, "Saving generated image...", stage="save")
            output_path = self._save_output(generated.image_bytes, generated.mime_type)

            elapsed = time.monotonic() - start_time
            self.config.update_provider_avg_seconds(self.request.provider, elapsed)
            self.config.set_last_output_dir(self.request.output_dir)

            self._emit_progress(100, "Completed.", stage="done")
            self.finished.emit(
                GenerationResult(
                    output_path=output_path,
                    provider=generated.provider,
                    model=generated.model,
                    elapsed_seconds=elapsed,
                )
            )
        except (ProviderError, KeyStoreError, OSError, ValueError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - surface safe generic error to UI
            self.failed.emit(f"Unexpected error: {exc}")

    def _validate_request(self) -> None:
        if self.request.provider not in self._providers:
            raise ValueError("Invalid provider selected.")
        if not self.request.reference_image.exists():
            raise ValueError("Reference image file does not exist.")
        if not self.request.prompt.strip():
            raise ValueError("Prompt is required.")
        if not self.request.output_dir.exists():
            self.request.output_dir.mkdir(parents=True, exist_ok=True)

    def _save_output(self, image_bytes: bytes, mime_type: str) -> Path:
        extension = ".png"
        if mime_type == "image/jpeg":
            extension = ".jpg"
        elif mime_type == "image/webp":
            extension = ".webp"

        output_name = self.request.output_name.strip()
        if not output_name:
            timestamp = int(time.time())
            output_name = f"{self.request.provider}_generated_{timestamp}"

        if not output_name.lower().endswith(extension):
            output_name = f"{output_name}{extension}"

        output_path = (self.request.output_dir / output_name).resolve()
        output_path.write_bytes(image_bytes)
        return output_path

    def _emit_progress(self, percent: int, message: str, **extra: object) -> None:
        payload = {"percent": percent, "message": message}
        payload.update(extra)
        self.progress.emit(payload)
