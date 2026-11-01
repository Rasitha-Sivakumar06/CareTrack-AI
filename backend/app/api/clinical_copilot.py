
from datetime import date, datetime
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.medical_report import MedicalReport
from app.models.clinical_measurement import ClinicalMeasurement
from app.services.clinical_copilot_service import ask_clinical_copilot


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-copilot",
    tags=["AI Clinical Copilot"],
)


class CopilotQuestion(BaseModel):
    patient_id: int = Field(gt=0)
    question: str = Field(min_length=3, max_length=2000)


class CopilotAnswer(BaseModel):
    patient_id: int
    patient_name: str
    answer: str


def json_safe(value):
    """Convert date/time values into JSON-safe strings."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()

    return value


def get_timestamp_warning(measured_at, visit_date):
    """
    Flag missing or differing dates without assuming which date is correct.

    Calendar dates are compared as stored. No timezone conversion is
    performed because the intended clinical timezone is not established.
    """

    if measured_at is None:
        return (
            "Measurement time is missing. "
            "Database creation time must not be used as a substitute."
        )

    if visit_date is None:
        return (
            "Visit date is missing. "
            "The measurement timeline cannot be fully verified."
        )

    if measured_at.date() != visit_date:
        return (
            "Measurement timestamp date differs from the visit date. "
            "Verify the source records and intended timezone."
        )

    return None


def build_measurement_context(measurement, visit):
    """Build a structured, transparent context for one measurement."""

    timestamp_warning = get_timestamp_warning(
        measurement.measured_at,
        visit.visit_date,
    )

    return {
        "measurement_id": measurement.id,
        "patient_id": measurement.patient_id,
        "visit_id": measurement.visit_id,
        "visit_date": json_safe(visit.visit_date),
        "measured_at": json_safe(measurement.measured_at),
        "created_at": json_safe(measurement.created_at),
        "measurement_time_missing": measurement.measured_at is None,
        "visit_date_missing": visit.visit_date is None,
        "timestamp_warning": timestamp_warning,
        "timestamp_status": (
            "needs_verification"
            if timestamp_warning
            else "no_date_mismatch_detected"
        ),
        "blood_pressure": measurement.blood_pressure,
        "systolic_bp": measurement.systolic_bp,
        "diastolic_bp": measurement.diastolic_bp,
        "hemoglobin": measurement.hemoglobin,
        "blood_glucose": measurement.blood_glucose,
        "heart_rate": measurement.heart_rate,
        "temperature": measurement.temperature,
        "oxygen_saturation": measurement.oxygen_saturation,
        "weight": measurement.weight,
    }


@router.post("/ask", response_model=CopilotAnswer)
def ask_copilot(
    request: CopilotQuestion,
    db: Session = Depends(get_db),
):
    # Find the requested patient.
    patient = (
        db.query(Patient)
        .filter(Patient.id == request.patient_id)
        .first()
    )

    if patient is None:
        raise HTTPException(
            status_code=404,
            detail="Patient not found.",
        )

    try:
        # Retrieve the patient's visits in chronological order.
        visits = (
            db.query(Visit)
            .filter(Visit.patient_id == patient.id)
            .order_by(Visit.visit_date.asc(), Visit.id.asc())
            .all()
        )

        visit_context = []

        for visit in visits:
            # Retrieve measurements belonging to this patient and visit.
            measurements = (
                db.query(ClinicalMeasurement)
                .filter(
                    ClinicalMeasurement.patient_id == patient.id,
                    ClinicalMeasurement.visit_id == visit.id,
                )
                .order_by(ClinicalMeasurement.id.asc())
                .all()
            )

            # Retrieve reports associated with this visit.
            reports = (
                db.query(MedicalReport)
                .filter(MedicalReport.visit_id == visit.id)
                .order_by(MedicalReport.id.asc())
                .all()
            )

            measurement_context = [
                build_measurement_context(measurement, visit)
                for measurement in measurements
            ]

            report_context = [
                {
                    "file_name": report.file_name,
                    "file_type": report.file_type,
                    "extracted_text": report.extracted_text,
                }
                for report in reports
            ]

            visit_context.append({
                "visit_id": visit.id,
                "visit_date": json_safe(visit.visit_date),
                "symptoms": visit.symptoms,
                "clinical_notes": visit.clinical_notes,
                "follow_up_notes": visit.follow_up_notes,
                "measurements": measurement_context,
                "reports": report_context,
            })

        # Build a data-quality summary independently of the AI response.
        all_measurements = [
            measurement
            for visit_data in visit_context
            for measurement in visit_data["measurements"]
        ]

        missing_measurement_times = [
            measurement["measurement_id"]
            for measurement in all_measurements
            if measurement["measurement_time_missing"]
        ]

        timestamp_warnings = [
            {
                "measurement_id": measurement["measurement_id"],
                "visit_id": measurement["visit_id"],
                "visit_date": measurement["visit_date"],
                "measured_at": measurement["measured_at"],
                "created_at": measurement["created_at"],
                "warning": measurement["timestamp_warning"],
            }
            for measurement in all_measurements
            if measurement["timestamp_warning"] is not None
        ]

        patient_context = json.dumps(
            {
                "patient": {
                    "patient_id": patient.id,
                    "patient_code": patient.patient_code,
                    "name": patient.name,
                    "age": patient.age,
                    "gender": patient.gender,
                    "location": patient.location,
                },
                "visits": visit_context,
                "data_quality_summary": {
                    "missing_measurement_time_ids":
                        missing_measurement_times,
                    "timestamp_warning_count":
                        len(timestamp_warnings),
                    "timestamp_warnings":
                        timestamp_warnings,
                    "interpretation_note": (
                        "These warnings identify data-quality limitations. "
                        "They do not prove that a measurement is inaccurate, "
                        "belongs to another visit, or indicates clinical "
                        "improvement or deterioration."
                    ),
                },
            },
            ensure_ascii=False,
            default=str,
        )

    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve the patient's clinical records.",
        )

    try:
        # Generate clinician-reviewed decision-support guidance.
        answer = ask_clinical_copilot(
            question=request.question.strip(),
            patient_context=patient_context,
        )

        return CopilotAnswer(
            patient_id=patient.id,
            patient_name=patient.name,
            answer=answer,
        )

    except Exception as exc:
        # Safe server-side exception logging: only record error type and patient ID.
        # Do not log question text, patient clinical history, or API keys.
        logger.error(
            "Clinical Copilot query failed for patient_id=%s. Error: %s: %s",
            patient.id,
            type(exc).__name__,
            str(exc)[:200],
            exc_info=False,
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "The AI service could not generate a response. "
                "Please try again."
            ),
        ) from None
