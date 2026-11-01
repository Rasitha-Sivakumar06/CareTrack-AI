from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class InsightItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric: str
    previous_value: Optional[float] = None
    current_value: Optional[float] = None
    change: Optional[float] = None
    unit: str
    observation: str
    status: str


class LongitudinalInsightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: int = Field(gt=0)
    patient_name: str

    previous_visit_date: Optional[str] = None
    current_visit_date: Optional[str] = None

    insights: list[InsightItem] = Field(default_factory=list)
    summary: str

    disclaimer: str = (
        "These observations support clinical review and are not a diagnosis. "
        "A qualified healthcare professional must interpret the results."
    )
