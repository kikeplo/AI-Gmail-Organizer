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


def save_backup_api_keys(api_keys: list[str]) -> None:
    """Persist backup API keys as a comma-separated local setting."""
    cleaned = [str(key).strip() for key in api_keys if str(key).strip()]
    set_key(str(ENV_FILE), "OPENAI_API_KEYS", ",".join(cleaned))


def get_api_keys(config: dict[str, str] | None = None) -> list[str]:
    """Return primary + backup API keys in configured order, without duplicates."""
    values = config or read_config()
    result: list[str] = []
    backup_text = values.get("OPENAI_API_KEYS", "")
    raw_backups = [item for chunk in backup_text.splitlines() for item in chunk.split(",")]
    for key in [values.get("OPENAI_API_KEY", ""), *raw_backups]:
        normalized = key.strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def save_model(model: str) -> None:
    set_key(str(ENV_FILE), "OPENAI_MODEL", model.strip())


def save_base_url(base_url: str) -> None:
    set_key(str(ENV_FILE), "OPENAI_BASE_URL", base_url.strip().rstrip("/"))


def save_provider_name(provider: str) -> None:
    set_key(str(ENV_FILE), "AI_PROVIDER", provider.strip())


def save_gmail_client_id(client_id: str) -> None:
    set_key(str(ENV_FILE), "GMAIL_CLIENT_ID", client_id.strip())


def save_local_ai(enabled: bool, base_url: str, model: str) -> None:
    set_key(str(ENV_FILE), "LOCAL_AI_ENABLED", "1" if enabled else "0")
    set_key(str(ENV_FILE), "LOCAL_AI_BASE_URL", base_url.strip().rstrip("/"))
    set_key(str(ENV_FILE), "LOCAL_AI_MODEL", model.strip())


def save_browser_settings(mode: str, cdp_url: str, profile_dir: str) -> None:
    set_key(str(ENV_FILE), "BROWSER_MODE", mode.strip().lower())
    set_key(str(ENV_FILE), "BROWSER_CDP_URL", cdp_url.strip())
    set_key(str(ENV_FILE), "BROWSER_USER_DATA_DIR", profile_dir.strip())


def install_google_credentials(source: str | Path) -> Path:
    source_path = Path(source)
    if not source_path.exists() or source_path.suffix.lower() != ".json":
        raise ValueError("Select a valid Google OAuth JSON file.")
    shutil.copy2(source_path, CREDENTIALS_FILE)
    return CREDENTIALS_FILE
