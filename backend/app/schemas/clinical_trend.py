from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ClinicalTrendPoint(BaseModel):
    visit_id: int = Field(gt=0)
    visit_date: date

    blood_pressure: Optional[str] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None

    hemoglobin: Optional[float] = None
    blood_glucose: Optional[float] = None
    heart_rate: Optional[float] = None
    temperature: Optional[float] = None
    oxygen_saturation: Optional[float] = None
    weight: Optional[float] = None


class ClinicalTrendResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: int = Field(gt=0)
    patient_name: str
    measurements: list[ClinicalTrendPoint] = Field(
        default_factory=list
    )
