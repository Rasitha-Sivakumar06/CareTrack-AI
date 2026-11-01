"""
CareTrack AI — Automated Test Suite for Clinical Fixes

Tests:
1. Blood pressure extraction unit tests (inline, separate lines, missing, invalid/inverted).
2. Safe idempotency check for duplicate medical report uploads (HTTP 409 Conflict).
3. Primary reading vs revision history in timeline, and single-point visit representation in Clinical Trends.
4. Correct measurement-date handling: no invented timestamp when unknown, and clear distinction of visit date vs measured_at.
"""

import io
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

# Configure stdout encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Backend path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine, BigInteger, Integer
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles

from app.database import Base, get_db
from app.main import app
from app.models.clinical_measurement import ClinicalMeasurement
from app.models.medical_report import MedicalReport
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.security import hash_password, create_access_token
from app.services.clinical_extraction_service import extract_clinical_information

# Map BigInteger to INTEGER in SQLite for autoincrement in memory
@compiles(BigInteger, "sqlite")
def compile_big_int_sqlite(type_, compiler, **kw):
    return "INTEGER"

# ---------------------------------------------------------------------------
# Setup isolated in-memory SQLite database
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

# Seed Doctor user for authentication
db = TestingSessionLocal()
doctor = User(
    username="dr_fixes_lead",
    email="dr_fixes@caretrack.org",
    hashed_password=hash_password("DoctorSecurePass2026!"),
    full_name="Dr. Clinical Lead",
    role="doctor",
    is_active=True,
)
db.add(doctor)
db.commit()
db.refresh(doctor)
doc_id = doctor.id
db.close()

doctor_token = create_access_token(subject=doc_id, role="doctor")
auth_headers = {"Authorization": f"Bearer {doctor_token}"}

print("=" * 75)
print("CARETRACK AI — CLINICAL FIXES AUTOMATED TEST SUITE")
print("=" * 75)

# ===========================================================================
# 1. BLOOD PRESSURE EXTRACTION TESTS
# ===========================================================================
print("\n[TEST 1] Blood Pressure Extraction Unit Tests...")

# 1a. Inline formats
res_inline_1 = extract_clinical_information("BP: 130/85 mmHg, Pulse: 72")
assert res_inline_1["systolic_bp"] == 130, f"Expected 130, got {res_inline_1['systolic_bp']}"
assert res_inline_1["diastolic_bp"] == 85, f"Expected 85, got {res_inline_1['diastolic_bp']}"
assert res_inline_1["blood_pressure"] == "130/85"

res_inline_2 = extract_clinical_information("Patient vitals - blood pressure 118 / 76")
assert res_inline_2["blood_pressure"] == "118/76"
assert res_inline_2["systolic_bp"] == 118
assert res_inline_2["diastolic_bp"] == 76

res_inline_3 = extract_clinical_information("Observation: 124/80 mmHg recorded.")
assert res_inline_3["blood_pressure"] == "124/80"
print("  [PASS] 1a: Inline slash formats extracted accurately.")

# 1b. Separate lines / tabular formats (as observed in PDF reports)
table_report_text = """
CARETRACK TEST REPORT
Measurement          Example value    Unit
Blood glucose        95               mg/dL
Systolic blood pressure
118
mmHg
Diastolic blood pressure
76
mmHg
Heart rate           72               beats/min
"""
res_table = extract_clinical_information(table_report_text)
assert res_table["systolic_bp"] == 118, f"Expected 118, got {res_table['systolic_bp']}"
assert res_table["diastolic_bp"] == 76, f"Expected 76, got {res_table['diastolic_bp']}"
assert res_table["blood_pressure"] == "118/76"
assert res_table["blood_glucose"] == 95.0
assert res_table["heart_rate"] == 72.0
print("  [PASS] 1b: Separate multi-line tabular format extracted accurately.")

# 1c. Separate labeled lines
sep_lines_text = "Systolic BP: 142 mmHg\nDiastolic BP: 92 mmHg"
res_sep = extract_clinical_information(sep_lines_text)
assert res_sep["blood_pressure"] == "142/92"
assert res_sep["systolic_bp"] == 142
assert res_sep["diastolic_bp"] == 92
print("  [PASS] 1c: Separate labeled lines extracted accurately.")

# 1d. Missing diastolic or systolic
res_missing_dia = extract_clinical_information("Systolic BP: 125 mmHg")
assert res_missing_dia["systolic_bp"] == 125
assert res_missing_dia["diastolic_bp"] is None
assert res_missing_dia["blood_pressure"] is None  # Combined string requires both

res_missing_sys = extract_clinical_information("Diastolic BP: 82 mmHg")
assert res_missing_sys["systolic_bp"] is None
assert res_missing_sys["diastolic_bp"] == 82
assert res_missing_sys["blood_pressure"] is None
print("  [PASS] 1d: Missing systolic/diastolic values handled cleanly without fabrication.")

# 1e. Invalid values: out-of-bounds or inverted
res_inverted = extract_clinical_information("Blood Pressure: 75/135")
assert res_inverted["blood_pressure"] is None, "Inverted BP (systolic < diastolic) must be rejected"
assert res_inverted["systolic_bp"] is None

res_out_of_bounds = extract_clinical_information("Blood Pressure: 350/15")
assert res_out_of_bounds["blood_pressure"] is None, "Out-of-bounds BP must be rejected"

res_empty = extract_clinical_information("")
assert res_empty["blood_pressure"] is None
assert res_empty["systolic_bp"] is None
print("  [PASS] 1e: Invalid, inverted, and out-of-bounds values safely rejected.")

# ===========================================================================
# 2. SAFE IDEMPOTENCY CHECK FOR MEDICAL REPORT UPLOADS
# ===========================================================================
print("\n[TEST 2] Medical Report Upload Idempotency Check...")

# Create test patient & visit
db = TestingSessionLocal()
pat = Patient(
    patient_code="FIX-PAT-001",
    name="Test Clinical Fix Patient",
    age=35,
    gender="Female",
)
db.add(pat)
db.commit()
db.refresh(pat)
pat_id = pat.id

vis = Visit(
    patient_id=pat_id,
    visit_date=date(2026, 11, 5),
    symptoms="Routine checkup",
    clinical_notes="Baseline check",
)
db.add(vis)
db.commit()
db.refresh(vis)
vis_id = vis.id
db.close()

# Generate a synthetic PDF
pdf_buf = io.BytesIO()
p_canvas = canvas.Canvas(pdf_buf, pagesize=letter)
p_canvas.drawString(100, 750, "CARETRACK CLINICAL TEST REPORT")
p_canvas.drawString(100, 720, "Systolic blood pressure: 120 mmHg")
p_canvas.drawString(100, 690, "Diastolic blood pressure: 80 mmHg")
p_canvas.drawString(100, 660, "Blood Glucose: 100 mg/dL")
p_canvas.save()
test_pdf_bytes = pdf_buf.getvalue()

with tempfile.TemporaryDirectory() as temp_dir:
    with patch("app.api.medical_report.UPLOAD_DIR", Path(temp_dir)), \
         patch("app.services.medical_report_service.UPLOAD_DIR", Path(temp_dir)):

        # First upload -> Success (201)
        up1 = client.post(
            "/medical-reports/upload",
            data={"patient_id": pat_id, "visit_id": vis_id},
            files={"file": ("Report_Alpha.pdf", test_pdf_bytes, "application/pdf")},
            headers=auth_headers,
        )
        assert up1.status_code == 201, f"First upload failed: {up1.status_code} - {up1.text}"
        rep1_data = up1.json()
        assert rep1_data["extracted_measurements"]["systolic_bp"] == 120
        assert rep1_data["extracted_measurements"]["diastolic_bp"] == 80
        assert rep1_data["extracted_measurements"]["blood_pressure"] == "120/80"
        print("  [PASS] 2a: First report upload succeeded with multi-line BP extraction.")

        # Second upload of identical report for the same visit -> HTTP 409 Conflict
        up_dup = client.post(
            "/medical-reports/upload",
            data={"patient_id": pat_id, "visit_id": vis_id},
            files={"file": ("Report_Alpha.pdf", test_pdf_bytes, "application/pdf")},
            headers=auth_headers,
        )
        assert up_dup.status_code == 409, f"Expected 409, got {up_dup.status_code}: {up_dup.text}"
        assert "already been uploaded" in up_dup.json()["detail"]
        print("  [PASS] 2b: Duplicate report upload safely rejected with HTTP 409 Conflict.")

        # Different report filename on same visit -> Allowed (201)
        up_diff = client.post(
            "/medical-reports/upload",
            data={"patient_id": pat_id, "visit_id": vis_id},
            files={"file": ("Report_Beta.pdf", test_pdf_bytes, "application/pdf")},
            headers=auth_headers,
        )
        assert up_diff.status_code == 201
        print("  [PASS] 2c: Distinct report for the visit allowed without false rejection.")

# ===========================================================================
# 3. MEASUREMENT REVISION HISTORY & CLINICAL TRENDS
# ===========================================================================
print("\n[TEST 3] Measurement Revision History & Clinical Trends Trajectory...")

# 3a. Record original measurement on Visit
meas1_resp = client.post(
    "/clinical-measurements/",
    json={
        "patient_id": pat_id,
        "visit_id": vis_id,
        "blood_glucose": 95.0,
        "systolic_bp": 118,
        "diastolic_bp": 76,
        "heart_rate": 72.0,
    },
    headers=auth_headers,
)
assert meas1_resp.status_code == 201
m1_id = meas1_resp.json()["id"]

# 3b. Record updated/revised measurement on the same Visit
meas2_resp = client.post(
    "/clinical-measurements/",
    json={
        "patient_id": pat_id,
        "visit_id": vis_id,
        "blood_glucose": 110.0,
        "systolic_bp": 124,
        "diastolic_bp": 80,
        "heart_rate": 78.0,
    },
    headers=auth_headers,
)
assert meas2_resp.status_code == 201
m2_id = meas2_resp.json()["id"]
print(f"  [PASS] 3a: Recorded original measurement #{m1_id} and revised measurement #{m2_id} for visit #{vis_id}.")

# 3c. Verify Patient Timeline:
# - Latest reading (m2) is at index 0 with is_latest == True
# - Superseded reading (m1) is at index 1 with is_latest == False
tl_resp = client.get(f"/patients/{pat_id}/timeline", headers=auth_headers)
assert tl_resp.status_code == 200
tl_data = tl_resp.json()
vis_tl = tl_data["visits"][0]
assert len(vis_tl["measurements"]) == 2
assert vis_tl["measurements"][0]["id"] == m2_id
assert vis_tl["measurements"][0]["is_latest"] is True
assert vis_tl["measurements"][0]["blood_glucose"] == 110.0
assert vis_tl["measurements"][1]["id"] == m1_id
assert vis_tl["measurements"][1]["is_latest"] is False
assert vis_tl["measurements"][1]["blood_glucose"] == 95.0
print("  [PASS] 3b: Timeline orders latest measurement as primary (index 0) with earlier readings as revisions.")

# 3d. Verify Clinical Trends:
# Revisions must NOT be treated as separate visits.
# Exactly one trend point for the visit should be returned, reflecting the latest reading.
trends_resp = client.get(f"/patients/{pat_id}/clinical-trends", headers=auth_headers)
assert trends_resp.status_code == 200
trends_data = trends_resp.json()
assert len(trends_data["measurements"]) == 1, (
    f"Expected exactly 1 trend point for visit #{vis_id}, got {len(trends_data['measurements'])}"
)
trend_pt = trends_data["measurements"][0]
assert trend_pt["visit_id"] == vis_id
assert trend_pt["blood_glucose"] == 110.0  # Uses latest updated measurement
assert trend_pt["systolic_bp"] == 124
assert trend_pt["diastolic_bp"] == 80
print("  [PASS] 3c: Clinical Trends correctly consolidated visit revisions into a single updated point.")

# ===========================================================================
# 4. MEASUREMENT DATE HANDLING (NO INVENTED TIMESTAMPS)
# ===========================================================================
print("\n[TEST 4] Measurement Date Handling (Preserve Distinctions)...")

# 4a. When measured_at is omitted, it remains None (not invented)
meas_no_time = client.post(
    "/clinical-measurements/",
    json={
        "patient_id": pat_id,
        "visit_id": vis_id,
        "weight": 65.0,
    },
    headers=auth_headers,
)
assert meas_no_time.status_code == 201
m_no_time_data = meas_no_time.json()
assert m_no_time_data["measured_at"] is None, "measured_at must not be invented when unrecorded"
assert m_no_time_data["timestamp_warning"] is None
print("  [PASS] 4a: Intra-day measurement time left None when unrecorded (no fake timestamp created).")

# 4b. When measured_at matches visit date
meas_matching = client.post(
    "/clinical-measurements/",
    json={
        "patient_id": pat_id,
        "visit_id": vis_id,
        "weight": 65.5,
        "measured_at": "2026-11-05T14:30:00",
    },
    headers=auth_headers,
)
assert meas_matching.status_code == 201
assert meas_matching.json()["timestamp_warning"] is None
print("  [PASS] 4b: Matching measurement date accepted without discrepancy warning.")

# 4c. When measured_at genuinely differs from visit date
meas_diff = client.post(
    "/clinical-measurements/",
    json={
        "patient_id": pat_id,
        "visit_id": vis_id,
        "weight": 66.0,
        "measured_at": "2026-11-01T10:00:00",
    },
    headers=auth_headers,
)
assert meas_diff.status_code == 201
assert meas_diff.json()["timestamp_warning"] is not None
assert "Measurement date (2026-11-01) differs from recorded visit date (2026-11-05)" in meas_diff.json()["timestamp_warning"]
print("  [PASS] 4c: Genuine date discrepancy flagged with clear informational warning.")

print("\n" + "=" * 75)
print("ALL CLINICAL FIX VERIFICATION TESTS PASSED (100% SUCCESS)!")
print("=" * 75)
