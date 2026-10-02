"""FastAPI service for manual and Alertmanager-triggered investigations."""

import hmac
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException

from kubesleuth import notify, storage
from kubesleuth.agent.graph import investigate
from kubesleuth.api.schemas import AlertmanagerPayload, InvestigateRequest
from kubesleuth.config import settings

log = logging.getLogger("kubesleuth.api")

_slots = threading.BoundedSemaphore(settings.max_concurrent_investigations)
_last_seen: dict[str, float] = {}
_last_seen_lock = threading.Lock()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    storage.init_db()
    yield


app = FastAPI(
    title="KubeSleuth",
    description="Read-only AI-assisted Kubernetes incident investigations.",
    version="0.1.0",
    lifespan=lifespan,
)


def _namespace_error(namespace: str) -> str | None:
    if namespace not in settings.namespaces:
        return (
            f"Namespace {namespace!r} is not allowed. "
            f"Allowed namespaces: {', '.join(settings.namespaces) or '(none)'}"
        )
    return None


def _in_cooldown(key: str) -> bool:
    now = time.monotonic()
    with _last_seen_lock:
        previous = _last_seen.get(key)
        if previous is not None and now - previous < settings.alert_cooldown_seconds:
            return True
        _last_seen[key] = now
        return False


def _run_investigation(investigation_id: str, namespace: str, symptom: str) -> None:
    try:
        with _slots:
            storage.mark_running(investigation_id)
            result = investigate(namespace, symptom)
            storage.finish(investigation_id, result)

        if result.report:
            notify.post_to_slack(namespace, symptom, result.report)
        else:
            log.error("Investigation %s failed: %s", investigation_id, result.error)
    except Exception:
        log.exception("Investigation %s could not be completed", investigation_id)


def _enqueue(
    source: str,
    namespace: str,
    symptom: str,
    background: BackgroundTasks,
) -> str:
    investigation_id = storage.create(source, namespace, symptom)
    background.add_task(_run_investigation, investigation_id, namespace, symptom)
    return investigation_id


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/investigate", status_code=202)
def start_investigation(
    request: InvestigateRequest,
    background: BackgroundTasks,
) -> dict:
    error = _namespace_error(request.namespace)
    if error:
        raise HTTPException(status_code=400, detail=error)

    investigation_id = _enqueue(
        "manual",
        request.namespace,
        request.symptom,
        background,
    )
    return {"id": investigation_id, "status": "queued"}


@app.post("/webhook/alertmanager")
def alertmanager_webhook(
    payload: AlertmanagerPayload,
    background: BackgroundTasks,
    x_webhook_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    expected_token = settings.webhook_token
    if expected_token:
        bearer_token = (
            authorization.removeprefix("Bearer ").strip()
            if authorization and authorization.startswith("Bearer ")
            else None
        )
        supplied_token = x_webhook_token or bearer_token
        if not supplied_token or not hmac.compare_digest(supplied_token, expected_token):
            raise HTTPException(status_code=401, detail="invalid webhook token")

    accepted: list[str] = []
    skipped = 0

    for alert in payload.alerts:
        namespace = alert.labels.get("namespace", "")
        alertname = alert.labels.get("alertname", "unknown")

        if (
            alert.status != "firing"
            or not namespace
            or _namespace_error(namespace)
            or _in_cooldown(f"{alertname}/{namespace}")
        ):
            skipped += 1
            continue

        detail = alert.annotations.get("summary") or alert.annotations.get("description") or ""
        symptom = f"Alert {alertname} is firing in namespace {namespace}. {detail}".strip()
        investigation_id = _enqueue("alertmanager", namespace, symptom, background)
        accepted.append(investigation_id)

    return {"accepted": accepted, "skipped": skipped}


@app.get("/investigations")
def list_investigations(limit: int = 20) -> list[dict]:
    return storage.list_recent(max(1, min(limit, 100)))


@app.get("/investigations/{investigation_id}")
def get_investigation(investigation_id: str) -> dict:
    investigation = storage.get(investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="investigation not found")
    return investigation
