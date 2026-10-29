"""Start the worker Container Apps Job right away ("Process now").

Calls the Azure management API  POST .../providers/Microsoft.App/jobs/<name>/start  with a token of the
API's managed identity. That identity may only start this one job (custom role "AR Worker Job Starter",
assigned on the job resource - see infra/main.bicep). Nothing here runs on the laptop.
"""
import json
import urllib.error
import urllib.request

from app.config import get_settings

ARM = "https://management.azure.com"
API_VERSION = "2024-03-01"


class WorkerJobUnavailable(RuntimeError):
    """Not running in Azure (or not configured): there is no job to start."""


class WorkerJobStartFailed(RuntimeError):
    pass


def configured() -> bool:
    s = get_settings()
    return bool(s.azure_subscription_id and s.azure_resource_group and s.worker_job_name)


def _token() -> str:
    from azure.identity import ManagedIdentityCredential

    s = get_settings()
    return ManagedIdentityCredential(client_id=s.azure_client_id or None).get_token(f"{ARM}/.default").token


def start_worker_job(timeout_s: float = 20) -> str:
    """Start one execution of the worker job. Returns the execution name Azure gives it."""
    s = get_settings()
    if not configured():
        raise WorkerJobUnavailable("No Azure worker job is configured here (AZURE_SUBSCRIPTION_ID, "
                                   "AZURE_RESOURCE_GROUP, WORKER_JOB_NAME). On the laptop run: python -m app.worker --once")
    url = (f"{ARM}/subscriptions/{s.azure_subscription_id}/resourceGroups/{s.azure_resource_group}"
           f"/providers/Microsoft.App/jobs/{s.worker_job_name}/start?api-version={API_VERSION}")
    try:
        req = urllib.request.Request(url, data=b"{}", method="POST",
                                     headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # 200 / 202
            body = resp.read()
    except urllib.error.HTTPError as exc:
        raise WorkerJobStartFailed(f"Azure refused to start the job (HTTP {exc.code})") from exc
    except Exception as exc:
        raise WorkerJobStartFailed(f"Could not start the job: {type(exc).__name__}") from exc
    try:
        return json.loads(body).get("name") or "started" if body else "started"
    except ValueError:
        return "started"
