"""FastAPI application - the single entry point for the API.

Run locally:   uvicorn app.main:app --reload
Then open:     http://127.0.0.1:8000/docs   (interactive API test page)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import emails, reference, system, auth, dashboard, workitems
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Backend for AR Remittance & Promise-to-Pay processing: e-mail ingestion, "
        "document reading, BSID matching, workflow and audit."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(reference.router)
app.include_router(emails.router)
app.include_router(emails.admin)
app.include_router(auth.router)
app.include_router(workitems.router)
app.include_router(dashboard.router)
