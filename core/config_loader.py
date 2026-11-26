"""Configuration loader supporting JSON settings and optional environment overrides."""

import json
import os
from pathlib import Path
from typing import Any


def load_settings(config_path: str | Path = "config/settings.json") -> dict[str, Any]:
    """Load settings from JSON and apply optional STRIVER_* environment overrides."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        settings: dict[str, Any] = json.load(fh)

    env_base_url = os.getenv("STRIVER_BASE_URL")
    if env_base_url:
        settings.setdefault("site", {})["base_url"] = env_base_url.rstrip("/")

    env_headless = os.getenv("STRIVER_HEADLESS")
    if env_headless is not None:
        settings.setdefault("browser", {})["headless"] = env_headless.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    env_timeout = os.getenv("STRIVER_TIMEOUT_MS")
    if env_timeout:
        settings.setdefault("browser", {})["timeout_ms"] = int(env_timeout)

    env_delay = os.getenv("STRIVER_REQUEST_DELAY_SECONDS")
    if env_delay:
        settings.setdefault("scraping", {})["request_delay_seconds"] = float(env_delay)

    env_log_level = os.getenv("STRIVER_LOG_LEVEL")
    if env_log_level:
        settings.setdefault("logging", {})["level"] = env_log_level.upper()

    env_output_dir = os.getenv("STRIVER_OUTPUT_DIR")
    if env_output_dir:
        base = Path(env_output_dir)
        settings.setdefault("output", {})["base_dir"] = str(base)
        settings["output"]["excel_dir"] = str(base / "Excel")
        settings["output"]["pdf_dir"] = str(base / "PDF")

    return settings
