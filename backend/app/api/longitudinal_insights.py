from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.clinical_measurement import ClinicalMeasurement
from app.schemas.longitudinal_insight import (
    InsightItem,
    LongitudinalInsightResponse,
)

router = APIRouter(
    prefix="/patients",
    tags=["Longitudinal Insights"],
)


def compare_metric(
    metric: str,
    previous: float | None,
    current: float | None,
    unit: str,
) -> InsightItem | None:
    if previous is None or current is None:
        return None

    change = round(current - previous, 2)

    if change > 0:
        direction = "increased"
    elif change < 0:
        direction = "decreased"
    else:
        direction = "remained unchanged"

    if change == 0:
        observation = f"{metric} {direction} at {current} {unit}."
    else:
        observation = (
            f"{metric} {direction} from {previous} to {current} {unit} "
            f"(change: {change:+g} {unit})."
        )

    return InsightItem(
        metric=metric,
        previous_value=previous,
        current_value=current,
        change=change,
        unit=unit,
        observation=observation,
        status="review",
    )


@router.get(
    "/{patient_id}/longitudinal-insights",
    response_model=LongitudinalInsightResponse,
)
def get_longitudinal_insights(
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

    records = (
        db.query(ClinicalMeasurement, Visit)
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

    if not records:
        return LongitudinalInsightResponse(
            patient_id=patient_id,
            patient_name=patient.name,
            insights=[],
            summary="No clinical measurements are available for comparison.",
        )

    # Select the latest measurement record for each visit.
    latest_by_visit = {}

    for measurement, visit in records:
        latest_by_visit[visit.id] = (measurement, visit)

    visits = sorted(
        latest_by_visit.values(),
        key=lambda item: (item[1].visit_date, item[1].id),
    )

    current_measurement, current_visit = visits[-1]

    if len(visits) < 2:
        return LongitudinalInsightResponse(
            patient_id=patient_id,
            patient_name=patient.name,
            current_visit_date=current_visit.visit_date.isoformat(),
            insights=[],
            summary=(
                "Only one visit with measurements is available. "
                "Record another visit to compare changes over time."
            ),
        )

    previous_measurement, previous_visit = visits[-2]

    metrics = [
        ("Blood glucose", "blood_glucose", "mg/dL"),
        ("Systolic blood pressure", "systolic_bp", "mmHg"),
        ("Diastolic blood pressure", "diastolic_bp", "mmHg"),
        ("Hemoglobin", "hemoglobin", "g/dL"),
        ("Heart rate", "heart_rate", "bpm"),
        ("Temperature", "temperature", "°C"),
        ("Oxygen saturation", "oxygen_saturation", "%"),
        ("Weight", "weight", "kg"),
    ]

    insights = []

    for label, attribute, unit in metrics:
        previous_value = getattr(previous_measurement, attribute)
        current_value = getattr(current_measurement, attribute)

        insight = compare_metric(
            label,
            previous_value,
            current_value,
            unit,
        )

        if insight is not None:
            insights.append(insight)

    summary = (
        f"Compared visits on {previous_visit.visit_date} "
        f"and {current_visit.visit_date}. "
        f"{len(insights)} measurements could be compared. "
        "Review the observations in the context of the patient's "
        "history and clinical condition."
    )

    return LongitudinalInsightResponse(
        patient_id=patient_id,
        patient_name=patient.name,
        previous_visit_date=previous_visit.visit_date.isoformat(),
        current_visit_date=current_visit.visit_date.isoformat(),
        insights=insights,
        summary=summary,
    )
