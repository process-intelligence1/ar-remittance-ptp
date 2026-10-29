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

    # --- Gmail ------------------------------------------------------------------
    gmail_address: str = "processintelligence1@gmail.com"
    gmail_client_secret_file: str = ""  # laptop only: OAuth Desktop client (used by scripts.gmail_auth)
    gmail_token_file: str = ""          # laptop: token written by scripts.gmail_auth
    gmail_token_json: str = ""          # Azure: the same token content, injected from Key Vault
    gmail_processed_label: str = "AR-Processed"
    gmail_outbound_label: str = "AR-Outbound"
    gmail_ignored_label: str = "AR-Ignored"  # system senders (rule "ignored_senders"): not stored
    gmail_max_per_poll: int = 100
    # Laptop and Azure read the SAME inbox, so only one may poll: true in Azure only (set by Bicep).
    poller_enabled: bool = False

    # --- Admin endpoints (/api/admin/*) ------------------------------------------
    # Callers send header X-Admin-Key. Empty = admin endpoints switched off. Azure: from Key Vault.
    admin_api_key: str = ""

    # --- Sample e-mails (data/samples/emails/<CODE>/) ----------------------------
    samples_root: str = str(PROJECT_ROOT / "data" / "samples" / "emails")

    # --- Outbound e-mail safety -------------------------------------------------
    # "redirect" = every outgoing e-mail goes to OUTBOUND_REDIRECT_TO only.
    outbound_mode: str = "redirect"
    outbound_redirect_to: str = "processintelligence1@gmail.com"

    # --- File storage ----------------------------------------------------------
    storage_backend: str = "local"  # local | azure_blob
    storage_local_root: str = str(PROJECT_ROOT / "data" / "runtime")
    azure_storage_account_url: str = ""  # e.g. https://<account>.blob.core.windows.net
    azure_storage_container: str = "ar-files"
    azure_client_id: str = ""  # client id of the managed identity used for Blob access (Azure only)

    # --- Document reading / OCR (M02) --------------------------------------------
    ocr_engine: str = "tesseract"  # tesseract | azure_di (Document Intelligence F0 - off by default)
    tesseract_cmd: str = ""        # laptop: path to tesseract.exe; container: on PATH
    doc_timeout_s: int = 120       # per document; then FAILED "timeout"
    ocr_dpi: int = 300             # scanned PDF pages are rendered at this resolution
    ocr_max_side_px: int = 4000    # larger images are scaled down first (memory)
    pdf_max_pages: int = 50        # pages read per PDF (the rest is noted as skipped)
    html_max_bytes: int = 2_000_000  # HTML attachments larger than this are not parsed
    azure_di_endpoint: str = ""    # only used when OCR_ENGINE=azure_di
    azure_di_key: str = ""

    # --- Worker job (M06) -----------------------------------------------------------
    # Set by Bicep in Azure. "Process now" starts this Container Apps Job through the Azure management API
    # with the API's managed identity (custom role that can start only this job). Empty = not in Azure.
    azure_subscription_id: str = ""
    azure_resource_group: str = ""
    worker_job_name: str = ""
    worker_time_budget_s: int = 180  # the worker starts no new e-mail after this many seconds

    # --- Demo login (M07) --------------------------------------------------------------
    # Presenters type DEMO_ACCESS_CODE; the API then issues a signed token (JWT_SECRET). Azure: both from Key Vault.
    # Empty = login switched off (no token, no data).
    demo_access_code: str = ""
    jwt_secret: str = ""
    token_hours: float = 10        # token lifetime; afterwards 401
    file_url_ttl_s: int = 300      # signed attachment download links
    login_max_attempts: int = 10   # per IP and window; then locked out
    login_window_s: int = 60
    login_lockout_s: int = 120

    # --- Front-end origin allowed to call the API (CORS) -------------------------
    cors_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
