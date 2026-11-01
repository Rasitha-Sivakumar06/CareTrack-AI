from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.clinical_measurement import ClinicalMeasurement
from app.schemas.clinical_measurement import (
    ClinicalMeasurementCreate,
    ClinicalMeasurementResponse,
)

router = APIRouter(
    prefix="/clinical-measurements",
    tags=["Clinical Measurements"],
)


@router.post(
    "",
    response_model=ClinicalMeasurementResponse,
    status_code=201,
    include_in_schema=False,
)
@router.post(
    "/",
    response_model=ClinicalMeasurementResponse,
    status_code=201,
)
def create_clinical_measurement(
    measurement: ClinicalMeasurementCreate,
    db: Session = Depends(get_db),
):
    # Verify that the patient exists.
    patient = (
        db.query(Patient)
        .filter(Patient.id == measurement.patient_id)
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found",
        )

    # Verify that the visit exists and belongs to this patient.
    visit = (
        db.query(Visit)
        .filter(
            Visit.id == measurement.visit_id,
            Visit.patient_id == measurement.patient_id,
        )
        .first()
    )

    if not visit:
        raise HTTPException(
            status_code=404,
            detail="Visit not found for this patient",
        )

    # Check whether the actual measurement date differs from the visit date.
    timestamp_warning = None

    if measurement.measured_at is not None:
        measured_date = measurement.measured_at.date()
        if measured_date != visit.visit_date:
            timestamp_warning = (
                f"Measurement date ({measured_date.isoformat()}) differs from "
                f"recorded visit date ({visit.visit_date.isoformat()}). "
                "Please verify the date before interpreting the timeline."
            )

    # Check for identical duplicate measurement on this visit to prevent repeated submissions
    metric_fields = (
        "systolic_bp",
        "diastolic_bp",
        "blood_pressure",
        "hemoglobin",
        "blood_glucose",
        "heart_rate",
        "temperature",
        "oxygen_saturation",
        "weight",
    )

    existing_measurements = (
        db.query(ClinicalMeasurement)
        .filter(
            ClinicalMeasurement.patient_id == measurement.patient_id,
            ClinicalMeasurement.visit_id == measurement.visit_id,
        )
        .all()
    )

    provided_fields = [
        f for f in metric_fields if getattr(measurement, f) is not None
    ]

    for existing in existing_measurements:
        if provided_fields and all(
            getattr(existing, f) == getattr(measurement, f)
            for f in provided_fields
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Identical clinical measurements have already been recorded "
                    "for this visit. Repeated submission rejected."
                ),
            )

    # Create the clinical measurement record.
    new_measurement = ClinicalMeasurement(
        patient_id=measurement.patient_id,
        visit_id=measurement.visit_id,
        measured_at=measurement.measured_at,
        blood_pressure=measurement.blood_pressure,
        systolic_bp=measurement.systolic_bp,
        diastolic_bp=measurement.diastolic_bp,
        hemoglobin=measurement.hemoglobin,
        blood_glucose=measurement.blood_glucose,
        heart_rate=measurement.heart_rate,
        temperature=measurement.temperature,
        oxygen_saturation=measurement.oxygen_saturation,
        weight=measurement.weight,
    )

    try:
        db.add(new_measurement)
        db.commit()
        db.refresh(new_measurement)

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save the clinical measurement.",
        )

    response = ClinicalMeasurementResponse.model_validate(
        new_measurement
    )

    response.timestamp_warning = timestamp_warning

    return response