"""Credential management for harness model clients."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class CredentialService:
    """Keyring-first API key storage with a plaintext `.env` fallback warning."""

    ENV_KEY_NAMES = {"HARNESS_API_KEY", "OPENAI_API_KEY"}

    def __init__(
        self,
        *,
        keyring_backend: Any | None = None,
        provider: str = "openai-compatible",
        service_name: str = "context-aware-harness",
        username: str = "openai-compatible-api-key",
        env_file: str | Path | None = None,
    ) -> None:
        self.provider = provider
        self.service_name = service_name
        self.username = username
        self.env_file = Path(env_file) if env_file is not None else Path(".env")
        if keyring_backend is None:
            try:
                import keyring as keyring_backend  # type: ignore[no-redef]
            except ImportError:
                keyring_backend = None
        self.keyring = keyring_backend

    def set(self, api_key: str) -> None:
        if self.keyring is None:
            raise RuntimeError("keyring backend is unavailable")
        self.keyring.set_password(self.service_name, self.username, api_key)

    def clear(self) -> bool:
        if self.keyring is None:
            return False
        try:
            if self.keyring.get_password(self.service_name, self.username) is None:
                return False
            self.keyring.delete_password(self.service_name, self.username)
        except Exception:
            return False
        return True

    def status(self) -> dict[str, object]:
        if self.keyring is not None:
            try:
                if self.keyring.get_password(self.service_name, self.username):
                    return self._status(True, "keyring", None)
            except Exception:
                return self._status(False, "keyring", "Keyring backend unavailable.")

        if self._env_has_key():
            return self._status(
                True,
                ".env",
                "Plaintext development fallback; move the key to keyring for normal use.",
            )

        return self._status(False, None, None)

    def _status(self, configured: bool, source: str | None, risk: str | None) -> dict[str, object]:
        return {
            "configured": configured,
            "provider": self.provider,
            "source": source,
            "risk": risk,
        }

    def _env_has_key(self) -> bool:
        if not self.env_file.exists():
            return False
        for line in self.env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            name = name.strip().removeprefix("export ").strip()
            value = value.strip().strip("\"'")
            if name in self.ENV_KEY_NAMES and value:
                return True
        return False
