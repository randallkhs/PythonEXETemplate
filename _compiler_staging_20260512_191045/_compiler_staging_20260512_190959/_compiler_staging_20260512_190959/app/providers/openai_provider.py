"""OpenAI image generation/editing provider."""

from __future__ import annotations

import base64
from pathlib import Path

import requests

from .base import GeneratedImage, ProviderError


OPENAI_IMAGE_MODEL = "gpt-image-2"
OPENAI_BASE_URL = "https://api.openai.com/v1"


class OpenAIImageProvider:
    provider_name = "openai"
    model_name = OPENAI_IMAGE_MODEL

    def validate_key(self, api_key: str, timeout_seconds: int = 20) -> None:
        if not api_key.strip():
            raise ProviderError("OpenAI API key is empty.")

        response = requests.get(
            f"{OPENAI_BASE_URL}/models/{self.model_name}",
            headers={"Authorization": f"Bearer {api_key.strip()}"},
            timeout=timeout_seconds,
        )
        if response.status_code != 200:
            message = self._extract_error_message(response)
            raise ProviderError(f"OpenAI key validation failed: {message}")

    def generate_from_reference(
        self,
        *,
        api_key: str,
        reference_image: Path,
        prompt: str,
        size: str,
        quality: str,
        timeout_seconds: int = 180,
    ) -> GeneratedImage:
        if not reference_image.exists():
            raise ProviderError("Reference image file was not found.")

        try:
            with reference_image.open("rb") as image_file:
                response = requests.post(
                    f"{OPENAI_BASE_URL}/images/edits",
                    headers={"Authorization": f"Bearer {api_key.strip()}"},
                    files={"image": (reference_image.name, image_file)},
                    data={
                        "model": self.model_name,
                        "prompt": prompt,
                        "size": size,
                        "quality": quality,
                    },
                    timeout=timeout_seconds,
                )
        except requests.RequestException as exc:
            raise ProviderError(f"OpenAI request failed: {exc}") from exc

        if response.status_code != 200:
            message = self._extract_error_message(response)
            raise ProviderError(f"OpenAI generation failed: {message}")

        payload = response.json()
        data = payload.get("data")
        if not isinstance(data, list) or not data:
            raise ProviderError("OpenAI response did not include generated image data.")

        first = data[0]
        if not isinstance(first, dict):
            raise ProviderError("OpenAI response image payload is invalid.")

        b64_value = first.get("b64_json")
        if not isinstance(b64_value, str) or not b64_value:
            raise ProviderError("OpenAI response did not contain b64_json.")

        try:
            image_bytes = base64.b64decode(b64_value)
        except (ValueError, TypeError) as exc:
            raise ProviderError("OpenAI image payload could not be decoded.") from exc

        return GeneratedImage(
            image_bytes=image_bytes,
            mime_type="image/png",
            provider=self.provider_name,
            model=self.model_name,
        )

    def _extract_error_message(self, response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"HTTP {response.status_code}"
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
        return f"HTTP {response.status_code}"
