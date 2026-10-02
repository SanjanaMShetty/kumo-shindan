"""HTTP request and Alertmanager payload models."""

from pydantic import BaseModel, Field


class InvestigateRequest(BaseModel):
    namespace: str = Field(min_length=1, max_length=63)
    symptom: str = Field(min_length=5, max_length=1000)


class Alert(BaseModel):
    status: str = "firing"
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    fingerprint: str | None = None


class AlertmanagerPayload(BaseModel):
    status: str = "firing"
    alerts: list[Alert] = Field(default_factory=list)
