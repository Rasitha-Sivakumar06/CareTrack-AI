from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class HealthRadarMetric(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    unit: str
    baseline_value: Optional[float] = None
    baseline_date: Optional[str] = None
    current_value: Optional[float] = None
    current_date: Optional[str] = None
    delta: Optional[float] = None
    percent_change: Optional[float] = None

    # Normalized scores (0-100 scale) for Radar visualization
    baseline_score: Optional[float] = None
    current_score: Optional[float] = None

    # Clinical decision-support flags
    alert_level: str = "STABLE"  # HIGH_ATTENTION, MODERATE_ATTENTION, STABLE, DATA_GAP
    status: str = "WITHIN_BASELINE"
    calculation_formula: str
    clinical_reason: str


class HealthRadarSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: int = Field(gt=0)
    patient_name: str
    patient_code: str
    total_visits_recorded: int
    baseline_visit_date: Optional[str] = None
    current_visit_date: Optional[str] = None
    metrics_compared_count: int
    attention_flags_count: int
    data_gaps_count: int
    overall_status: str  # ATTENTION_REQUIRED, MONITORING_RECOMMENDED, STABLE_TRAJECTORY, INSUFFICIENT_HISTORY
    evidence_narrative: str
    clinical_action_suggestions: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "Health Change Radar observations are clinical decision-support indicators, "
        "not medical diagnoses. Results must be reviewed and confirmed by a qualified healthcare professional."
    )


class HealthRadarResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary: HealthRadarSummary
    radar_metrics: list[HealthRadarMetric] = Field(default_factory=list)
