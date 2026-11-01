from datetime import date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class ReadingPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    visit_id: int
    visit_date: date
    value: Optional[float] = None
    measured_at: Optional[str] = None
    timestamp_warning: Optional[str] = None
    has_multiple_readings: bool = False


class TrajectoryMetric(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    unit: str
    baseline_reading: Optional[ReadingPoint] = None
    previous_reading: Optional[ReadingPoint] = None
    latest_reading: Optional[ReadingPoint] = None
    delta_from_previous: Optional[float] = None
    delta_from_baseline: Optional[float] = None
    percent_change_from_baseline: Optional[float] = None
    classification: str  # CONCERNING_CHANGE, IMPROVING_TREND, STABLE_TREND, MODERATE_SHIFT, DATA_GAP, DATA_INCONSISTENCY
    classification_label: str
    severity_level: str  # high, moderate, normal, info
    formula_breakdown: str
    clinical_explanation: str
    data_quality_note: Optional[str] = None


class HealthTrajectorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: int = Field(gt=0)
    patient_name: str
    patient_code: str
    total_visits_recorded: int
    chronological_span: Optional[str] = None
    baseline_visit_date: Optional[date] = None
    latest_visit_date: Optional[date] = None
    concerning_count: int = 0
    improving_count: int = 0
    stable_count: int = 0
    data_gaps_count: int = 0
    overall_trajectory_status: str  # ATTENTION_REQUIRED, STABILIZING_TRAJECTORY, STABLE_MAINTENANCE, INSUFFICIENT_HISTORY
    factual_trajectory_narrative: str
    clinical_decision_support_notes: List[str] = Field(default_factory=list)
    visit_quality_warnings: List[str] = Field(default_factory=list)


class HealthTrajectoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary: HealthTrajectorySummary
    metrics: List[TrajectoryMetric]
    disclaimer: str = (
        "Clinical decision support only. Not an autonomous diagnosis or clinically validated prediction system. "
        "All trajectory classifications are based strictly on documented historical readings and configured demonstration rules. "
        "A qualified healthcare professional must review and verify all findings against primary source records."
    )
