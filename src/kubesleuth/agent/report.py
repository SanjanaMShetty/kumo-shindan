"""Structured output for an incident investigation."""

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "MISSING_ENV_VAR",
    "MISSING_CONFIG_RESOURCE",
    "IMAGE_PULL",
    "OOM_KILLED",
    "APPLICATION_CRASH",
    "INSUFFICIENT_RESOURCES",
    "SCHEDULING_CONSTRAINT",
    "STORAGE",
    "SERVICE_SELECTOR",
    "READINESS_PROBE",
    "LIVENESS_PROBE",
    "NO_ISSUE_FOUND",
    "UNKNOWN",
]


class IncidentReport(BaseModel):
    category: Category = Field(
        description="Classify the underlying cause, not just the symptom. Use MISSING_ENV_VAR when evidence explicitly says a required variable is unset; use APPLICATION_CRASH only when no more specific cause is supported."
    )
    root_cause: str = Field(description="One or two sentences stating the likely root cause.")
    evidence: list[str] = Field(description="Specific facts taken from Kubernetes tool output.")
    suggested_fix: str = Field(description="A human-reviewed fix, in plain language.")
    fix_commands: list[str] = Field(
        default_factory=list,
        description="Optional commands for a human to review. Never execute them.",
    )
    prevention: str = Field(description="How to reduce the chance of this failure recurring.")
    confidence: Literal["high", "medium", "low"]
    confidence_reason: str = Field(description="Why this confidence level is appropriate.")
