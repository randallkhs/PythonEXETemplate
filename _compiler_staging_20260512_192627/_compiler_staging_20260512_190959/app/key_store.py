"""Secure key storage using OS keyring."""

from __future__ import annotations

import keyring
from keyring.errors import KeyringError


SERVICE_NAME = "ACS-AI-Image-Reproducer"


class KeyStoreError(RuntimeError):
    """Raised when keyring operations fail."""


def save_api_key(provider: str, api_key: str) -> None:
    try:
        keyring.set_password(SERVICE_NAME, provider, api_key.strip())
    except KeyringError as exc:
        raise KeyStoreError(f"Failed to save API key for {provider}.") from exc


def load_api_key(provider: str) -> str:
    try:
        value = keyring.get_password(SERVICE_NAME, provider)
    except KeyringError as exc:
        raise KeyStoreError(f"Failed to read API key for {provider}.") from exc
    return value or ""


def has_api_key(provider: str) -> bool:
    return bool(load_api_key(provider))


def clear_api_key(provider: str) -> None:
    try:
        keyring.delete_password(SERVICE_NAME, provider)
    except keyring.errors.PasswordDeleteError:
        return
    except KeyringError as exc:
        raise KeyStoreError(f"Failed to clear API key for {provider}.") from exc
