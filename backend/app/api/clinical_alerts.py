from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.clinical_measurement import ClinicalMeasurement

# Router for patient-prefixed endpoints (/patients/{id}/clinical-alerts)
router = APIRouter(
    prefix="/patients",
    tags=["Clinical Alerts"],
)

# Router for top-level /clinical-alerts endpoints
alerts_router = APIRouter(
    prefix="/clinical-alerts",
    tags=["Clinical Alerts"],
)


class ClinicalAlert(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric: str
    value: float
    unit: str
    severity: str
    threshold: str
    reason: str


class ClinicalAlertsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: int = Field(gt=0)
    patient_name: str
    visit_date: Optional[date] = None
    alerts: list[ClinicalAlert] = Field(default_factory=list)
    summary: str
    disclaimer: str = (
        "Demo screening rules only. Alerts are not diagnoses. "
        "A qualified healthcare professional must review the results."
    )


class AlertRuleDefinition(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field: str
    metric: str
    unit: str
    low: Optional[float] = None
    high: Optional[float] = None
    severity: str


class PatientAlertItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: int = Field(gt=0)
    patient_name: str
    patient_code: str
    age: Optional[int] = None
    gender: Optional[str] = None
    location: Optional[str] = None
    latest_visit_date: Optional[date] = None
    highest_severity: str  # high, moderate, normal, no_data
    alerts_count: int = 0
    alerts: list[ClinicalAlert] = Field(default_factory=list)
    summary: str
    is_synthetic_demo: bool = True


class ClinicalAlertsOverviewSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_patients_evaluated: int
    patients_with_alerts: int
    high_priority_count: int
    moderate_priority_count: int
    normal_count: int
    no_data_count: int


class ClinicalAlertsOverviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rules: list[AlertRuleDefinition]
    summary: ClinicalAlertsOverviewSummary
    patients: list[PatientAlertItem]
    disclaimer: str = (
        "Demonstration screening rules applied to synthetic patient data. "
        "Alerts are not medical diagnoses and do not constitute real-time monitoring. "
        "A qualified healthcare professional must review and confirm all clinical findings."
    )


# Illustrative demonstration thresholds only.
# These are not validated medical guidance or emergency triage rules.
ALERT_RULES = [
    {
        "field": "systolic_bp",
        "metric": "Systolic blood pressure",
        "unit": "mmHg",
        "low": 90,
        "high": 180,
        "severity": "high",
    },
    {
        "field": "diastolic_bp",
        "metric": "Diastolic blood pressure",
        "unit": "mmHg",
        "low": 60,
        "high": 120,
        "severity": "high",
    },
    {
        "field": "blood_glucose",
        "metric": "Blood glucose",
        "unit": "mg/dL",
        "low": 70,
        "high": 200,
        "severity": "moderate",
    },
    {
        "field": "heart_rate",
        "metric": "Heart rate",
        "unit": "bpm",
        "low": 50,
        "high": 120,
        "severity": "moderate",
    },
    {
        "field": "temperature",
        "metric": "Body temperature",
        "unit": "°C",
        "low": 35,
        "high": 38,
        "severity": "moderate",
    },
    {
        "field": "oxygen_saturation",
        "metric": "Oxygen saturation",
        "unit": "%",
        "low": 92,
        "high": None,
        "severity": "high",
    },
]


def evaluate_alerts_for_patient(patient: Patient, db: Session) -> PatientAlertItem:
    """
    Evaluates demonstration screening alert rules against the most recent clinical
    measurement for the given patient.
    """
    latest = (
        db.query(ClinicalMeasurement, Visit)
        .join(
            Visit,
            ClinicalMeasurement.visit_id == Visit.id,
        )
        .filter(
            ClinicalMeasurement.patient_id == patient.id,
            Visit.patient_id == patient.id,
        )
        .order_by(
            Visit.visit_date.desc(),
            Visit.id.desc(),
            ClinicalMeasurement.id.desc(),
        )
        .first()
    )

    if latest is None:
        return PatientAlertItem(
            patient_id=patient.id,
            patient_name=patient.name,
            patient_code=patient.patient_code,
            age=patient.age,
            gender=patient.gender,
            location=patient.location,
            latest_visit_date=None,
            highest_severity="no_data",
            alerts_count=0,
            alerts=[],
            summary="No recorded clinical measurements on file to evaluate.",
            is_synthetic_demo=True,
        )

    measurement, visit = latest
    alerts = []

    for rule in ALERT_RULES:
        value = getattr(measurement, rule["field"], None)

        # Missing measurements are skipped, not assumed normal.
        if value is None:
            continue

        below = rule["low"] is not None and value < rule["low"]
        above = rule["high"] is not None and value > rule["high"]

        if below or above:
            if below:
                threshold = f"Below {rule['low']} {rule['unit']}"
                direction = "below"
            else:
                threshold = f"Above {rule['high']} {rule['unit']}"
                direction = "above"

            alerts.append(
                ClinicalAlert(
                    metric=rule["metric"],
                    value=float(value),
                    unit=rule["unit"],
                    severity=rule["severity"],
                    threshold=threshold,
                    reason=(
                        f"Recorded value is {direction} the configured "
                        "demo review threshold. Qualified clinical review "
                        "is recommended."
                    ),
                )
            )

    if any(a.severity == "high" for a in alerts):
        highest_severity = "high"
    elif any(a.severity == "moderate" for a in alerts):
        highest_severity = "moderate"
    else:
        highest_severity = "normal"

    if alerts:
        summary = (
            f"{len(alerts)} measurement(s) crossed demonstration review thresholds. "
            "Arrange qualified clinical review."
        )
    else:
        summary = (
            "All recorded values are within the configured demonstration thresholds. "
            "This does not establish that the patient is healthy."
        )

    return PatientAlertItem(
        patient_id=patient.id,
        patient_name=patient.name,
        patient_code=patient.patient_code,
        age=patient.age,
        gender=patient.gender,
        location=patient.location,
        latest_visit_date=visit.visit_date,
        highest_severity=highest_severity,
        alerts_count=len(alerts),
        alerts=alerts,
        summary=summary,
        is_synthetic_demo=True,
    )


@router.get(
    "/{patient_id}/clinical-alerts",
    response_model=ClinicalAlertsResponse,
)
def get_clinical_alerts(
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

    item = evaluate_alerts_for_patient(patient, db)

    return ClinicalAlertsResponse(
        patient_id=item.patient_id,
        patient_name=item.patient_name,
        visit_date=item.latest_visit_date,
        alerts=item.alerts,
        summary=item.summary,
    )


def compute_alerts_overview(db: Session) -> ClinicalAlertsOverviewResponse:
    patients = db.query(Patient).order_by(Patient.id.asc()).all()
    patient_items: list[PatientAlertItem] = []

    high_count = 0
    mod_count = 0
    normal_count = 0
    no_data_count = 0
    with_alerts_count = 0

    for p in patients:
        item = evaluate_alerts_for_patient(p, db)
        patient_items.append(item)

        if item.highest_severity == "high":
            high_count += 1
            with_alerts_count += 1
        elif item.highest_severity == "moderate":
            mod_count += 1
            with_alerts_count += 1
        elif item.highest_severity == "normal":
            normal_count += 1
        elif item.highest_severity == "no_data":
            no_data_count += 1

    # Priority sort: high severity first, then moderate, then no_data, then normal
    severity_rank = {
        "high": 1,
        "moderate": 2,
        "no_data": 3,
        "normal": 4,
    }
    patient_items.sort(
        key=lambda item: (
            severity_rank.get(item.highest_severity, 5),
            -item.alerts_count,
            item.patient_id,
        )
    )

    rules = [AlertRuleDefinition(**r) for r in ALERT_RULES]

    summary = ClinicalAlertsOverviewSummary(
        total_patients_evaluated=len(patients),
        patients_with_alerts=with_alerts_count,
        high_priority_count=high_count,
        moderate_priority_count=mod_count,
        normal_count=normal_count,
        no_data_count=no_data_count,
    )

    return ClinicalAlertsOverviewResponse(
        rules=rules,
        summary=summary,
        patients=patient_items,
    )


@alerts_router.get(
    "/overview",
    response_model=ClinicalAlertsOverviewResponse,
    summary="Clinical Alerts & Health Urgency Overview",
)
def get_alerts_overview(
    db: Session = Depends(get_db),
):
    """
    Returns an overview of all configured demonstration screening rules,
    aggregated alert counts, and prioritized patient alert items for the
    Clinical Alerts Dashboard.
    """
    return compute_alerts_overview(db)


@router.get(
    "/alerts/overview",
    response_model=ClinicalAlertsOverviewResponse,
    include_in_schema=False,
)
def get_alerts_overview_alias(
    db: Session = Depends(get_db),
):
    return compute_alerts_overview(db)
