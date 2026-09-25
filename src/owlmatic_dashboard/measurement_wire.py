"""Export-safe v2 measurements: aggregates always, workflow identities only by consent."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Assessment(Contract):
    workflow_ref: str
    method: Literal["observed-history-v1"] = "observed-history-v1"
    observed_tasks: int
    measured_tasks: int
    baseline_samples: int
    baseline_min_tokens: int | None = None
    baseline_max_tokens: int | None = None
    host_models: tuple[str, ...] = ()
    workloads: tuple[str, ...] = ()
    measured_agent_tokens: int | None = None
    estimated_operational_savings: int | None = None
    estimated_net_savings: int | None = None
    estimated_context_reference_tokens: int | None = None
    context_bytes_reduced: int | None = None
    creation_tokens: int | None = None
    maintenance_tokens: int | None = None
    quality: Literal["unmeasured", "partial", "preliminary"]
    issues: tuple[str, ...]
    latest_observation_at: str | None = None
    comparison: Literal["recorded_manual_tasks"] = "recorded_manual_tasks"


class MeasurementMetrics(Contract):
    scope: Literal["retained_measurement_history"] = "retained_measurement_history"
    observed_tasks: int = Field(ge=0)
    measured_tasks: int = Field(ge=0)
    unattributed_tasks: int = Field(ge=0)
    measured_agent_tokens: int | None = Field(default=None, ge=0)
    estimated_operational_savings: int | None = None
    estimated_net_savings: int | None = None
    estimated_context_reference_tokens: int | None = None
    context_bytes_reduced: int | None = None
    latest_observation_at: str | None = None
    workflows: tuple[Assessment, ...] | None = None
    method: Literal["observed-history-v1"] = "observed-history-v1"
    note: str = "Historical comparison, not a guaranteed minimum; reference tokens are not provider billing"
