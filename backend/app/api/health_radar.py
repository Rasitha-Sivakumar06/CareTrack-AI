from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.clinical_measurement import ClinicalMeasurement
from app.schemas.health_radar import (
    HealthRadarMetric,
    HealthRadarResponse,
    HealthRadarSummary,
)

router = APIRouter(
    prefix="/patients",
    tags=["Health Change Radar"],
)


def clamp(val: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, val))


def calculate_normalized_score(metric_key: str, value: Optional[float]) -> Optional[float]:
    """
    Normalizes diverse clinical vital signs onto a standardized 0-100 radar axis.
    50 represents a standard reference baseline midpoint.
    """
    if value is None:
        return None

    try:
        val = float(value)
    except (ValueError, TypeError):
        return None

    if metric_key == "blood_glucose":
        # 50 mg/dL -> 10, 100 mg/dL -> 50, 200 mg/dL -> 85, 250+ -> 100
        return round(clamp(10.0 + ((val - 50.0) / 200.0) * 80.0), 1)

    if metric_key == "systolic_bp":
        # 80 mmHg -> 15, 120 mmHg -> 50, 180 mmHg -> 90
        return round(clamp(15.0 + ((val - 80.0) / 100.0) * 70.0), 1)

    if metric_key == "diastolic_bp":
        # 50 mmHg -> 15, 80 mmHg -> 50, 110 mmHg -> 90
        return round(clamp(15.0 + ((val - 50.0) / 60.0) * 70.0), 1)

    if metric_key == "heart_rate":
        # 45 bpm -> 15, 75 bpm -> 50, 120 bpm -> 90
        return round(clamp(15.0 + ((val - 45.0) / 75.0) * 70.0), 1)

    if metric_key == "oxygen_saturation":
        # 85% -> 15, 95% -> 60, 100% -> 95
        return round(clamp(15.0 + ((val - 85.0) / 15.0) * 80.0), 1)

    if metric_key == "hemoglobin":
        # 7 g/dL -> 15, 14 g/dL -> 65, 18 g/dL -> 95
        return round(clamp(15.0 + ((val - 7.0) / 11.0) * 80.0), 1)

    if metric_key == "temperature":
        # 35.5 C -> 20, 36.8 C -> 50, 39.5 C -> 95
        return round(clamp(20.0 + ((val - 35.5) / 4.0) * 75.0), 1)

    if metric_key == "weight":
        # 40 kg -> 20, 70 kg -> 55, 120 kg -> 95
        return round(clamp(20.0 + ((val - 40.0) / 80.0) * 75.0), 1)

    return 50.0


METRIC_DEFINITIONS = [
    {
        "key": "blood_glucose",
        "label": "Blood Glucose",
        "unit": "mg/dL",
    },
    {
        "key": "systolic_bp",
        "label": "Systolic BP",
        "unit": "mmHg",
    },
    {
        "key": "diastolic_bp",
        "label": "Diastolic BP",
        "unit": "mmHg",
    },
    {
        "key": "heart_rate",
        "label": "Heart Rate",
        "unit": "bpm",
    },
    {
        "key": "oxygen_saturation",
        "label": "Oxygen Saturation",
        "unit": "%",
    },
    {
        "key": "hemoglobin",
        "label": "Hemoglobin",
        "unit": "g/dL",
    },
    {
        "key": "temperature",
        "label": "Temperature",
        "unit": "°C",
    },
    {
        "key": "weight",
        "label": "Body Weight",
        "unit": "kg",
    },
]


def evaluate_clinical_change(
    key: str,
    label: str,
    unit: str,
    b_val: Optional[float],
    b_date: Optional[str],
    c_val: Optional[float],
    c_date: Optional[str],
) -> tuple[str, str, str, str, Optional[float], Optional[float]]:
    """
    Returns (alert_level, status, formula, reason, delta, percent_change)
    Alert levels: HIGH_ATTENTION, MODERATE_ATTENTION, STABLE, DATA_GAP
    """
    if b_val is None and c_val is None:
        return (
            "DATA_GAP",
            "UNRECORDED",
            f"No {label.lower()} measurements recorded across baseline or current visit.",
            f"No {label.lower()} data on file. Assess whether this measurement is clinically indicated.",
            None,
            None,
        )

    if b_val is not None and c_val is None:
        return (
            "DATA_GAP",
            "MISSING_CURRENT",
            f"Baseline: {b_val} {unit} ({b_date}). Current visit measurement missing.",
            f"{label} was omitted during the latest visit. Do not assume normal or unchanged values without measurement.",
            None,
            None,
        )

    if b_val is None and c_val is not None:
        return (
            "DATA_GAP",
            "NEW_METRIC",
            f"Current: {c_val} {unit} ({c_date}). Baseline measurement not recorded.",
            f"{label} recorded for the first time. Establishes baseline for future longitudinal comparisons.",
            None,
            None,
        )

    # Both values exist
    delta = round(c_val - b_val, 2)
    pct = round(((c_val - b_val) / b_val) * 100.0, 1) if b_val != 0 else 0.0

    if delta == 0:
        formula = f"Current ({c_val} {unit} on {c_date}) == Baseline ({b_val} {unit} on {b_date}) -> Change: 0.0 {unit} (0.0%)"
    else:
        formula = f"Current ({c_val} {unit} on {c_date}) - Baseline ({b_val} {unit} on {b_date}) = {delta:+g} {unit} ({pct:+g}%)"

    # Clinical rules per metric
    if key == "oxygen_saturation":
        if c_val < 92.0:
            return (
                "HIGH_ATTENTION",
                "HYPOXIA_CONCERN",
                formula,
                "Current oxygen saturation is below 92%. Immediate clinical assessment of airway and oxygenation advised.",
                delta,
                pct,
            )
        if delta <= -4.0:
            return (
                "HIGH_ATTENTION",
                "SIGNIFICANT_DROP",
                formula,
                f"Oxygen saturation decreased by {abs(delta)}% from baseline ({b_val}% -> {c_val}%). Check respiratory symptoms.",
                delta,
                pct,
            )

    if key == "systolic_bp":
        if c_val >= 160.0 or delta >= 25.0:
            return (
                "HIGH_ATTENTION",
                "ELEVATED_SHIFT",
                formula,
                f"Systolic blood pressure elevated (+{delta} mmHg). Evaluate for medication adherence, stress, or hypertensive progression.",
                delta,
                pct,
            )
        if c_val < 90.0 or delta <= -25.0:
            return (
                "HIGH_ATTENTION",
                "HYPOTENSIVE_SHIFT",
                formula,
                f"Systolic blood pressure markedly low or declining ({delta} mmHg). Assess for dehydration, sepsis, or medication overtreatment.",
                delta,
                pct,
            )
        if c_val >= 140.0 or delta >= 15.0:
            return (
                "MODERATE_ATTENTION",
                "MODERATE_ELEVATION",
                formula,
                "Mild-to-moderate systolic rise above baseline. Ongoing blood pressure tracking recommended.",
                delta,
                pct,
            )

    if key == "diastolic_bp":
        if c_val >= 100.0 or delta >= 15.0:
            return (
                "HIGH_ATTENTION",
                "ELEVATED_SHIFT",
                formula,
                f"Diastolic blood pressure elevated ({c_val} mmHg, +{delta} mmHg). Consider cardiovascular assessment.",
                delta,
                pct,
            )
        if c_val < 60.0 or delta <= -15.0:
            return (
                "MODERATE_ATTENTION",
                "HYPOTENSIVE_SHIFT",
                formula,
                "Low diastolic blood pressure observed. Check for orthostatic symptoms.",
                delta,
                pct,
            )

    if key == "blood_glucose":
        if c_val < 70.0:
            return (
                "HIGH_ATTENTION",
                "HYPOGLYCEMIC_SHIFT",
                formula,
                f"Hypoglycemic reading recorded ({c_val} mg/dL). Immediate clinical review of caloric intake and antidiabetic agents required.",
                delta,
                pct,
            )
        if c_val >= 200.0 or delta >= 30.0:
            return (
                "HIGH_ATTENTION",
                "GLYCEMIC_ELEVATION",
                formula,
                f"Blood glucose increased significantly (+{delta} mg/dL to {c_val} mg/dL). Review fasting status, diet, and HbA1c.",
                delta,
                pct,
            )
        if c_val >= 140.0 or delta >= 15.0:
            return (
                "MODERATE_ATTENTION",
                "MODERATE_ELEVATION",
                formula,
                "Moderate glycemic elevation observed above baseline. Follow up on diabetes management plan.",
                delta,
                pct,
            )

    if key == "heart_rate":
        if c_val > 110.0 or c_val < 50.0:
            return (
                "HIGH_ATTENTION",
                "TACHY_BRADYCARDIA",
                formula,
                f"Resting heart rate outside standard limits ({c_val} bpm). Review cardiac rhythm, thyroid function, or medications.",
                delta,
                pct,
            )
        if abs(delta) >= 20.0:
            return (
                "MODERATE_ATTENTION",
                "RATE_VARIABILITY",
                formula,
                f"Heart rate shift of {delta:+g} bpm noted across visits. Assess for pain, anxiety, infection, or medication effects.",
                delta,
                pct,
            )

    if key == "temperature":
        if c_val >= 38.0:
            return (
                "HIGH_ATTENTION",
                "FEVER_DETECTED",
                formula,
                f"Pyrexia recorded ({c_val} °C). Investigate for acute infectious or inflammatory focus.",
                delta,
                pct,
            )
        if c_val < 35.5:
            return (
                "MODERATE_ATTENTION",
                "HYPOTHERMIC_SHIFT",
                formula,
                "Subnormal body temperature noted. Verify measurement accuracy.",
                delta,
                pct,
            )

    if key == "hemoglobin":
        if c_val < 11.0 or delta <= -2.0:
            return (
                "HIGH_ATTENTION",
                "ANEMIA_ALERT",
                formula,
                f"Hemoglobin is low or declining ({c_val} g/dL, change {delta:+g} g/dL). Screen for blood loss or nutritional deficiency.",
                delta,
                pct,
            )

    if key == "weight":
        if abs(pct) >= 7.0:
            return (
                "HIGH_ATTENTION",
                "RAPID_WEIGHT_CHANGE",
                formula,
                f"Weight shifted by {pct:+g}% ({delta:+g} kg). Rapid weight changes may indicate fluid retention or metabolic imbalance.",
                delta,
                pct,
            )
        if abs(pct) >= 4.0:
            return (
                "MODERATE_ATTENTION",
                "WEIGHT_CHANGE",
                formula,
                f"Moderate weight change of {delta:+g} kg ({pct:+g}%). Track dietary intake and lifestyle.",
                delta,
                pct,
            )

    return (
        "STABLE",
        "WITHIN_BASELINE",
        formula,
        f"{label} remains within expected baseline variance.",
        delta,
        pct,
    )


@router.get(
    "/{patient_id}/health-radar",
    response_model=HealthRadarResponse,
    summary="Health Change Radar Decision Support",
)
def get_health_change_radar(
    patient_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    """
    Computes multidimensional longitudinal health change radar comparison
    between historical baseline and recent measurements with explainable
    mathematical delta breakdowns and clinical decision-support rationale.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found.",
        )

    # Retrieve all visits for this patient ordered chronologically
    visits = (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_date.asc(), Visit.id.asc())
        .all()
    )

    if not visits:
        # Patient registered but no visits yet
        summary = HealthRadarSummary(
            patient_id=patient.id,
            patient_name=patient.name,
            patient_code=patient.patient_code,
            total_visits_recorded=0,
            metrics_compared_count=0,
            attention_flags_count=0,
            data_gaps_count=len(METRIC_DEFINITIONS),
            overall_status="INSUFFICIENT_HISTORY",
            evidence_narrative=(
                f"Patient {patient.name} ({patient.patient_code}) has no recorded clinical visits. "
                "Register an initial clinic visit and vital signs to establish a health baseline."
            ),
            clinical_action_suggestions=[
                "Perform initial clinical intake and baseline vitals check.",
                "Record primary symptoms and medical history.",
            ],
        )
        empty_metrics = [
            HealthRadarMetric(
                key=m["key"],
                label=m["label"],
                unit=m["unit"],
                baseline_value=None,
                current_value=None,
                baseline_score=0.0,
                current_score=0.0,
                alert_level="DATA_GAP",
                status="UNRECORDED",
                calculation_formula="No measurements on file.",
                clinical_reason=f"No {m['label'].lower()} measurements recorded.",
            )
            for m in METRIC_DEFINITIONS
        ]
        return HealthRadarResponse(summary=summary, radar_metrics=empty_metrics)

    # Fetch all measurements linked to these visits
    measurements = (
        db.query(ClinicalMeasurement)
        .filter(ClinicalMeasurement.patient_id == patient_id)
        .order_by(ClinicalMeasurement.created_at.asc(), ClinicalMeasurement.id.asc())
        .all()
    )

    # Map latest measurement per visit
    meas_by_visit: dict[int, ClinicalMeasurement] = {}
    for m in measurements:
        meas_by_visit[m.visit_id] = m

    # Select baseline visit and current visit
    # Baseline = earliest visit with measurements (or visits[0])
    # Current = latest visit with measurements (or visits[-1])
    visits_with_meas = [v for v in visits if v.id in meas_by_visit]

    if not visits_with_meas:
        summary = HealthRadarSummary(
            patient_id=patient.id,
            patient_name=patient.name,
            patient_code=patient.patient_code,
            total_visits_recorded=len(visits),
            baseline_visit_date=visits[0].visit_date.isoformat(),
            current_visit_date=visits[-1].visit_date.isoformat(),
            metrics_compared_count=0,
            attention_flags_count=0,
            data_gaps_count=len(METRIC_DEFINITIONS),
            overall_status="INSUFFICIENT_HISTORY",
            evidence_narrative=(
                f"Patient {patient.name} has {len(visits)} visit(s) recorded, but no physical measurements "
                "or vitals were logged. Record clinical measurements to enable the Health Change Radar."
            ),
            clinical_action_suggestions=[
                "Obtain standard vital signs (BP, HR, SpO2, Temperature).",
                "Log blood glucose if metabolic symptoms are present.",
            ],
        )
        empty_metrics = [
            HealthRadarMetric(
                key=m["key"],
                label=m["label"],
                unit=m["unit"],
                baseline_value=None,
                current_value=None,
                baseline_score=0.0,
                current_score=0.0,
                alert_level="DATA_GAP",
                status="UNRECORDED",
                calculation_formula="No measurements on file.",
                clinical_reason=f"No {m['label'].lower()} measurements recorded.",
            )
            for m in METRIC_DEFINITIONS
        ]
        return HealthRadarResponse(summary=summary, radar_metrics=empty_metrics)

    baseline_visit = visits_with_meas[0]
    current_visit = visits_with_meas[-1]
    baseline_meas = meas_by_visit[baseline_visit.id]
    current_meas = meas_by_visit[current_visit.id]

    b_date_str = baseline_visit.visit_date.isoformat()
    c_date_str = current_visit.visit_date.isoformat()

    radar_metrics: list[HealthRadarMetric] = []
    attention_count = 0
    data_gaps_count = 0
    compared_count = 0
    notable_shifts: list[str] = []

    for defn in METRIC_DEFINITIONS:
        k = defn["key"]
        lbl = defn["label"]
        unit = defn["unit"]

        b_val = getattr(baseline_meas, k, None)
        c_val = getattr(current_meas, k, None)

        if b_val is not None and c_val is not None:
            compared_count += 1

        alert_level, status, formula, reason, delta, pct = evaluate_clinical_change(
            key=k,
            label=lbl,
            unit=unit,
            b_val=b_val,
            b_date=b_date_str,
            c_val=c_val,
            c_date=c_date_str,
        )

        if alert_level in ("HIGH_ATTENTION", "MODERATE_ATTENTION"):
            attention_count += 1
            if delta is not None:
                notable_shifts.append(f"{lbl} ({delta:+g} {unit})")

        if alert_level == "DATA_GAP":
            data_gaps_count += 1

        b_score = calculate_normalized_score(k, b_val)
        c_score = calculate_normalized_score(k, c_val)

        radar_metrics.append(
            HealthRadarMetric(
                key=k,
                label=lbl,
                unit=unit,
                baseline_value=b_val,
                baseline_date=b_date_str if b_val is not None else None,
                current_value=c_val,
                current_date=c_date_str if c_val is not None else None,
                delta=delta,
                percent_change=pct,
                baseline_score=b_score or 0.0,
                current_score=c_score or 0.0,
                alert_level=alert_level,
                status=status,
                calculation_formula=formula,
                clinical_reason=reason,
            )
        )

    # Determine overall status and synthesize factual narrative
    if attention_count >= 2 or any(m.alert_level == "HIGH_ATTENTION" for m in radar_metrics):
        overall_status = "ATTENTION_REQUIRED"
    elif attention_count == 1:
        overall_status = "MONITORING_RECOMMENDED"
    elif len(visits_with_meas) < 2:
        overall_status = "INSUFFICIENT_HISTORY"
    else:
        overall_status = "STABLE_TRAJECTORY"

    action_suggestions = []
    if any(m.key == "oxygen_saturation" and m.alert_level == "HIGH_ATTENTION" for m in radar_metrics):
        action_suggestions.append("Immediate priority: evaluate respiratory symptoms and oxygenation.")
    if any(m.key in ("systolic_bp", "diastolic_bp") and m.alert_level == "HIGH_ATTENTION" for m in radar_metrics):
        action_suggestions.append("Review antihypertensive regimen and cardiovascular risk profile.")
    if any(m.key == "blood_glucose" and m.alert_level == "HIGH_ATTENTION" for m in radar_metrics):
        action_suggestions.append("Evaluate dietary adherence, fasting status, and schedule HbA1c review.")
    if data_gaps_count > 0:
        action_suggestions.append(f"Address {data_gaps_count} missing vital sign(s) during the next evaluation.")
    if not action_suggestions:
        action_suggestions.append("Continue current longitudinal management plan and scheduled follow-up.")

    # Synthesize factual narrative
    if len(visits_with_meas) < 2:
        narrative = (
            f"Patient {patient.name} ({patient.patient_code}) has 1 recorded visit with clinical measurements on {c_date_str}. "
            "Initial baseline parameters established. Record an upcoming visit with vitals to calculate longitudinal health shifts."
        )
    else:
        shift_str = ", ".join(notable_shifts) if notable_shifts else "all parameters within baseline stability"
        narrative = (
            f"Patient {patient.name} ({patient.patient_code}) has {len(visits)} visits on record spanning {b_date_str} to {c_date_str}. "
            f"Longitudinal comparison across {compared_count} measured dimension(s) reveals {attention_count} clinical attention flag(s) "
            f"and {data_gaps_count} data gap(s). Primary shifts: {shift_str}."
        )

    summary = HealthRadarSummary(
        patient_id=patient.id,
        patient_name=patient.name,
        patient_code=patient.patient_code,
        total_visits_recorded=len(visits),
        baseline_visit_date=b_date_str,
        current_visit_date=c_date_str,
        metrics_compared_count=compared_count,
        attention_flags_count=attention_count,
        data_gaps_count=data_gaps_count,
        overall_status=overall_status,
        evidence_narrative=narrative,
        clinical_action_suggestions=action_suggestions,
    )

    return HealthRadarResponse(summary=summary, radar_metrics=radar_metrics)
