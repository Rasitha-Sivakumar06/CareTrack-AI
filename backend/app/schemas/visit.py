from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class VisitCreate(BaseModel):
    patient_id: int = Field(gt=0)
    visit_date: date
    symptoms: Optional[str] = None
    clinical_notes: Optional[str] = None
    follow_up_notes: Optional[str] = None


class VisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    visit_date: date
    symptoms: Optional[str] = None
    clinical_notes: Optional[str] = None
    follow_up_notes: Optional[str] = None
