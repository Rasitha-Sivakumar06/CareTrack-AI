from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TimelineReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    extracted_text: Optional[str] = None


class TimelineMeasurement(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    visit_id: int

    blood_pressure: Optional[str] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None

    hemoglobin: Optional[float] = None
    blood_glucose: Optional[float] = None
    heart_rate: Optional[float] = None
    temperature: Optional[float] = None
    oxygen_saturation: Optional[float] = None
    weight: Optional[float] = None

    measured_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    is_latest: bool = True


class TimelineVisit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_date: date

    symptoms: Optional[str] = None
    clinical_notes: Optional[str] = None
    follow_up_notes: Optional[str] = None

    reports: list[TimelineReport] = Field(default_factory=list)
    measurements: list[TimelineMeasurement] = Field(default_factory=list)


class PatientTimelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: int
    patient_code: str
    name: str

    age: Optional[int] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None

    visits: list[TimelineVisit] = Field(default_factory=list)
