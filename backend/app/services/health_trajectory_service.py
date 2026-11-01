from datetime import date, datetime
from typing import Optional, List, Dict, Tuple
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.visit import Visit
from app.models.clinical_measurement import ClinicalMeasurement
from app.schemas.health_trajectory import (
    ReadingPoint,
    TrajectoryMetric,
    HealthTrajectorySummary,
    HealthTrajectoryResponse,
)

METRIC_DEFINITIONS = [
    {
        "key": "blood_glucose",
        "label": "Blood Glucose",
        "unit": "mg/dL",
        "ref_low": 70.0,
        "ref_high": 140.0,
    },
    {
        "key": "systolic_bp",
        "label": "Systolic Blood Pressure",
        "unit": "mmHg",
        "ref_low": 90.0,
        "ref_high": 120.0,
    },
    {
        "key": "diastolic_bp",
        "label": "Diastolic Blood Pressure",
        "unit": "mmHg",
        "ref_low": 60.0,
        "ref_high": 80.0,
    },
    {
        "key": "heart_rate",
        "label": "Heart Rate",
        "unit": "bpm",
        "ref_low": 50.0,
        "ref_high": 100.0,
    },
    {
        "key": "oxygen_saturation",
        "label": "Oxygen Saturation",
        "unit": "%",
        "ref_low": 95.0,
        "ref_high": 100.0,
    },
    {
        "key": "hemoglobin",
        "label": "Hemoglobin",
        "unit": "g/dL",
        "ref_low": 12.0,
        "ref_high": 16.5,
    },
    {
        "key": "temperature",
        "label": "Body Temperature",
        "unit": "°C",
        "ref_low": 36.1,
        "ref_high": 37.3,
    },
    {
        "key": "weight",
        "label": "Body Weight",
        "unit": "kg",
        "ref_low": None,
        "ref_high": None,
    },
]


def check_timestamp_warning(measured_at: Optional[datetime], visit_date: Optional[date]) -> Optional[str]:
    """Flag genuine timestamp discrepancy without assuming which date is true."""
    if measured_at is None:
        # Absence of intra-day clock time is grouped cleanly at the visit level
        return None
    if visit_date is None:
        return "Visit date is missing; chronological sequence cannot be verified."
    if measured_at.date() != visit_date:
        return (
            f"Measurement timestamp ({measured_at.date().isoformat()}) differs from "
            f"recorded visit date ({visit_date.isoformat()}). Reconcile source records."
        )
    return None


def classify_metric_trajectory(
    key: str,
    label: str,
    unit: str,
    b_val: Optional[float],
    b_date: Optional[date],
    p_val: Optional[float],
    p_date: Optional[date],
    c_val: Optional[float],
    c_date: Optional[date],
    has_timestamp_warning: bool,
) -> Tuple[str, str, str, str, str]:
    """
    Evaluates longitudinal clinical trajectory using metric-specific physiology rules.
    Returns: (classification, classification_label, severity_level, formula_breakdown, clinical_explanation)
    """
    # 1. Missing data cases
    if b_val is None and c_val is None:
        return (
            "DATA_GAP",
            "Unrecorded Data",
            "info",
            f"No {label.lower()} readings on file.",
            f"{label} has not been documented for this patient across recorded visits.",
        )
    if b_val is not None and c_val is None:
        return (
            "DATA_GAP",
            "Missing Current Reading",
            "moderate",
            f"Baseline: {b_val} {unit} ({b_date}). Current visit reading is missing.",
            f"{label} was omitted during the latest evaluation. Do not assume values remained unchanged.",
        )
    if b_val is None and c_val is not None:
        return (
            "DATA_GAP",
            "New Baseline Established",
            "info",
            f"First recorded reading: {c_val} {unit} ({c_date}). Prior visits unrecorded.",
            f"{label} recorded for the first time on {c_date}. Establishes baseline for future evaluations.",
        )

    # 2. Both baseline and current exist
    delta = round(c_val - b_val, 2)
    pct = round(((c_val - b_val) / b_val) * 100.0, 1) if b_val != 0 else 0.0

    if delta == 0:
        formula = f"Latest ({c_val} {unit} on {c_date}) == Baseline ({b_val} {unit} on {b_date}) -> Change: 0.0 {unit} (0.0%)"
    else:
        formula = f"Latest ({c_val} {unit} on {c_date}) - Baseline ({b_val} {unit} on {b_date}) = {delta:+g} {unit} ({pct:+g}%)"

    if has_timestamp_warning:
        # Transparent data inconsistency flag
        pass

    # 3. Metric-specific clinical change interpretation
    if key == "blood_glucose":
        if c_val < 70.0:
            return (
                "CONCERNING_CHANGE",
                "Hypoglycemic Reading",
                "high",
                formula,
                f"Blood glucose declined to hypoglycemic range ({c_val} mg/dL). Immediate clinician review of caloric intake and antidiabetic regimen required.",
            )
        if c_val >= 200.0 or delta >= 30.0:
            return (
                "CONCERNING_CHANGE",
                "Glycemic Escalation",
                "high",
                formula,
                f"Blood glucose escalated significantly (+{delta} mg/dL to {c_val} mg/dL). Assess dietary intake, adherence, and HbA1c trajectory.",
            )
        if b_val >= 140.0 and delta <= -15.0 and c_val >= 70.0:
            return (
                "IMPROVING_TREND",
                "Glycemic Normalization",
                "normal",
                formula,
                f"Elevated baseline glucose reduced by {abs(delta)} mg/dL toward target reference range ({b_val} -> {c_val} mg/dL).",
            )
        if c_val >= 140.0 or delta >= 15.0:
            return (
                "MODERATE_SHIFT",
                "Moderate Elevation",
                "moderate",
                formula,
                f"Mild-to-moderate glycemic increase noted ({delta:+g} mg/dL). Follow up on dietary lifestyle.",
            )
        return (
            "STABLE_TREND",
            "Glycemic Stability",
            "normal",
            formula,
            f"Blood glucose remains within expected baseline range ({c_val} mg/dL, change: {delta:+g} mg/dL).",
        )

    if key == "systolic_bp":
        if c_val >= 160.0 or delta >= 25.0:
            return (
                "CONCERNING_CHANGE",
                "Hypertensive Escalation",
                "high",
                formula,
                f"Systolic blood pressure escalated markedly (+{delta} mmHg to {c_val} mmHg). Evaluate medication adherence and cardiovascular risk.",
            )
        if c_val < 90.0:
            return (
                "CONCERNING_CHANGE",
                "Hypotensive Shift",
                "high",
                formula,
                f"Systolic blood pressure declined to hypotensive levels ({c_val} mmHg). Assess for dehydration, sepsis, or medication overtreatment.",
            )
        if b_val >= 140.0 and delta <= -15.0 and c_val >= 90.0 and c_val <= 130.0:
            return (
                "IMPROVING_TREND",
                "Blood Pressure Normalization",
                "normal",
                formula,
                f"Elevated baseline systolic BP improved by {abs(delta)} mmHg toward target reference ({b_val} -> {c_val} mmHg).",
            )
        if delta <= -25.0:
            return (
                "CONCERNING_CHANGE",
                "Hypotensive Shift",
                "high",
                formula,
                f"Systolic blood pressure declined significantly ({delta} mmHg to {c_val} mmHg). Assess for dehydration, sepsis, or medication overtreatment.",
            )
        if c_val >= 140.0 or delta >= 15.0:
            return (
                "MODERATE_SHIFT",
                "Moderate Elevation",
                "moderate",
                formula,
                f"Mild systolic elevation observed above baseline ({delta:+g} mmHg). Ongoing tracking advised.",
            )
        return (
            "STABLE_TREND",
            "Blood Pressure Stable",
            "normal",
            formula,
            f"Systolic blood pressure is stable within target parameters ({c_val} mmHg, change: {delta:+g} mmHg).",
        )

    if key == "diastolic_bp":
        if c_val >= 100.0 or delta >= 15.0:
            return (
                "CONCERNING_CHANGE",
                "Diastolic Escalation",
                "high",
                formula,
                f"Diastolic blood pressure elevated (+{delta} mmHg to {c_val} mmHg). Review cardiovascular status.",
            )
        if c_val < 60.0:
            return (
                "CONCERNING_CHANGE",
                "Low Diastolic Pressure",
                "moderate",
                formula,
                f"Diastolic pressure is low ({c_val} mmHg, change: {delta:+g} mmHg). Check for orthostatic symptoms.",
            )
        if b_val >= 90.0 and delta <= -10.0 and c_val >= 60.0 and c_val <= 85.0:
            return (
                "IMPROVING_TREND",
                "Diastolic Normalization",
                "normal",
                formula,
                f"Elevated baseline diastolic BP decreased by {abs(delta)} mmHg toward reference target ({b_val} -> {c_val} mmHg).",
            )
        if delta <= -15.0:
            return (
                "CONCERNING_CHANGE",
                "Low Diastolic Pressure",
                "moderate",
                formula,
                f"Diastolic pressure declined significantly ({delta} mmHg to {c_val} mmHg). Check for orthostatic symptoms.",
            )
        return (
            "STABLE_TREND",
            "Diastolic Stable",
            "normal",
            formula,
            f"Diastolic blood pressure remains within expected variance ({c_val} mmHg).",
        )

    if key == "oxygen_saturation":
        if c_val < 92.0:
            return (
                "CONCERNING_CHANGE",
                "Hypoxia Concern",
                "high",
                formula,
                f"Oxygen saturation is critically low at {c_val}%. Prompt clinical evaluation of respiratory function and airway required.",
            )
        if delta <= -4.0:
            return (
                "CONCERNING_CHANGE",
                "Desaturation Drop",
                "high",
                formula,
                f"Oxygen saturation dropped by {abs(delta)}% from baseline ({b_val}% -> {c_val}%). Inquire about dyspnea, cough, or respiratory fatigue.",
            )
        if b_val < 95.0 and c_val >= 95.0:
            return (
                "IMPROVING_TREND",
                "Oxygenation Recovery",
                "normal",
                formula,
                f"Oxygen saturation recovered from low baseline ({b_val}%) to standard room-air levels ({c_val}%).",
            )
        return (
            "STABLE_TREND",
            "Oxygenation Normal",
            "normal",
            formula,
            f"Oxygen saturation is stable at {c_val}% (change: {delta:+g}%).",
        )

    if key == "heart_rate":
        if c_val > 110.0 or c_val < 50.0:
            return (
                "CONCERNING_CHANGE",
                "Rate Anomaly",
                "high",
                formula,
                f"Heart rate outside standard physiological limits ({c_val} bpm). Investigate arrhythmia, thyroid disease, or medication effects.",
            )
        if abs(delta) >= 20.0:
            return (
                "MODERATE_SHIFT",
                "Rate Variability",
                "moderate",
                formula,
                f"Heart rate changed by {delta:+g} bpm across visits ({b_val} -> {c_val} bpm). Check hydration, anxiety, or acute illness.",
            )
        if (b_val > 100.0 and c_val <= 85.0) or (b_val < 55.0 and c_val >= 65.0):
            return (
                "IMPROVING_TREND",
                "Heart Rate Normalization",
                "normal",
                formula,
                f"Resting heart rate normalized from baseline ({b_val} bpm -> {c_val} bpm).",
            )
        return (
            "STABLE_TREND",
            "Heart Rate Stable",
            "normal",
            formula,
            f"Resting heart rate remains within expected baseline range ({c_val} bpm).",
        )

    if key == "temperature":
        if c_val >= 38.0:
            return (
                "CONCERNING_CHANGE",
                "Pyrexia / Fever",
                "high",
                formula,
                f"Elevated body temperature recorded ({c_val} °C). Screen for infectious or inflammatory causes.",
            )
        if c_val < 35.5:
            return (
                "CONCERNING_CHANGE",
                "Hypothermic Shift",
                "moderate",
                formula,
                f"Body temperature subnormal ({c_val} °C). Confirm thermometer calibration and patient exposure.",
            )
        if b_val >= 38.0 and c_val <= 37.2:
            return (
                "IMPROVING_TREND",
                "Fever Defervescence",
                "normal",
                formula,
                f"Elevated baseline fever resolved ({b_val} °C -> {c_val} °C).",
            )
        return (
            "STABLE_TREND",
            "Afebrile / Stable",
            "normal",
            formula,
            f"Body temperature is stable at {c_val} °C.",
        )

    if key == "hemoglobin":
        if c_val < 11.0 or delta <= -2.0:
            return (
                "CONCERNING_CHANGE",
                "Anemia Progression",
                "high",
                formula,
                f"Hemoglobin is low or declining ({c_val} g/dL, change {delta:+g} g/dL). Screen for blood loss or nutritional deficiency.",
            )
        if b_val < 11.0 and delta >= 1.5:
            return (
                "IMPROVING_TREND",
                "Hemoglobin Recovery",
                "normal",
                formula,
                f"Hemoglobin improved by +{delta} g/dL toward standard target ({b_val} -> {c_val} g/dL).",
            )
        return (
            "STABLE_TREND",
            "Hemoglobin Stable",
            "normal",
            formula,
            f"Hemoglobin level is stable ({c_val} g/dL).",
        )

    if key == "weight":
        if abs(pct) >= 7.0:
            return (
                "CONCERNING_CHANGE",
                "Rapid Weight Change",
                "high",
                formula,
                f"Body weight shifted rapidly by {pct:+g}% ({delta:+g} kg). Rapid shifts may signal fluid retention or acute metabolic deficit.",
            )
        if abs(pct) >= 4.0:
            return (
                "MODERATE_SHIFT",
                "Weight Shift",
                "moderate",
                formula,
                f"Moderate weight shift of {delta:+g} kg ({pct:+g}%) observed across visits.",
            )
        return (
            "STABLE_TREND",
            "Weight Stable",
            "normal",
            formula,
            f"Body weight is stable ({c_val} kg, change: {delta:+g} kg).",
        )

    return (
        "STABLE_TREND",
        "Within Baseline",
        "normal",
        formula,
        f"{label} remains within expected baseline range.",
    )


def compute_health_trajectory(patient_id: int, db: Session) -> Optional[HealthTrajectoryResponse]:
    """
    Computes explainable multi-visit longitudinal clinical change detection
    grounded strictly in recorded facts, source visit IDs, dates, and validated delta math.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        return None

    # Retrieve all visits chronologically
    visits: List[Visit] = (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_date.asc(), Visit.id.asc())
        .all()
    )

    if not visits:
        summary = HealthTrajectorySummary(
            patient_id=patient.id,
            patient_name=patient.name,
            patient_code=patient.patient_code,
            total_visits_recorded=0,
            chronological_span="No recorded visits on file.",
            overall_trajectory_status="INSUFFICIENT_HISTORY",
            factual_trajectory_narrative=(
                f"Patient {patient.name} ({patient.patient_code}) has no recorded clinical visits in the system. "
                "Register an intake visit with baseline vital signs to initiate longitudinal change tracking."
            ),
            clinical_decision_support_notes=[
                "Perform intake clinical assessment.",
                "Record baseline physical measurements (BP, Heart Rate, Glucose, SpO2).",
            ],
        )
        empty_metrics = [
            TrajectoryMetric(
                key=m["key"],
                label=m["label"],
                unit=m["unit"],
                classification="DATA_GAP",
                classification_label="Unrecorded Data",
                severity_level="info",
                formula_breakdown="No measurements on file.",
                clinical_explanation=f"No {m['label'].lower()} measurements recorded.",
            )
            for m in METRIC_DEFINITIONS
        ]
        return HealthTrajectoryResponse(summary=summary, metrics=empty_metrics)

    # Fetch all measurements linked to this patient
    all_meas: List[ClinicalMeasurement] = (
        db.query(ClinicalMeasurement)
        .filter(ClinicalMeasurement.patient_id == patient_id)
        .order_by(ClinicalMeasurement.created_at.asc(), ClinicalMeasurement.id.asc())
        .all()
    )

    # Group measurements by visit_id to accurately detect duplicate or multiple readings
    meas_by_visit: Dict[int, List[ClinicalMeasurement]] = {}
    for m in all_meas:
        meas_by_visit.setdefault(m.visit_id, []).append(m)

    # Visits that contain recorded measurements
    visits_with_meas = [v for v in visits if v.id in meas_by_visit and len(meas_by_visit[v.id]) > 0]

    b_visit = visits_with_meas[0] if visits_with_meas else visits[0]
    l_visit = visits_with_meas[-1] if visits_with_meas else visits[-1]
    p_visit = visits_with_meas[-2] if len(visits_with_meas) >= 2 else None

    b_date = b_visit.visit_date
    l_date = l_visit.visit_date
    p_date = p_visit.visit_date if p_visit else None

    # Calculate chronological span
    if b_date == l_date:
        span_str = f"Single evaluation date ({l_date.isoformat()})"
    else:
        span_str = f"Spans {b_date.isoformat()} to {l_date.isoformat()} ({len(visits)} visits recorded)"

    if len(visits_with_meas) < 2:
        # Only 1 visit with measurements on file
        single_meas_list = meas_by_visit.get(l_visit.id, [])
        latest_meas = single_meas_list[-1] if single_meas_list else None

        single_warnings: List[str] = []
        if latest_meas and latest_meas.measured_at is None:
            single_warnings.append(
                f"Visit #{l_visit.id} ({l_visit.visit_date.isoformat()}): Intra-day measurement clock time is unrecorded; baseline readings are indexed by calendar visit date."
            )
        elif latest_meas and latest_meas.measured_at and latest_meas.measured_at.date() != l_visit.visit_date:
            single_warnings.append(
                f"Visit #{l_visit.id}: Measurement timestamp ({latest_meas.measured_at.date().isoformat()}) differs from visit date ({l_visit.visit_date.isoformat()}). Reconcile clinical records."
            )

        metrics: List[TrajectoryMetric] = []
        for defn in METRIC_DEFINITIONS:
            k = defn["key"]
            lbl = defn["label"]
            u = defn["unit"]
            val = getattr(latest_meas, k, None) if latest_meas else None

            warn = None
            if latest_meas:
                warn = check_timestamp_warning(latest_meas.measured_at, l_visit.visit_date)

            rp = None
            if latest_meas and val is not None:
                rp = ReadingPoint(
                    visit_id=l_visit.id,
                    visit_date=l_visit.visit_date,
                    value=float(val),
                    measured_at=latest_meas.measured_at.isoformat() if latest_meas.measured_at else None,
                    timestamp_warning=warn,
                    has_multiple_readings=len(single_meas_list) > 1,
                )

            data_quality_note = None
            if warn:
                data_quality_note = warn
            elif len(single_meas_list) > 1:
                data_quality_note = f"Multiple ({len(single_meas_list)}) readings recorded on visit #{l_visit.id}; used reading #{latest_meas.id}."

            metrics.append(
                TrajectoryMetric(
                    key=k,
                    label=lbl,
                    unit=u,
                    baseline_reading=rp,
                    latest_reading=rp,
                    classification="DATA_GAP" if val is None else "STABLE_TREND",
                    classification_label="Baseline Established" if val is not None else "Unrecorded Data",
                    severity_level="normal" if val is not None else "info",
                    formula_breakdown=f"Initial baseline: {val} {u} ({l_date})" if val is not None else "No measurement on file.",
                    clinical_explanation=(
                        f"Initial baseline reading of {val} {u} established on {l_date}. "
                        "A future follow-up visit is required to determine longitudinal trajectory."
                        if val is not None
                        else f"No {lbl.lower()} measurements recorded for this patient."
                    ),
                    data_quality_note=data_quality_note,
                )
            )

        summary = HealthTrajectorySummary(
            patient_id=patient.id,
            patient_name=patient.name,
            patient_code=patient.patient_code,
            total_visits_recorded=len(visits),
            chronological_span=span_str,
            baseline_visit_date=b_date,
            latest_visit_date=l_date,
            concerning_count=0,
            improving_count=0,
            stable_count=sum(1 for m in metrics if m.classification == "STABLE_TREND"),
            data_gaps_count=sum(1 for m in metrics if m.classification == "DATA_GAP"),
            overall_trajectory_status="INSUFFICIENT_HISTORY",
            factual_trajectory_narrative=(
                f"Patient {patient.name} ({patient.patient_code}) has 1 documented visit with physical measurements on {l_date.isoformat()}. "
                "Baseline clinical parameters have been established. Document a follow-up visit to evaluate longitudinal health changes."
            ),
            clinical_decision_support_notes=[
                "Schedule routine longitudinal follow-up.",
                "Obtain repeat vital signs on subsequent visit to establish clinical trajectory.",
            ],
            visit_quality_warnings=single_warnings,
        )
        return HealthTrajectoryResponse(summary=summary, metrics=metrics)

    # 2 or more visits with measurements exist
    b_meas_list = meas_by_visit[b_visit.id]
    l_meas_list = meas_by_visit[l_visit.id]
    p_meas_list = meas_by_visit[p_visit.id] if p_visit else []

    b_meas = b_meas_list[-1]
    l_meas = l_meas_list[-1]
    p_meas = p_meas_list[-1] if p_meas_list else None

    # Collect grouped visit-level quality warnings
    visit_warnings: List[str] = []
    missing_time_visits: List[str] = []

    if b_meas and b_meas.measured_at is None:
        missing_time_visits.append(f"Visit #{b_visit.id} ({b_visit.visit_date.isoformat()})")
    elif b_meas and b_meas.measured_at and b_meas.measured_at.date() != b_visit.visit_date:
        visit_warnings.append(
            f"Visit #{b_visit.id}: measurement timestamp ({b_meas.measured_at.date().isoformat()}) differs from recorded visit date ({b_visit.visit_date.isoformat()}). Reconcile source records."
        )

    if l_meas and l_meas.id != b_meas.id:
        if l_meas.measured_at is None:
            missing_time_visits.append(f"Visit #{l_visit.id} ({l_visit.visit_date.isoformat()})")
        elif l_meas.measured_at and l_meas.measured_at.date() != l_visit.visit_date:
            visit_warnings.append(
                f"Visit #{l_visit.id}: measurement timestamp ({l_meas.measured_at.date().isoformat()}) differs from recorded visit date ({l_visit.visit_date.isoformat()}). Reconcile source records."
            )

    if p_meas and p_meas.id not in (b_meas.id, l_meas.id):
        if p_meas.measured_at is None:
            missing_time_visits.append(f"Visit #{p_visit.id} ({p_visit.visit_date.isoformat()})")
        elif p_meas.measured_at and p_meas.measured_at.date() != p_visit.visit_date:
            visit_warnings.append(
                f"Visit #{p_visit.id}: measurement timestamp ({p_meas.measured_at.date().isoformat()}) differs from recorded visit date ({p_visit.visit_date.isoformat()}). Reconcile source records."
            )

    if missing_time_visits:
        joined_v = ", ".join(missing_time_visits)
        visit_warnings.insert(
            0,
            f"Measurement clock time is unrecorded for {joined_v}; clinical readings are sequenced by recorded calendar visit date."
        )

    metrics: List[TrajectoryMetric] = []
    concerning_count = 0
    improving_count = 0
    stable_count = 0
    data_gaps_count = 0
    notable_findings: List[str] = []

    for defn in METRIC_DEFINITIONS:
        k = defn["key"]
        lbl = defn["label"]
        u = defn["unit"]

        b_val = getattr(b_meas, k, None)
        l_val = getattr(l_meas, k, None)
        p_val = getattr(p_meas, k, None) if p_meas else None

        b_warn = check_timestamp_warning(b_meas.measured_at, b_visit.visit_date)
        l_warn = check_timestamp_warning(l_meas.measured_at, l_visit.visit_date)
        p_warn = check_timestamp_warning(p_meas.measured_at, p_visit.visit_date) if p_meas else None

        b_rp = ReadingPoint(
            visit_id=b_visit.id,
            visit_date=b_visit.visit_date,
            value=float(b_val) if b_val is not None else None,
            measured_at=b_meas.measured_at.isoformat() if b_meas.measured_at else None,
            timestamp_warning=b_warn,
            has_multiple_readings=len(b_meas_list) > 1,
        ) if b_val is not None else None

        l_rp = ReadingPoint(
            visit_id=l_visit.id,
            visit_date=l_visit.visit_date,
            value=float(l_val) if l_val is not None else None,
            measured_at=l_meas.measured_at.isoformat() if l_meas.measured_at else None,
            timestamp_warning=l_warn,
            has_multiple_readings=len(l_meas_list) > 1,
        ) if l_val is not None else None

        p_rp = ReadingPoint(
            visit_id=p_visit.id,
            visit_date=p_visit.visit_date,
            value=float(p_val) if p_val is not None else None,
            measured_at=p_meas.measured_at.isoformat() if p_meas and p_meas.measured_at else None,
            timestamp_warning=p_warn,
            has_multiple_readings=len(p_meas_list) > 1 if p_meas else False,
        ) if p_val is not None and p_visit else None

        delta_prev = round(l_val - p_val, 2) if (l_val is not None and p_val is not None) else None
        delta_base = round(l_val - b_val, 2) if (l_val is not None and b_val is not None) else None
        pct_base = round(((l_val - b_val) / b_val) * 100.0, 1) if (l_val is not None and b_val is not None and b_val != 0) else None

        has_any_warning = bool(b_warn or l_warn or (p_warn if p_visit else False))

        classification, class_label, severity, formula, reason = classify_metric_trajectory(
            key=k,
            label=lbl,
            unit=u,
            b_val=b_val,
            b_date=b_date,
            p_val=p_val,
            p_date=p_date,
            c_val=l_val,
            c_date=l_date,
            has_timestamp_warning=has_any_warning,
        )

        quality_notes = []
        if l_warn:
            quality_notes.append(f"Latest visit: {l_warn}")
        if len(l_meas_list) > 1:
            quality_notes.append(f"Multiple ({len(l_meas_list)}) readings recorded on latest visit; used reading #{l_meas.id}.")

        if classification == "CONCERNING_CHANGE":
            concerning_count += 1
            if delta_base is not None:
                notable_findings.append(f"{lbl} shifted {delta_base:+g} {u} ({class_label})")
        elif classification == "IMPROVING_TREND":
            improving_count += 1
            if delta_base is not None:
                notable_findings.append(f"{lbl} improved {delta_base:+g} {u} ({class_label})")
        elif classification == "STABLE_TREND":
            stable_count += 1
        elif classification == "DATA_GAP":
            data_gaps_count += 1

        metrics.append(
            TrajectoryMetric(
                key=k,
                label=lbl,
                unit=u,
                baseline_reading=b_rp,
                previous_reading=p_rp,
                latest_reading=l_rp,
                delta_from_previous=delta_prev,
                delta_from_baseline=delta_base,
                percent_change_from_baseline=pct_base,
                classification=classification,
                classification_label=class_label,
                severity_level=severity,
                formula_breakdown=formula,
                clinical_explanation=reason,
                data_quality_note="; ".join(quality_notes) if quality_notes else None,
            )
        )

    # Determine overall status
    if concerning_count >= 1:
        overall_status = "ATTENTION_REQUIRED"
    elif improving_count >= 1:
        overall_status = "STABILIZING_TRAJECTORY"
    else:
        overall_status = "STABLE_MAINTENANCE"

    # Build factual grounded narrative
    findings_str = "; ".join(notable_findings) if notable_findings else "all measured parameters demonstrate baseline stability"
    narrative = (
        f"Patient {patient.name} ({patient.patient_code}) has {len(visits)} visits on record spanning {b_date.isoformat()} to {l_date.isoformat()}. "
        f"Longitudinal trajectory comparison reveals {concerning_count} concerning shift(s), {improving_count} improving trend(s), "
        f"{stable_count} stable metric(s), and {data_gaps_count} data gap(s). Primary shifts: {findings_str}."
    )

    action_notes = []
    if any(m.key in ("systolic_bp", "diastolic_bp") and m.classification == "CONCERNING_CHANGE" for m in metrics):
        action_notes.append("Prioritize cardiovascular review and medication adherence check.")
    if any(m.key == "oxygen_saturation" and m.classification == "CONCERNING_CHANGE" for m in metrics):
        action_notes.append("Evaluate airway patency, dyspnea, and respiratory symptoms immediately.")
    if any(m.key == "blood_glucose" and m.classification == "CONCERNING_CHANGE" for m in metrics):
        action_notes.append("Assess glycemic management, fasting adherence, and arrange HbA1c review.")
    if any(m.classification == "IMPROVING_TREND" for m in metrics):
        action_notes.append("Document positive clinical response to ongoing care regimen.")
    if data_gaps_count > 0:
        action_notes.append(f"Complete {data_gaps_count} omitted measurement(s) during subsequent clinic visits.")
    if not action_notes:
        action_notes.append("Continue current longitudinal management plan and scheduled follow-up visits.")

    summary = HealthTrajectorySummary(
        patient_id=patient.id,
        patient_name=patient.name,
        patient_code=patient.patient_code,
        total_visits_recorded=len(visits),
        chronological_span=span_str,
        baseline_visit_date=b_date,
        latest_visit_date=l_date,
        concerning_count=concerning_count,
        improving_count=improving_count,
        stable_count=stable_count,
        data_gaps_count=data_gaps_count,
        overall_trajectory_status=overall_status,
        factual_trajectory_narrative=narrative,
        clinical_decision_support_notes=action_notes,
        visit_quality_warnings=visit_warnings,
    )

    return HealthTrajectoryResponse(summary=summary, metrics=metrics)
