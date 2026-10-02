"""Optional Slack notifications for completed investigations."""

import logging

import httpx

from kubesleuth.agent.report import IncidentReport
from kubesleuth.config import settings

log = logging.getLogger(__name__)


def post_to_slack(namespace: str, symptom: str, report: IncidentReport) -> None:
    if not settings.slack_webhook_url:
        return

    text = (
        f":mag: *KubeSleuth investigation* (namespace `{namespace}`)\n"
        f"*Symptom:* {symptom}\n"
        f"*Category:* `{report.category}`  *Confidence:* {report.confidence}\n"
        f"*Root cause:* {report.root_cause}\n"
        f"*Suggested fix:* {report.suggested_fix}"
    )
    try:
        httpx.post(
            settings.slack_webhook_url,
            json={"text": text},
            timeout=10,
        ).raise_for_status()
    except Exception:
        log.exception("Slack notification failed")
