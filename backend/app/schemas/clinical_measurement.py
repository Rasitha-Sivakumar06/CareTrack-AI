
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClinicalMeasurementCreate(BaseModel):
    patient_id: int = Field(gt=0)
    visit_id: int = Field(gt=0)

    # Actual time the measurement was taken.
    measured_at: Optional[datetime] = None

    blood_pressure: Optional[str] = Field(
        default=None, max_length=30
    )
    systolic_bp: Optional[int] = Field(
        default=None, ge=0, le=300
    )
    diastolic_bp: Optional[int] = Field(
        default=None, ge=0, le=200
    )

    hemoglobin: Optional[float] = Field(
        default=None, ge=0, le=30
    )
    blood_glucose: Optional[float] = Field(
        default=None, ge=0, le=2000
    )
    heart_rate: Optional[float] = Field(
        default=None, ge=0, le=400
    )
    temperature: Optional[float] = Field(
        default=None, ge=0, le=100
    )
    oxygen_saturation: Optional[float] = Field(
        default=None, ge=0, le=100
    )
    weight: Optional[float] = Field(
        default=None, gt=0, le=500
    )

    @model_validator(mode="after")
    def require_at_least_one_measurement(self):
        measurement_fields = (
            "blood_pressure",
            "systolic_bp",
            "diastolic_bp",
            "hemoglobin",
            "blood_glucose",
            "heart_rate",
            "temperature",
            "oxygen_saturation",
            "weight",
        )

        if not any(
            getattr(self, field) is not None
            for field in measurement_fields
        ):
            raise ValueError(
                "Provide at least one clinical measurement."
            )

        return self


class ClinicalMeasurementResponse(ClinicalMeasurementCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp_warning: Optional[str] = None
