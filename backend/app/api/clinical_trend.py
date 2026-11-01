from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.clinical_measurement import ClinicalMeasurement
from app.schemas.clinical_trend import (
    ClinicalTrendResponse,
    ClinicalTrendPoint,
)

router = APIRouter(
    prefix="/patients",
    tags=["Clinical Trends"],
)


@router.get(
    "/{patient_id}/clinical-trends",
    response_model=ClinicalTrendResponse,
)
def get_clinical_trends(
    patient_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    # Find the patient.
    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id)
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found",
        )

    # Retrieve measurements with the matching patient's visit dates.
    results = (
        db.query(ClinicalMeasurement, Visit.visit_date)
        .join(
            Visit,
            ClinicalMeasurement.visit_id == Visit.id,
        )
        .filter(
            ClinicalMeasurement.patient_id == patient_id,
            Visit.patient_id == patient_id,
        )
        .order_by(
            Visit.visit_date.asc(),
            ClinicalMeasurement.id.asc(),
        )
        .all()
    )

    # Map latest measurement per visit so revisions are not treated as separate visits.
    # Because results is ordered chronologically, dict insertion order maintains chronological visit progression.
    latest_by_visit: dict[int, tuple[ClinicalMeasurement, any]] = {}
    for measurement, visit_date in results:
        latest_by_visit[measurement.visit_id] = (measurement, visit_date)

    measurements = []

    for visit_id, (measurement, visit_date) in latest_by_visit.items():
        measurements.append(
            ClinicalTrendPoint(
                visit_id=measurement.visit_id,
                visit_date=visit_date,
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
        )

    return ClinicalTrendResponse(
        patient_id=patient.id,
        patient_name=patient.name,
        measurements=measurements,
    )
