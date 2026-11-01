"""
CareTrack AI — Phase 3 End-to-End Automated Integration Test Suite

Verifies all primary workflows using FastAPI TestClient and an isolated
in-memory SQLite database. Zero reads or writes touch Supabase.
External AI calls (Gemini) are deterministically mocked.

Workflows Covered:
1. Authentication & Session Validation (Doctor Login, /auth/me, invalid credentials)
2. Patient Registration, Retrieval, and List
3. Chronological Visit Creation
4. Clinical Measurement Submission (multi-visit vitals)
5. Patient Longitudinal Timeline
6. Clinical Trends (multi-point trajectory)
7. Health Change Radar (baseline vs current delta calculation)
8. Clinical Alerts & Urgency Queue Overview
9. AI Clinical Copilot (context grounding & decision-support prompt verification)
10. Medical Report Workflow (upload, OCR extraction, measurement confirmation, file download)
11. Longitudinal Patient History PDF Export
"""

import io
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Configure stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.clinical_measurement import ClinicalMeasurement
from app.models.medical_report import MedicalReport
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.security import hash_password

from sqlalchemy import BigInteger, Integer
from sqlalchemy.ext.compiler import compiles

# Map BigInteger to INTEGER in SQLite so autoincrement primary keys function properly in test memory
@compiles(BigInteger, "sqlite")
def compile_big_int_sqlite(type_, compiler, **kw):
    return "INTEGER"

# ---------------------------------------------------------------------------
# 1. SETUP ISOLATED IN-MEMORY DATABASE & DEPENDENCY OVERRIDE
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
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
print("CARETRACK AI — PHASE 3 END-TO-END AUTOMATED INTEGRATION TESTS")
print("=" * 75)

# Seed Doctor account in isolated database
db = TestingSessionLocal()
doctor_password = "DoctorPhase3Secure2026!"
doctor = User(
    username="dr_e2e_lead",
    email="dr_e2e@caretrack.org",
    hashed_password=hash_password(doctor_password),
    full_name="Dr. E2E Clinician",
    role="doctor",
    is_active=True,
)
db.add(doctor)
db.commit()
db.refresh(doctor)
db.close()

# ---------------------------------------------------------------------------
# TEST 1: AUTHENTICATION & SESSION VALIDATION
# ---------------------------------------------------------------------------
print("\n[TEST 1] Authentication & Doctor Session Validation...")

# 1a. Successful Login
login_resp = client.post(
    "/auth/login",
    data={"username": "dr_e2e_lead", "password": doctor_password},
)
assert login_resp.status_code == 200, f"Login failed: {login_resp.status_code} - {login_resp.text}"
login_data = login_resp.json()
assert "access_token" in login_data, "Missing access_token in login response"
assert login_data["token_type"] == "bearer", "Token type must be bearer"
assert login_data["user"]["role"] == "doctor", f"Expected doctor role, got {login_data['user']['role']}"
assert login_data["user"]["username"] == "dr_e2e_lead"
print("  [PASS] Doctor login succeeded with valid JWT and profile payload.")

auth_token = login_data["access_token"]
auth_headers = {"Authorization": f"Bearer {auth_token}"}

# 1b. Verify /auth/me
me_resp = client.get("/auth/me", headers=auth_headers)
assert me_resp.status_code == 200
assert me_resp.json()["username"] == "dr_e2e_lead"
assert me_resp.json()["role"] == "doctor"
print("  [PASS] /auth/me returns authenticated doctor identity.")

# 1c. Invalid login attempt
bad_login = client.post(
    "/auth/login",
    data={"username": "dr_e2e_lead", "password": "WrongPassword123!"},
)
assert bad_login.status_code == 401
assert bad_login.json()["detail"] == "Incorrect username or password."
print("  [PASS] Invalid login credentials safely rejected with HTTP 401.")

# ---------------------------------------------------------------------------
# TEST 2: PATIENT REGISTRATION & RETRIEVAL
# ---------------------------------------------------------------------------
print("\n[TEST 2] Patient Registration & Retrieval Workflow...")

patient_payload = {
    "patient_code": "E2E-PAT-001",
    "name": "Ananya Roy",
    "age": 42,
    "gender": "Female",
    "phone": "+91 9876543210",
    "location": "North Community Clinic",
}

create_pat_resp = client.post("/patients/", json=patient_payload, headers=auth_headers)
assert create_pat_resp.status_code == 201, f"Create patient failed: {create_pat_resp.text}"
created_patient = create_pat_resp.json()
patient_id = created_patient["id"]
assert created_patient["patient_code"] == "E2E-PAT-001"
assert created_patient["name"] == "Ananya Roy"
assert created_patient["age"] == 42
assert created_patient["gender"] == "Female"
print(f"  [PASS] Patient registered successfully with ID #{patient_id}.")

# Retrieve by ID
get_pat_resp = client.get(f"/patients/{patient_id}", headers=auth_headers)
assert get_pat_resp.status_code == 200
assert get_pat_resp.json()["id"] == patient_id
assert get_pat_resp.json()["name"] == "Ananya Roy"
print("  [PASS] Patient details retrieval verified.")

# Retrieve all patients
list_pat_resp = client.get("/patients/", headers=auth_headers)
assert list_pat_resp.status_code == 200
patients_list = list_pat_resp.json()
assert any(p["id"] == patient_id for p in patients_list)
print(f"  [PASS] Patient list query verified (contains #{patient_id}).")

# Duplicate patient code rejection
dup_pat_resp = client.post("/patients/", json=patient_payload, headers=auth_headers)
assert dup_pat_resp.status_code == 409
assert "already registered" in dup_pat_resp.json()["detail"]
print("  [PASS] Duplicate patient code properly rejected with HTTP 409 Conflict.")

# ---------------------------------------------------------------------------
# TEST 3: CHRONOLOGICAL VISIT CREATION
# ---------------------------------------------------------------------------
print("\n[TEST 3] Chronological Visit Creation...")

# Visit 1: Initial evaluation
visit1_resp = client.post(
    "/visits/",
    json={
        "patient_id": patient_id,
        "visit_date": "2026-09-01",
        "symptoms": "Occasional headaches, mild dizziness upon standing",
        "clinical_notes": "Initial consultation. Baseline vitals recorded.",
        "follow_up_notes": "Follow-up in 6 weeks with lab work.",
    },
    headers=auth_headers,
)
assert visit1_resp.status_code == 201, f"Visit 1 creation failed: {visit1_resp.text}"
visit1_id = visit1_resp.json()["id"]
assert visit1_resp.json()["visit_date"] == "2026-09-01"
print(f"  [PASS] Visit 1 created (ID #{visit1_id}, Date: 2026-09-01).")

# Visit 2: Follow-up evaluation
visit2_resp = client.post(
    "/visits/",
    json={
        "patient_id": patient_id,
        "visit_date": "2026-10-15",
        "symptoms": "Headaches resolved, energy level improved",
        "clinical_notes": "Progress checkup. Dietary adjustments noted.",
        "follow_up_notes": "Routine annual follow-up.",
    },
    headers=auth_headers,
)
assert visit2_resp.status_code == 201, f"Visit 2 creation failed: {visit2_resp.text}"
visit2_id = visit2_resp.json()["id"]
assert visit2_resp.json()["visit_date"] == "2026-10-15"
print(f"  [PASS] Visit 2 created (ID #{visit2_id}, Date: 2026-10-15).")

# Verify visits list by patient
visits_resp = client.get(f"/visits/patient/{patient_id}", headers=auth_headers)
assert visits_resp.status_code == 200
visits_list = visits_resp.json()
assert len(visits_list) == 2
# Note: get_patient_visits returns newest first (Visit.visit_date.desc())
assert visits_list[0]["id"] == visit2_id
assert visits_list[1]["id"] == visit1_id
print("  [PASS] Patient visits retrieved (ordered newest first as specified by endpoint).")

# ---------------------------------------------------------------------------
# TEST 4: CLINICAL MEASUREMENT SUBMISSION
# ---------------------------------------------------------------------------
print("\n[TEST 4] Clinical Measurement Submission (Multi-Visit Vitals)...")

# Measurements for Visit 1 (Baseline: elevated BP & glucose)
m1_payload = {
    "patient_id": patient_id,
    "visit_id": visit1_id,
    "blood_pressure": "142/90",
    "systolic_bp": 142,
    "diastolic_bp": 90,
    "blood_glucose": 140.0,
    "heart_rate": 82.0,
    "temperature": 37.1,
    "oxygen_saturation": 97.0,
    "weight": 68.5,
    "measured_at": "2026-09-01T10:15:00",
}
m1_resp = client.post("/clinical-measurements/", json=m1_payload, headers=auth_headers)
assert m1_resp.status_code == 201, f"Measurement 1 submission failed: {m1_resp.text}"
m1_id = m1_resp.json()["id"]
assert m1_resp.json()["systolic_bp"] == 142
assert m1_resp.json()["blood_glucose"] == 140.0
print(f"  [PASS] Visit 1 measurements recorded (ID #{m1_id}: BP 142/90, Glucose 140 mg/dL).")

# Measurements for Visit 2 (Follow-up: normalized BP & glucose)
m2_payload = {
    "patient_id": patient_id,
    "visit_id": visit2_id,
    "blood_pressure": "120/80",
    "systolic_bp": 120,
    "diastolic_bp": 80,
    "blood_glucose": 105.0,
    "heart_rate": 72.0,
    "temperature": 36.8,
    "oxygen_saturation": 99.0,
    "weight": 67.0,
    "measured_at": "2026-10-15T11:30:00",
}
m2_resp = client.post("/clinical-measurements/", json=m2_payload, headers=auth_headers)
assert m2_resp.status_code == 201, f"Measurement 2 submission failed: {m2_resp.text}"
m2_id = m2_resp.json()["id"]
assert m2_resp.json()["systolic_bp"] == 120
assert m2_resp.json()["blood_glucose"] == 105.0
print(f"  [PASS] Visit 2 measurements recorded (ID #{m2_id}: BP 120/80, Glucose 105 mg/dL).")

# Verify duplicate measurement prevention (HTTP 409 Conflict)
dup_meas_resp = client.post("/clinical-measurements/", json=m1_payload, headers=auth_headers)
assert dup_meas_resp.status_code == 409
assert "already been recorded" in dup_meas_resp.json()["detail"]
print("  [PASS] Repeated duplicate measurement submission rejected with HTTP 409 Conflict.")

# ---------------------------------------------------------------------------
# TEST 5: LONGITUDINAL PATIENT TIMELINE
# ---------------------------------------------------------------------------
print("\n[TEST 5] Longitudinal Patient Timeline Workflow...")

timeline_resp = client.get(f"/patients/{patient_id}/timeline", headers=auth_headers)
assert timeline_resp.status_code == 200, f"Timeline failed: {timeline_resp.text}"
tl_data = timeline_resp.json()
assert tl_data["patient_id"] == patient_id
assert tl_data["name"] == "Ananya Roy"
assert len(tl_data["visits"]) == 2
# Verify chronological structure
first_visit = tl_data["visits"][0]
assert first_visit["visit_date"] == "2026-09-01"
assert len(first_visit["measurements"]) == 1
assert first_visit["measurements"][0]["systolic_bp"] == 142

second_visit = tl_data["visits"][1]
assert second_visit["visit_date"] == "2026-10-15"
assert len(second_visit["measurements"]) == 1
assert second_visit["measurements"][0]["systolic_bp"] == 120
print(f"  [PASS] Timeline returned 2 chronological visits with attached measurements.")

# ---------------------------------------------------------------------------
# TEST 6: CLINICAL TRENDS WORKFLOW
# ---------------------------------------------------------------------------
print("\n[TEST 6] Clinical Trends Trajectory Workflow...")

trends_resp = client.get(f"/patients/{patient_id}/clinical-trends", headers=auth_headers)
assert trends_resp.status_code == 200, f"Trends failed: {trends_resp.text}"
trends_data = trends_resp.json()
assert trends_data["patient_id"] == patient_id
assert "measurements" in trends_data
assert len(trends_data["measurements"]) == 2
# Chronological progression
assert trends_data["measurements"][0]["systolic_bp"] == 142
assert trends_data["measurements"][0]["blood_glucose"] == 140.0
assert trends_data["measurements"][1]["systolic_bp"] == 120
assert trends_data["measurements"][1]["blood_glucose"] == 105.0
print("  [PASS] Clinical trends trajectory points verified across visits (Systolic: 142->120, Glucose: 140->105).")

# ---------------------------------------------------------------------------
# TEST 7: HEALTH CHANGE RADAR WORKFLOW
# ---------------------------------------------------------------------------
print("\n[TEST 7] Health Change Radar Trajectory Workflow...")

radar_resp = client.get(f"/patients/{patient_id}/health-radar", headers=auth_headers)
assert radar_resp.status_code == 200, f"Radar failed: {radar_resp.text}"
radar_data = radar_resp.json()
assert "summary" in radar_data, "Health radar missing summary object"
assert "radar_metrics" in radar_data, "Health radar missing radar_metrics list"

summary = radar_data["summary"]
assert summary["patient_id"] == patient_id
assert summary["total_visits_recorded"] == 2
assert summary["baseline_visit_date"] == "2026-09-01"
assert summary["current_visit_date"] == "2026-10-15"
assert summary["overall_status"] in ("ATTENTION_REQUIRED", "MONITORING_RECOMMENDED", "STABLE_TRAJECTORY", "INSUFFICIENT_HISTORY")
assert len(summary["evidence_narrative"]) > 0

# Check metric calculation for blood glucose
glucose_radar = next((m for m in radar_data["radar_metrics"] if m["key"] == "blood_glucose"), None)
assert glucose_radar is not None, "blood_glucose metric missing in radar metrics"
assert glucose_radar["baseline_value"] == 140.0
assert glucose_radar["current_value"] == 105.0
assert glucose_radar["delta"] == -35.0
print(f"  [PASS] Radar delta calculated accurately (Baseline: 140, Current: 105, Delta: -35 mg/dL).")
print(f"  [PASS] Radar Overall Status: {summary['overall_status']}.")

# ---------------------------------------------------------------------------
# TEST 8: CLINICAL ALERTS & URGENCY DASHBOARD
# ---------------------------------------------------------------------------
print("\n[TEST 8] Clinical Alerts & Health Urgency Dashboard...")

# Patient-specific alerts (evaluated on most recent visit: Visit 2 where BP=120/80, Glucose=105)
alerts_resp = client.get(f"/patients/{patient_id}/clinical-alerts", headers=auth_headers)
assert alerts_resp.status_code == 200
p_alerts = alerts_resp.json()
assert p_alerts["patient_id"] == patient_id
assert "disclaimer" in p_alerts
assert len(p_alerts["disclaimer"]) > 0
print(f"  [PASS] Patient clinical alerts evaluated (Summary: '{p_alerts['summary']}').")

# Urgency Overview across patient population
overview_resp = client.get("/clinical-alerts/overview", headers=auth_headers)
assert overview_resp.status_code == 200
overview = overview_resp.json()
assert "summary" in overview
assert "patients" in overview
assert overview["summary"]["total_patients_evaluated"] >= 1
assert any(p["patient_id"] == patient_id for p in overview["patients"])
print(f"  [PASS] Clinic urgency queue includes Patient #{patient_id} with configured triage severity.")

# ---------------------------------------------------------------------------
# TEST 9: AI CLINICAL COPILOT WORKFLOW (DETERMINISTIC MOCK)
# ---------------------------------------------------------------------------
print("\n[TEST 9] AI Clinical Copilot Workflow (Context & Grounding)...")

mock_answer = (
    "Based on the 2 recorded visits for Ananya Roy (E2E-PAT-001):\n"
    "1. Systolic blood pressure decreased from 142 mmHg (2026-09-01) to 120 mmHg (2026-10-15).\n"
    "2. Blood glucose decreased from 140 mg/dL to 105 mg/dL.\n"
    "Missing data: Lipid panel and HbA1c have not been documented."
)

with patch("app.api.clinical_copilot.ask_clinical_copilot", return_value=mock_answer) as mock_copilot:
    copilot_resp = client.post(
        "/clinical-copilot/ask",
        json={
            "patient_id": patient_id,
            "question": "What is the trajectory of the patient's blood pressure and glucose?",
        },
        headers=auth_headers,
    )
    assert copilot_resp.status_code == 200, f"Copilot request failed: {copilot_resp.text}"
    copilot_data = copilot_resp.json()
    assert copilot_data["patient_id"] == patient_id
    assert copilot_data["patient_name"] == "Ananya Roy"
    assert "142 mmHg" in copilot_data["answer"]
    assert "120 mmHg" in copilot_data["answer"]

    # Verify that ask_clinical_copilot received grounded patient context
    mock_copilot.assert_called_once()
    call_kwargs = mock_copilot.call_args.kwargs
    call_args = mock_copilot.call_args.args
    called_question = call_kwargs.get("question") or (call_args[0] if len(call_args) > 0 else "")
    called_context = call_kwargs.get("patient_context") or (call_args[1] if len(call_args) > 1 else "")
    assert "What is the trajectory" in called_question
    assert "Ananya Roy" in called_context
    assert "142" in called_context
    assert "105" in called_context
    print("  [PASS] Copilot grounded context correctly injected patient visits and vitals.")
    print("  [PASS] Structured Copilot response validated.")

# ---------------------------------------------------------------------------
# TEST 10: MEDICAL REPORT WORKFLOW (UPLOAD, OCR, CONFIRM, DOWNLOAD)
# ---------------------------------------------------------------------------
print("\n[TEST 10] Medical Report Workflow (Upload, OCR, Confirmation, File Download)...")

# Generate synthetic PDF with clinical text
pdf_buf = io.BytesIO()
p_canvas = canvas.Canvas(pdf_buf, pagesize=letter)
p_canvas.drawString(100, 750, "CARETRACK CLINICAL LAB REPORT")
p_canvas.drawString(100, 720, "Patient: Ananya Roy")
p_canvas.drawString(100, 690, "Blood Pressure: 130/85 mmHg")
p_canvas.drawString(100, 660, "Blood Glucose: 110 mg/dL")
p_canvas.drawString(100, 630, "Heart Rate: 74 bpm")
p_canvas.save()
synthetic_pdf_bytes = pdf_buf.getvalue()

with tempfile.TemporaryDirectory() as temp_upload_dir:
    with patch("app.api.medical_report.UPLOAD_DIR", Path(temp_upload_dir)), \
         patch("app.services.medical_report_service.UPLOAD_DIR", Path(temp_upload_dir)):

        # 10a. Upload Report
        upload_resp = client.post(
            "/medical-reports/upload",
            data={"patient_id": patient_id, "visit_id": visit1_id},
            files={"file": ("Synthetic_Lab_Report.pdf", synthetic_pdf_bytes, "application/pdf")},
            headers=auth_headers,
        )
        assert upload_resp.status_code == 201, f"Report upload failed: {upload_resp.text}"
        rep_data = upload_resp.json()
        report_id = rep_data["id"]
        assert rep_data["file_name"] == "Synthetic_Lab_Report.pdf"
        assert rep_data["visit_id"] == visit1_id
        assert "Blood Pressure: 130/85" in (rep_data.get("extracted_text") or "")

        extracted_meas = rep_data.get("extracted_measurements")
        assert extracted_meas is not None, "Extracted measurements should be populated"
        assert extracted_meas["systolic_bp"] == 130
        assert extracted_meas["diastolic_bp"] == 85
        assert extracted_meas["blood_glucose"] == 110.0
        print(f"  [PASS] Medical report uploaded (ID #{report_id}); OCR extraction matched vitals (BP: 130/85, Glucose: 110).")

        # 10b. Confirm Extracted Measurements into ClinicalMeasurement Table
        confirm_resp = client.post(
            f"/medical-reports/{report_id}/confirm-measurements",
            json={"patient_id": patient_id, "visit_id": visit1_id},
            headers=auth_headers,
        )
        assert confirm_resp.status_code == 200, f"Confirm measurements failed: {confirm_resp.text}"
        conf_data = confirm_resp.json()
        assert conf_data["message"] == "Measurements saved for clinical review."
        assert "measurement" in conf_data
        assert conf_data["measurement"]["id"] is not None
        assert "disclaimer" in conf_data
        print(f"  [PASS] Extracted measurements successfully confirmed into database (M ID #{conf_data['measurement']['id']}).")

        # 10c. Download Uploaded Medical Report File
        file_resp = client.get(
            f"/medical-reports/{report_id}/file",
            params={"patient_id": patient_id},
            headers=auth_headers,
        )
        assert file_resp.status_code == 200, f"File download failed: {file_resp.status_code} - {file_resp.text}"
        assert file_resp.content == synthetic_pdf_bytes
        print(f"  [PASS] Uploaded file binary successfully downloaded and matched original bytes ({len(file_resp.content)} bytes).")

# ---------------------------------------------------------------------------
# TEST 11: LONGITUDINAL PATIENT HISTORY PDF EXPORT
# ---------------------------------------------------------------------------
print("\n[TEST 11] Patient History Longitudinal PDF Export...")

pdf_export_resp = client.get(f"/patients/{patient_id}/pdf", headers=auth_headers)
assert pdf_export_resp.status_code == 200, f"PDF export failed: {pdf_export_resp.status_code} - {pdf_export_resp.text}"
assert pdf_export_resp.headers["Content-Type"] == "application/pdf"
assert "attachment" in pdf_export_resp.headers["Content-Disposition"]
assert "CareTrack_Patient_E2E-PAT-001_History.pdf" in pdf_export_resp.headers["Content-Disposition"]
pdf_content = pdf_export_resp.content
assert len(pdf_content) > 3000, f"PDF content unexpectedly small ({len(pdf_content)} bytes)"
assert pdf_content.startswith(b"%PDF-"), "PDF does not start with %PDF- header"
print(f"  [PASS] Generated PDF export ({len(pdf_content)} bytes) with valid header and attachment disposition.")

# Verify non-existent patient PDF export yields 404
bad_pdf_resp = client.get("/patients/99999/pdf", headers=auth_headers)
assert bad_pdf_resp.status_code == 404
print("  [PASS] Non-existent patient PDF request returns HTTP 404 Not Found.")

print("\n" + "=" * 75)
print("ALL 11 END-TO-END WORKFLOW INTEGRATION TESTS PASSED (100% SUCCESS)!")
print("=" * 75)
