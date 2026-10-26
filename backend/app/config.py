"""Application settings.

Every setting is read from environment variables, or from the `.env` file in the
project root. Nothing secret is ever written in code. In Azure, the same names
are supplied by Key Vault / Container Apps settings, so the code never changes
between the laptop and the cloud.
"""
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General -------------------------------------------------------------
    app_name: str = "AR Remittance & PTP Control Tower"
    environment: str = "local"  # local | demo | prod

    # --- Database ------------------------------------------------------------
    database_url: str = "postgresql+psycopg://ar_app:CHANGE_ME@localhost:5432/ar_demo"

    # --- Demo business date ----------------------------------------------------
    # All business rules (due dates, PTP kept/broken, date scoring) use this date,
    # not the real calendar, so a demo looks the same on any day.
    business_date: date = date(2026, 10, 28)

    # --- Gmail (used from Day 3) ----------------------------------------------
    gmail_address: str = "processintelligence1@gmail.com"
    gmail_client_secret_file: str = ""
    gmail_token_file: str = ""

    # --- Outbound e-mail safety -------------------------------------------------
    # "redirect" = every outgoing e-mail goes to OUTBOUND_REDIRECT_TO only.
    outbound_mode: str = "redirect"
    outbound_redirect_to: str = "processintelligence1@gmail.com"

    # --- File storage ----------------------------------------------------------
    storage_backend: str = "local"  # local | azure_blob
    storage_local_root: str = str(PROJECT_ROOT / "data" / "runtime")

    # --- OCR -------------------------------------------------------------------
    ocr_engine: str = "tesseract"  # tesseract | azure_di
    tesseract_cmd: str = ""

    # --- Front-end origin allowed to call the API (CORS) -------------------------
    cors_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
