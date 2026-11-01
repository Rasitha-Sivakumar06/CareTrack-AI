from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.medical_report import MedicalReport
from app.models.clinical_measurement import ClinicalMeasurement
from app.schemas.timeline import PatientTimelineResponse


router = APIRouter(
    prefix="/patients",
    tags=["Patient Timeline"],
)


@router.get(
    "/{patient_id}/timeline",
    response_model=PatientTimelineResponse,
)
def get_patient_timeline(
    patient_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id)
        .first()
    )

    if patient is None:
        raise HTTPException(
            status_code=404,
            detail="Patient not found",
        )

    visits = (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_date.asc(), Visit.id.asc())
        .all()
    )

    timeline_visits = []

    for visit in visits:
        reports = (
            db.query(MedicalReport)
            .filter(MedicalReport.visit_id == visit.id)
            .order_by(MedicalReport.id.asc())
            .all()
        )

        measurements = (
            db.query(ClinicalMeasurement)
            .filter(
                ClinicalMeasurement.visit_id == visit.id,
                ClinicalMeasurement.patient_id == patient_id,
            )
            .order_by(
                ClinicalMeasurement.created_at.asc(),
                ClinicalMeasurement.id.asc(),
            )
            .all()
        )

        # Deduplicate reports per visit (grouping identical file_name and extracted_text)
        unique_reports = []
        seen_report_keys = set()
        for report in reports:
            key = (report.file_name or "", (report.extracted_text or "").strip())
            if key not in seen_report_keys:
                seen_report_keys.add(key)
                unique_reports.append(report)

        timeline_reports = [
            {
                "id": report.id,
                "file_name": report.file_name,
                "file_type": report.file_type,
                "extracted_text": report.extracted_text,
            }
            for report in unique_reports
        ]

        # Order measurements newest first so latest measurement is the primary reading (index 0)
        # while preserving earlier readings as revision history
        epoch_fallback = datetime.min.replace(tzinfo=timezone.utc)
        sorted_measurements = sorted(
            measurements,
            key=lambda m: (m.created_at or epoch_fallback, m.id),
            reverse=True,
        )

        timeline_measurements = [
            {
                "id": measurement.id,
                "patient_id": measurement.patient_id,
                "visit_id": measurement.visit_id,
                "blood_pressure": measurement.blood_pressure,
                "systolic_bp": measurement.systolic_bp,
                "diastolic_bp": measurement.diastolic_bp,
                "hemoglobin": measurement.hemoglobin,
                "blood_glucose": measurement.blood_glucose,
                "heart_rate": measurement.heart_rate,
                "temperature": measurement.temperature,
                "oxygen_saturation": measurement.oxygen_saturation,
                "weight": measurement.weight,
                "measured_at": measurement.measured_at,
                "created_at": measurement.created_at,
                "is_latest": (idx == 0),
            }
            for idx, measurement in enumerate(sorted_measurements)
        ]

        timeline_visits.append(
            {
                "id": visit.id,
                "visit_date": visit.visit_date,
                "symptoms": visit.symptoms,
                "clinical_notes": visit.clinical_notes,
                "follow_up_notes": visit.follow_up_notes,
                "reports": timeline_reports,
                "measurements": timeline_measurements,
            }
        )

    return {
        "patient_id": patient.id,
        "patient_code": patient.patient_code,
        "name": patient.name,
        "age": patient.age,
        "gender": patient.gender,
        "phone": patient.phone,
        "location": patient.location,
        "visits": timeline_visits,
    }
