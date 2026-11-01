"""
CareTrack AI — HealthTrajectory AI Automated Test Suite

Tests:
1. Anonymous request rejection with HTTP 401 Unauthorized on /patients/{id}/health-trajectory.
2. Non-existent patient rejection with HTTP 404 Not Found.
3. Insufficient history handling (0 visits and 1 visit with measurements).
4. Concerning change detection (increasing glucose +105 mg/dL, systolic BP +45 mmHg, SpO2 drop to 90%).
5. Improving trend detection (normalizing elevated systolic BP 155 -> 118 mmHg, glucose 160 -> 95 mg/dL).
6. Stable trajectory detection (parameters within baseline physiological variance).
7. Missing data & data gap detection (metric omitted on follow-up visit).
8. Data inconsistency detection (timestamp discrepancy between measured_at and visit_date).
9. Multiple readings on single visit handling (has_multiple_readings flagged, latest used).
10. Source visit attribution & exact transparent delta calculations.
11. Clinician-supervised decision support disclaimer presence.

Zero live database writes are performed. Tests run on an isolated in-memory SQLite engine.
"""

from datetime import date, datetime
import sys
from pathlib import Path

# Configure stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import BigInteger, Integer
from sqlalchemy.ext.compiler import compiles

# Map BigInteger to INTEGER in SQLite so autoincrement PKs function in test memory
@compiles(BigInteger, "sqlite")
def compile_big_int_sqlite(type_, compiler, **kw):
    return "INTEGER"

from app.database import Base, get_db
from app.main import app
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.clinical_measurement import ClinicalMeasurement
from app.models.user import User
from app.security import hash_password, create_access_token

# Setup isolated in-memory SQLite engine
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    expire_on_commit=False,
)
Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

print("=" * 75)
print("CARETRACK AI — HEALTHTRAJECTORY AI AUTOMATED TEST SUITE")
print("=" * 75)

# Seed Doctor account
db = TestingSessionLocal()
doctor = User(
    username="dr_trajectory_lead",
    email="dr_traj@caretrack.org",
    hashed_password=hash_password("TrajSecurePass2026!"),
    full_name="Dr. Longitudinal Trajectory",
    role="doctor",
    is_active=True,
)
db.add(doctor)
db.commit()
db.refresh(doctor)
doc_token = create_access_token(subject=doctor.id, role="doctor")
auth_headers = {"Authorization": f"Bearer {doc_token}"}
db.close()

# -------------------------------------------------------------------
# 1. Anonymous Access Rejection (401 Unauthorized)
# -------------------------------------------------------------------
print("\n[TEST 1] Anonymous Access Rejection (401)...")
anon_resp = client.get("/patients/1/health-trajectory")
assert anon_resp.status_code == 401, f"Expected 401, got {anon_resp.status_code}"
assert anon_resp.json()["detail"] == "Authentication token is missing."
print("  [PASS] Anonymous GET /patients/1/health-trajectory blocked with 401 Unauthorized.")

# -------------------------------------------------------------------
# 2. Non-Existent Patient (404 Not Found)
# -------------------------------------------------------------------
print("\n[TEST 2] Non-Existent Patient Rejection (404)...")
resp_404 = client.get("/patients/99999/health-trajectory", headers=auth_headers)
assert resp_404.status_code == 404
assert resp_404.json()["detail"] == "Patient not found."
print("  [PASS] Non-existent patient properly returned HTTP 404 Not Found.")

# -------------------------------------------------------------------
# 3. Insufficient History Handling (0 visits and 1 visit)
# -------------------------------------------------------------------
print("\n[TEST 3] Insufficient History Handling (0 and 1 Visit)...")
db = TestingSessionLocal()

# Patient A: 0 visits
pat_a = Patient(
    patient_code="TRAJ-000",
    name="Ravi NoVisits",
    age=35,
    gender="Male",
    phone="555-0101",
    location="Chennai",
)
# Patient B: 1 visit only
pat_b = Patient(
    patient_code="TRAJ-001",
    name="Meera SingleVisit",
    age=48,
    gender="Female",
    phone="555-0102",
    location="Madurai",
)
db.add_all([pat_a, pat_b])
db.commit()
db.refresh(pat_a)
db.refresh(pat_b)

# Add single visit and measurement for Patient B
v_b = Visit(
    patient_id=pat_b.id,
    visit_date=date(2026, 8, 10),
    symptoms="Intake checkup",
    clinical_notes="Baseline vital signs recorded",
)
db.add(v_b)
db.commit()
db.refresh(v_b)

m_b = ClinicalMeasurement(
    patient_id=pat_b.id,
    visit_id=v_b.id,
    blood_pressure="122/82",
    systolic_bp=122,
    diastolic_bp=82,
    blood_glucose=98.0,
    heart_rate=72.0,
    oxygen_saturation=98.0,
    measured_at=datetime(2026, 8, 10, 9, 30),
)
db.add(m_b)
db.commit()
db.close()

# Test Patient A (0 visits)
resp_a = client.get(f"/patients/{pat_a.id}/health-trajectory", headers=auth_headers)
assert resp_a.status_code == 200
data_a = resp_a.json()
assert data_a["summary"]["overall_trajectory_status"] == "INSUFFICIENT_HISTORY"
assert data_a["summary"]["total_visits_recorded"] == 0
assert "no recorded clinical visits" in data_a["summary"]["factual_trajectory_narrative"].lower()
print("  [PASS] 0-visit patient handled safely with INSUFFICIENT_HISTORY status.")

# Test Patient B (1 visit with baseline established)
resp_b = client.get(f"/patients/{pat_b.id}/health-trajectory", headers=auth_headers)
assert resp_b.status_code == 200
data_b = resp_b.json()
assert data_b["summary"]["overall_trajectory_status"] == "INSUFFICIENT_HISTORY"
assert data_b["summary"]["total_visits_recorded"] == 1
glucose_b = next(m for m in data_b["metrics"] if m["key"] == "blood_glucose")
assert glucose_b["classification_label"] == "Baseline Established"
assert glucose_b["baseline_reading"]["value"] == 98.0
print("  [PASS] 1-visit patient accurately flagged as Baseline Established without guessing trajectory.")

# -------------------------------------------------------------------
# 4. Concerning Change Trajectory (Increasing / Escalating Risk)
# -------------------------------------------------------------------
print("\n[TEST 4] Concerning Change Trajectory (Escalating Glucose, BP & Hypoxia)...")
db = TestingSessionLocal()
pat_c = Patient(
    patient_code="TRAJ-CONC-01",
    name="Suresh Concern",
    age=55,
    gender="Male",
    phone="555-0103",
    location="Coimbatore",
)
db.add(pat_c)
db.commit()
db.refresh(pat_c)

# Visit 1: Baseline normal readings
v_c1 = Visit(
    patient_id=pat_c.id,
    visit_date=date(2026, 7, 1),
    symptoms="Routine checkup",
)
# Visit 2: Followup with marked deterioration
v_c2 = Visit(
    patient_id=pat_c.id,
    visit_date=date(2026, 9, 15),
    symptoms="Shortness of breath, fatigue",
)
db.add_all([v_c1, v_c2])
db.commit()
db.refresh(v_c1)
db.refresh(v_c2)

m_c1 = ClinicalMeasurement(
    patient_id=pat_c.id,
    visit_id=v_c1.id,
    blood_pressure="120/80",
    systolic_bp=120,
    diastolic_bp=80,
    blood_glucose=105.0,
    heart_rate=74.0,
    oxygen_saturation=98.0,
    measured_at=datetime(2026, 7, 1, 10, 0),
)
m_c2 = ClinicalMeasurement(
    patient_id=pat_c.id,
    visit_id=v_c2.id,
    blood_pressure="165/102",
    systolic_bp=165,
    diastolic_bp=102,
    blood_glucose=210.0,
    heart_rate=112.0,
    oxygen_saturation=90.0,
    measured_at=datetime(2026, 9, 15, 11, 0),
)
db.add_all([m_c1, m_c2])
db.commit()
db.close()

resp_c = client.get(f"/patients/{pat_c.id}/health-trajectory", headers=auth_headers)
assert resp_c.status_code == 200
data_c = resp_c.json()

assert data_c["summary"]["overall_trajectory_status"] == "ATTENTION_REQUIRED"
assert data_c["summary"]["concerning_count"] >= 3

# Check Blood Glucose: 105 -> 210 (+105 mg/dL)
glucose_c = next(m for m in data_c["metrics"] if m["key"] == "blood_glucose")
assert glucose_c["classification"] == "CONCERNING_CHANGE"
assert glucose_c["delta_from_baseline"] == 105.0
assert glucose_c["percent_change_from_baseline"] == 100.0
assert "Glycemic Escalation" in glucose_c["classification_label"]
assert glucose_c["baseline_reading"]["visit_id"] == v_c1.id
assert glucose_c["latest_reading"]["visit_id"] == v_c2.id

# Check Systolic BP: 120 -> 165 (+45 mmHg)
sys_c = next(m for m in data_c["metrics"] if m["key"] == "systolic_bp")
assert sys_c["classification"] == "CONCERNING_CHANGE"
assert sys_c["delta_from_baseline"] == 45.0
assert "Hypertensive Escalation" in sys_c["classification_label"]

# Check Oxygen Saturation: 98 -> 90 (-8%)
spo2_c = next(m for m in data_c["metrics"] if m["key"] == "oxygen_saturation")
assert spo2_c["classification"] == "CONCERNING_CHANGE"
assert spo2_c["delta_from_baseline"] == -8.0
assert "Hypoxia Concern" in spo2_c["classification_label"]
print("  [PASS] Concerning shifts (Glucose +105, Systolic +45, SpO2 90%) correctly detected and attributed.")

# -------------------------------------------------------------------
# 5. Improving Trend Trajectory (Decreasing / Normalizing toward Target)
# -------------------------------------------------------------------
print("\n[TEST 5] Improving Trend Trajectory (Elevated Baseline Normalizing)...")
db = TestingSessionLocal()
pat_d = Patient(
    patient_code="TRAJ-IMP-02",
    name="Lakshmi Recovery",
    age=52,
    gender="Female",
    phone="555-0104",
    location="Tiruchirappalli",
)
db.add(pat_d)
db.commit()
db.refresh(pat_d)

v_d1 = Visit(
    patient_id=pat_d.id,
    visit_date=date(2026, 6, 1),
    symptoms="Headaches, elevated BP diagnosed",
)
v_d2 = Visit(
    patient_id=pat_d.id,
    visit_date=date(2026, 8, 15),
    symptoms="Symptoms resolved, diet modified",
)
db.add_all([v_d1, v_d2])
db.commit()
db.refresh(v_d1)
db.refresh(v_d2)

# Elevated baseline vitals that normalize on visit 2
m_d1 = ClinicalMeasurement(
    patient_id=pat_d.id,
    visit_id=v_d1.id,
    blood_pressure="155/95",
    systolic_bp=155,
    diastolic_bp=95,
    blood_glucose=160.0,
    heart_rate=88.0,
    oxygen_saturation=97.0,
    measured_at=datetime(2026, 6, 1, 9, 0),
)
m_d2 = ClinicalMeasurement(
    patient_id=pat_d.id,
    visit_id=v_d2.id,
    blood_pressure="118/76",
    systolic_bp=118,
    diastolic_bp=76,
    blood_glucose=95.0,
    heart_rate=72.0,
    oxygen_saturation=99.0,
    measured_at=datetime(2026, 8, 15, 10, 0),
)
db.add_all([m_d1, m_d2])
db.commit()
db.close()

resp_d = client.get(f"/patients/{pat_d.id}/health-trajectory", headers=auth_headers)
assert resp_d.status_code == 200
data_d = resp_d.json()

assert data_d["summary"]["overall_trajectory_status"] == "STABILIZING_TRAJECTORY"
assert data_d["summary"]["improving_count"] >= 2
assert data_d["summary"]["concerning_count"] == 0

# Check Systolic BP: 155 -> 118 (-37 mmHg) -> IMPROVING_TREND (Normalization)
sys_d = next(m for m in data_d["metrics"] if m["key"] == "systolic_bp")
assert sys_d["classification"] == "IMPROVING_TREND"
assert sys_d["delta_from_baseline"] == -37.0
assert "Normalization" in sys_d["classification_label"]

# Check Glucose: 160 -> 95 (-65 mg/dL) -> IMPROVING_TREND
glucose_d = next(m for m in data_d["metrics"] if m["key"] == "blood_glucose")
assert glucose_d["classification"] == "IMPROVING_TREND"
assert glucose_d["delta_from_baseline"] == -65.0
print("  [PASS] Normalized blood pressure and glucose correctly classified as IMPROVING_TREND.")

# -------------------------------------------------------------------
# 6. Stable Maintenance Trajectory
# -------------------------------------------------------------------
print("\n[TEST 6] Stable Maintenance Trajectory...")
db = TestingSessionLocal()
pat_e = Patient(
    patient_code="TRAJ-STAB-03",
    name="Gopal Stable",
    age=40,
    gender="Male",
    phone="555-0105",
    location="Salem",
)
db.add(pat_e)
db.commit()
db.refresh(pat_e)

v_e1 = Visit(patient_id=pat_e.id, visit_date=date(2026, 5, 1))
v_e2 = Visit(patient_id=pat_e.id, visit_date=date(2026, 10, 1))
db.add_all([v_e1, v_e2])
db.commit()
db.refresh(v_e1)
db.refresh(v_e2)

m_e1 = ClinicalMeasurement(
    patient_id=pat_e.id,
    visit_id=v_e1.id,
    blood_pressure="118/76",
    systolic_bp=118,
    diastolic_bp=76,
    blood_glucose=92.0,
    heart_rate=72.0,
    oxygen_saturation=98.0,
    temperature=36.6,
    weight=68.0,
    measured_at=datetime(2026, 5, 1, 9, 30),
)
m_e2 = ClinicalMeasurement(
    patient_id=pat_e.id,
    visit_id=v_e2.id,
    blood_pressure="120/78",
    systolic_bp=120,
    diastolic_bp=78,
    blood_glucose=95.0,
    heart_rate=70.0,
    oxygen_saturation=98.0,
    temperature=36.7,
    weight=68.2,
    measured_at=datetime(2026, 10, 1, 9, 30),
)
db.add_all([m_e1, m_e2])
db.commit()
db.close()

resp_e = client.get(f"/patients/{pat_e.id}/health-trajectory", headers=auth_headers)
assert resp_e.status_code == 200
data_e = resp_e.json()
assert data_e["summary"]["overall_trajectory_status"] == "STABLE_MAINTENANCE"
assert data_e["summary"]["stable_count"] >= 7
print("  [PASS] Stable patient measurements correctly classified as STABLE_MAINTENANCE.")

# -------------------------------------------------------------------
# 7. Missing Data & Data Gap Detection
# -------------------------------------------------------------------
print("\n[TEST 7] Missing Data & Data Gap Detection...")
db = TestingSessionLocal()
pat_f = Patient(
    patient_code="TRAJ-GAP-04",
    name="Devi DataGap",
    age=39,
    gender="Female",
    phone="555-0106",
    location="Vellore",
)
db.add(pat_f)
db.commit()
db.refresh(pat_f)

v_f1 = Visit(patient_id=pat_f.id, visit_date=date(2026, 4, 1))
v_f2 = Visit(patient_id=pat_f.id, visit_date=date(2026, 9, 1))
db.add_all([v_f1, v_f2])
db.commit()
db.refresh(v_f1)
db.refresh(v_f2)

# Weight recorded on visit 1, omitted on visit 2
m_f1 = ClinicalMeasurement(
    patient_id=pat_f.id,
    visit_id=v_f1.id,
    blood_pressure="120/80",
    systolic_bp=120,
    diastolic_bp=80,
    weight=72.0,
    measured_at=datetime(2026, 4, 1, 10, 0),
)
m_f2 = ClinicalMeasurement(
    patient_id=pat_f.id,
    visit_id=v_f2.id,
    blood_pressure="122/82",
    systolic_bp=122,
    diastolic_bp=82,
    weight=None,  # Omitted on visit 2
    measured_at=datetime(2026, 9, 1, 10, 0),
)
db.add_all([m_f1, m_f2])
db.commit()
db.close()

resp_f = client.get(f"/patients/{pat_f.id}/health-trajectory", headers=auth_headers)
assert resp_f.status_code == 200
data_f = resp_f.json()
weight_f = next(m for m in data_f["metrics"] if m["key"] == "weight")
assert weight_f["classification"] == "DATA_GAP"
assert weight_f["classification_label"] == "Missing Current Reading"
assert weight_f["baseline_reading"]["value"] == 72.0
assert weight_f["latest_reading"] is None
print("  [PASS] Omitted measurement flagged as DATA_GAP (Missing Current Reading) without assumption.")

# -------------------------------------------------------------------
# 8. Data Inconsistency (Timestamp Discrepancy) & Multiple Readings
# -------------------------------------------------------------------
print("\n[TEST 8] Data Inconsistency & Multiple Readings Detection...")
db = TestingSessionLocal()
pat_g = Patient(
    patient_code="TRAJ-INCON-05",
    name="Arjun Inconsistent",
    age=60,
    gender="Male",
    phone="555-0107",
    location="Erode",
)
db.add(pat_g)
db.commit()
db.refresh(pat_g)

# Visit date is 2026-09-01, but measurement measured_at is 2026-09-03
v_g1 = Visit(patient_id=pat_g.id, visit_date=date(2026, 8, 1))
v_g2 = Visit(patient_id=pat_g.id, visit_date=date(2026, 9, 1))
db.add_all([v_g1, v_g2])
db.commit()
db.refresh(v_g1)
db.refresh(v_g2)

m_g1 = ClinicalMeasurement(
    patient_id=pat_g.id,
    visit_id=v_g1.id,
    systolic_bp=120,
    measured_at=datetime(2026, 8, 1, 10, 0),
)
# Reading 1 on visit 2
m_g2_1 = ClinicalMeasurement(
    patient_id=pat_g.id,
    visit_id=v_g2.id,
    systolic_bp=135,
    measured_at=datetime(2026, 9, 3, 11, 0),  # Differing date from visit_date
)
# Reading 2 on visit 2 (multiple readings on same visit)
m_g2_2 = ClinicalMeasurement(
    patient_id=pat_g.id,
    visit_id=v_g2.id,
    systolic_bp=132,
    measured_at=datetime(2026, 9, 3, 11, 30),
)
db.add_all([m_g1, m_g2_1, m_g2_2])
db.commit()
db.close()

resp_g = client.get(f"/patients/{pat_g.id}/health-trajectory", headers=auth_headers)
assert resp_g.status_code == 200
data_g = resp_g.json()

sys_g = next(m for m in data_g["metrics"] if m["key"] == "systolic_bp")
assert sys_g["latest_reading"]["has_multiple_readings"] is True
assert sys_g["latest_reading"]["timestamp_warning"] is not None
assert "differs from recorded visit date" in sys_g["latest_reading"]["timestamp_warning"]
assert "Multiple" in sys_g["data_quality_note"]
print("  [PASS] Timestamp discrepancy and multiple visit readings transparently reported.")

# -------------------------------------------------------------------
# 9. Clinician Decision Support Disclaimers
# -------------------------------------------------------------------
print("\n[TEST 9] Clinician Decision Support Disclaimers...")
assert "Clinical decision support only" in data_g["disclaimer"]
assert "Not an autonomous diagnosis" in data_g["disclaimer"]
assert "qualified healthcare professional" in data_g["disclaimer"].lower()
print("  [PASS] Mandatory non-diagnostic regulatory disclaimer verified.")

print("\n" + "=" * 75)
print("ALL HEALTHTRAJECTORY AI AUTOMATED TESTS PASSED (100% SUCCESS)!")
print("=" * 75)
