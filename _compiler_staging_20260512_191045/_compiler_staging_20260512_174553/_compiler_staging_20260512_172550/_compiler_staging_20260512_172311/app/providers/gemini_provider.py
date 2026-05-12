"""Gemini image generation/editing provider."""

from __future__ import annotations

import base64
from pathlib import Path

import requests

from .base import GeneratedImage, ProviderError


GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image-preview"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

SIZE_TO_ASPECT_RATIO = {
    "1024x1024": "1:1",
    "1536x1024": "3:2",
    "1024x1536": "2:3",
    "1920x1080": "16:9",
    "1080x1920": "9:16",
}


class GeminiImageProvider:
    provider_name = "gemini"
    model_name = GEMINI_IMAGE_MODEL

    def validate_key(self, api_key: str, timeout_seconds: int = 20) -> None:
        if not api_key.strip():
            raise ProviderError("Gemini API key is empty.")

        response = requests.get(
            f"{GEMINI_BASE_URL}/models/{self.model_name}",
            headers={"x-goog-api-key": api_key.strip()},
            timeout=timeout_seconds,
        )
        if response.status_code != 200:
            message = self._extract_error_message(response)
            raise ProviderError(f"Gemini key validation failed: {message}")

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

        mime_type = self._detect_mime_type(reference_image)
        image_base64 = base64.b64encode(reference_image.read_bytes()).decode("ascii")
        aspect_ratio = SIZE_TO_ASPECT_RATIO.get(size, "1:1")
        image_size = self._size_to_resolution(quality)

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_base64,
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                # Gemini REST expects image settings under imageConfig.
                "imageConfig": {
                    "aspectRatio": aspect_ratio,
                    "imageSize": image_size,
                },
            },
        }

        try:
            response = requests.post(
                f"{GEMINI_BASE_URL}/models/{self.model_name}:generateContent",
                headers={
                    "x-goog-api-key": api_key.strip(),
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"Gemini request failed: {exc}") from exc

        if response.status_code != 200:
            message = self._extract_error_message(response)
            raise ProviderError(f"Gemini generation failed: {message}")

        data = response.json()
        image_part = self._extract_image_part(data)
        if image_part is None:
            message = self._extract_text(data) or "Gemini response did not include image data."
            raise ProviderError(message)

        raw_data = image_part.get("data")
        output_mime = image_part.get("mime_type") or image_part.get("mimeType") or "image/png"

        if not isinstance(raw_data, str) or not raw_data:
            raise ProviderError("Gemini image payload is empty.")

        try:
            image_bytes = base64.b64decode(raw_data)
        except (ValueError, TypeError) as exc:
            raise ProviderError("Gemini image payload could not be decoded.") from exc

        return GeneratedImage(
            image_bytes=image_bytes,
            mime_type=str(output_mime),
            provider=self.provider_name,
            model=self.model_name,
        )

    def _extract_image_part(self, payload: dict) -> dict | None:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            return None

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict):
                    continue
                if isinstance(part.get("inlineData"), dict):
                    return part["inlineData"]
                if isinstance(part.get("inline_data"), dict):
                    return part["inline_data"]
        return None

    def _extract_text(self, payload: dict) -> str:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            return ""
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    return part["text"].strip()
        return ""

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

    def _size_to_resolution(self, quality: str) -> str:
        quality_value = quality.strip().lower()
        if quality_value == "high":
            return "4K"
        if quality_value == "medium":
            return "2K"
        return "1K"

    def _detect_mime_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".png":
            return "image/png"
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "application/octet-stream"
