"""Per-user application configuration."""

from __future__ import annotations

from pathlib import Path
import os
import shutil

from dotenv import dotenv_values, set_key


def app_data_dir() -> Path:
    root = os.getenv("LOCALAPPDATA")
    path = Path(root) / "AI Gmail Organizer" if root else Path.home() / ".ai-gmail-organizer"
    path.mkdir(parents=True, exist_ok=True)
    return path


CONFIG_DIR = app_data_dir()
ENV_FILE = CONFIG_DIR / ".env"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"


def read_config() -> dict[str, str]:
    values = dotenv_values(ENV_FILE)
    return {key: value or "" for key, value in values.items() if key}


def save_api_key(api_key: str) -> None:
    set_key(str(ENV_FILE), "OPENAI_API_KEY", api_key.strip())


def save_model(model: str) -> None:
    set_key(str(ENV_FILE), "OPENAI_MODEL", model.strip())


def save_base_url(base_url: str) -> None:
    set_key(str(ENV_FILE), "OPENAI_BASE_URL", base_url.strip().rstrip("/"))


def save_provider_name(provider: str) -> None:
    set_key(str(ENV_FILE), "AI_PROVIDER", provider.strip())


def install_google_credentials(source: str | Path) -> Path:
    source_path = Path(source)
    if not source_path.exists() or source_path.suffix.lower() != ".json":
        raise ValueError("Select a valid Google OAuth JSON file.")
    shutil.copy2(source_path, CREDENTIALS_FILE)
    return CREDENTIALS_FILE
