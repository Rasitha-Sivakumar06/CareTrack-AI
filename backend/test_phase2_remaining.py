import sys
import time
from pathlib import Path

# Add backend directory to path
backend_dir = Path(r"C:\Users\Admin\Downloads\AI_Longitudinal_Healthcare\backend")
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, BigInteger
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles

from app.database import Base, get_db
from app.main import app
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.clinical_measurement import ClinicalMeasurement
from app.models.medical_report import MedicalReport
from app.models.user import User
from app.security import create_access_token, hash_password

# Map BigInteger to INTEGER in SQLite so autoincrement primary keys function properly in test memory
@compiles(BigInteger, "sqlite")
def compile_big_int_sqlite(type_, compiler, **kw):
    return "INTEGER"

# Setup isolated in-memory SQLite test database with StaticPool
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

# Seed Doctor account in isolated database
db = TestingSessionLocal()
doctor = User(
    id=1,
    username="dr_phase2_tester",
    email="dr_phase2@caretrack.org",
    hashed_password=hash_password("DoctorPhase2SecurePass!"),
    full_name="Dr. Phase2 Clinician",
    role="doctor",
    is_active=True,
)
db.add(doctor)
db.commit()
db.close()

auth_token = create_access_token(1, "doctor")
client.headers.update({"Authorization": f"Bearer {auth_token}"})

print("=" * 70)
print("PHASE 2 REMAINING FEATURES AUTOMATED VERIFICATION")
print("=" * 70)

# Setup a clean synthetic test patient
suffix = str(int(time.time()))[-5:]
test_patient_code = f"T2-REM-{suffix}"
create_resp = client.post("/patients/", json={
    "patient_code": test_patient_code,
    "name": "Synthetic Phase2 Test Patient",
    "age": 40,
    "gender": "Male",
    "phone": "555-0188",
    "location": "North Clinic",
})
assert create_resp.status_code == 201, f"Failed to create test patient: {create_resp.text}"
test_patient = create_resp.json()
patient_id = test_patient["id"]
print(f"Created synthetic test patient ID #{patient_id} ({test_patient_code})")

# -------------------------------------------------------------
# TEST 1: VISIT REGISTRATION
# -------------------------------------------------------------
print("\n" + "-" * 60)
print("1. Testing Visit Registration")
print("-" * 60)

# 1.1 Valid visit creation
visit_payload = {
    "patient_id": patient_id,
    "visit_date": "2026-10-22",
    "symptoms": "Mild fever and sore throat",
    "clinical_notes": "Patient presented with acute pharyngitis symptoms.",
    "follow_up_notes": "Return if fever persists beyond 3 days.",
}
v_resp = client.post("/visits/", json=visit_payload)
print(f"1.1 Valid visit status: {v_resp.status_code}")
assert v_resp.status_code == 201, f"Expected 201, got {v_resp.status_code}: {v_resp.text}"
visit = v_resp.json()
visit_id = visit["id"]
assert visit["patient_id"] == patient_id
assert visit["visit_date"] == "2026-10-22"
print(f"PASS: Created visit #{visit_id} for patient #{patient_id}.")

# 1.2 Invalid patient ID
v_inv_patient = client.post("/visits/", json={
    "patient_id": 999999,
    "visit_date": "2026-10-22",
    "symptoms": "Test",
})
print(f"1.2 Invalid patient status: {v_inv_patient.status_code}")
assert v_inv_patient.status_code == 404, f"Expected 404, got {v_inv_patient.status_code}"
print("PASS: Correctly rejected visit creation for non-existent patient with 404.")

# 1.3 Validation errors (missing date or negative patient_id)
v_inv_schema = client.post("/visits/", json={
    "patient_id": -1,
    "visit_date": "invalid-date",
})
print(f"1.3 Validation error status: {v_inv_schema.status_code}")
assert v_inv_schema.status_code == 422, f"Expected 422, got {v_inv_schema.status_code}"
print("PASS: Correctly rejected malformed visit payload with 422.")

# 1.4 Retrieve single visit
get_v_resp = client.get(f"/visits/{visit_id}")
print(f"1.4 GET /visits/{visit_id} status: {get_v_resp.status_code}")
assert get_v_resp.status_code == 200
assert get_v_resp.json()["id"] == visit_id
print(f"PASS: GET /visits/{visit_id} successfully retrieved visit #{visit_id}.")

# 1.5 Retrieve patient visits
list_v_resp = client.get(f"/visits/patient/{patient_id}")
print(f"1.5 GET /visits/patient/{patient_id} count: {len(list_v_resp.json())}")
assert list_v_resp.status_code == 200
assert any(v["id"] == visit_id for v in list_v_resp.json())
print(f"PASS: Visit #{visit_id} returned in patient visits list.")

# -------------------------------------------------------------
# TEST 2: MANUAL CLINICAL MEASUREMENTS
# -------------------------------------------------------------
print("\n" + "-" * 60)
print("2. Testing Manual Clinical Measurements & Duplicate Prevention")
print("-" * 60)

# 2.1 Valid manual measurement creation
meas_payload = {
    "patient_id": patient_id,
    "visit_id": visit_id,
    "systolic_bp": 120,
    "diastolic_bp": 80,
    "blood_glucose": 95.5,
    "heart_rate": 72.0,
    "temperature": 36.6,
    "oxygen_saturation": 98.0,
    "weight": 70.0,
}
m_resp = client.post("/clinical-measurements/", json=meas_payload)
print(f"2.1 Valid measurement status: {m_resp.status_code}")
assert m_resp.status_code == 201, f"Expected 201, got {m_resp.status_code}: {m_resp.text}"
m_data = m_resp.json()
print(f"PASS: Measurement created successfully with ID #{m_data['id']}.")

# 2.2 Duplicate prevention on repeated submission
dup_m_resp = client.post("/clinical-measurements/", json=meas_payload)
print(f"2.2 Duplicate measurement status: {dup_m_resp.status_code}")
print(f"Duplicate detail: {dup_m_resp.json().get('detail')}")
assert dup_m_resp.status_code == 409, f"Expected 409, got {dup_m_resp.status_code}"
assert "already been recorded" in dup_m_resp.json().get("detail", "")
print("PASS: Identical repeated measurement submission rejected with HTTP 409 Conflict.")

# 2.3 Legitimate new measurement for the same visit (different vitals/values)
new_meas_payload = {
    "patient_id": patient_id,
    "visit_id": visit_id,
    "blood_glucose": 135.0,  # postprandial glucose reading
}
new_m_resp = client.post("/clinical-measurements/", json=new_meas_payload)
print(f"2.3 Additional distinct measurement status: {new_m_resp.status_code}")
assert new_m_resp.status_code == 201, f"Expected 201, got {new_m_resp.status_code}: {new_m_resp.text}"
print(f"PASS: Allowed legitimate new measurement #{new_m_resp.json()['id']} on same visit.")

# 2.4 Validation: Empty measurements (at least one required)
empty_meas_resp = client.post("/clinical-measurements/", json={
    "patient_id": patient_id,
    "visit_id": visit_id,
})
print(f"2.4 Empty measurement status: {empty_meas_resp.status_code}")
assert empty_meas_resp.status_code == 422
print("PASS: Empty measurements rejected with HTTP 422.")

# 2.5 Validation: Out-of-bounds systolic BP (> 300)
oob_meas_resp = client.post("/clinical-measurements/", json={
    "patient_id": patient_id,
    "visit_id": visit_id,
    "systolic_bp": 350,
})
print(f"2.5 Out of bounds BP status: {oob_meas_resp.status_code}")
assert oob_meas_resp.status_code == 422
print("PASS: Out-of-bounds systolic BP rejected with HTTP 422.")

# 2.6 Validation: Mismatched visit/patient (patient exists, but does not own this visit)
other_p_resp = client.post("/patients/", json={
    "patient_code": f"T2-OTHER-{suffix}",
    "name": "Other Test Patient",
    "age": 35,
    "gender": "Female",
    "phone": "555-0199",
    "location": "South Clinic",
})
other_patient_id = other_p_resp.json()["id"]

mismatch_resp = client.post("/clinical-measurements/", json={
    "patient_id": other_patient_id,  # different patient
    "visit_id": visit_id,  # belongs to test_patient
    "systolic_bp": 120,
})
print(f"2.6 Mismatched patient/visit status: {mismatch_resp.status_code}")
assert mismatch_resp.status_code == 404
print("PASS: Mismatched visit/patient rejected with HTTP 404.")

# -------------------------------------------------------------
# TEST 3: SECURE MEDICAL REPORT VIEWING & DOWNLOADING
# -------------------------------------------------------------
print("\n" + "-" * 60)
print("3. Testing Secure Medical Report Retrieval & Access Controls")
print("-" * 60)

# Create a test medical report attached to visit_id
db = TestingSessionLocal()
# Create a dummy report file in uploads
from app.services.medical_report_service import UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
dummy_file = UPLOAD_DIR / f"test_report_{suffix}.pdf"
dummy_file.write_bytes(b"%PDF-1.4 test document content for CareTrack AI")

test_report = MedicalReport(
    visit_id=visit_id,
    file_name="Lab_Results_Oct2026.pdf",
    file_type="application/pdf",
    file_path=str(dummy_file),
    extracted_text="Patient Blood Pressure: 130/85 mmHg, Blood Glucose: 110 mg/dL",
)
db.add(test_report)
db.commit()
db.refresh(test_report)
report_id = test_report.id
db.close()
print(f"Created test report #{report_id} linked to visit #{visit_id} (Patient #{patient_id})")

# 3.1 Authorized download with correct patient_id
auth_resp = client.get(f"/medical-reports/{report_id}/file?patient_id={patient_id}")
print(f"3.1 Authorized download status: {auth_resp.status_code}")
assert auth_resp.status_code == 200, f"Expected 200, got {auth_resp.status_code}"
assert b"%PDF-1.4" in auth_resp.content
print("PASS: Authorized report download returned file content successfully.")

# 3.2 Unauthorized download with different/wrong patient_id
unauth_resp = client.get(f"/medical-reports/{report_id}/file?patient_id={other_patient_id}")
print(f"3.2 Unauthorized download status: {unauth_resp.status_code}")
assert unauth_resp.status_code == 403, f"Expected 403, got {unauth_resp.status_code}"
assert "Access denied" in unauth_resp.json().get("detail", "")
print("PASS: Access denied (HTTP 403) for unauthorized patient ID.")

# 3.3 Non-existent report ID
nonexist_resp = client.get(f"/medical-reports/999999/file?patient_id={patient_id}")
print(f"3.3 Non-existent report status: {nonexist_resp.status_code}")
assert nonexist_resp.status_code == 404
print("PASS: Non-existent report returned HTTP 404.")

# -------------------------------------------------------------
# TEST 4: MEASUREMENT CONFIRMATION WORKFLOW
# -------------------------------------------------------------
print("\n" + "-" * 60)
print("4. Testing Measurement Confirmation Workflow")
print("-" * 60)

# Create another visit with no prior measurements for confirmation test
v2_resp = client.post("/visits/", json={
    "patient_id": patient_id,
    "visit_date": "2026-10-23",
    "symptoms": "Follow-up",
})
visit2_id = v2_resp.json()["id"]

# Create a report for visit2
db = TestingSessionLocal()
report2 = MedicalReport(
    visit_id=visit2_id,
    file_name="Lab_Report_2.pdf",
    file_type="application/pdf",
    file_path=str(dummy_file),
    extracted_text="Clinical Report:\nBlood Pressure: 130/85 mmHg\nBlood Glucose: 110 mg/dL",
)
db.add(report2)
db.commit()
db.refresh(report2)
report2_id = report2.id
db.close()

# 4.1 First confirmation -> should succeed and save measurements
conf1_resp = client.post(
    f"/medical-reports/{report2_id}/confirm-measurements",
    json={"patient_id": patient_id, "visit_id": visit2_id},
)
print(f"4.1 First confirmation status: {conf1_resp.status_code}")
assert conf1_resp.status_code == 200, f"Expected 200, got {conf1_resp.status_code}: {conf1_resp.text}"
saved_meas = conf1_resp.json()["measurement"]
print(f"PASS: Confirmed measurements saved: BP={saved_meas['blood_pressure']}, Glucose={saved_meas['blood_glucose']}")

# 4.2 Duplicate confirmation of identical measurements -> should be rejected with 409
conf_dup_resp = client.post(
    f"/medical-reports/{report2_id}/confirm-measurements",
    json={"patient_id": patient_id, "visit_id": visit2_id},
)
print(f"4.2 Duplicate confirmation status: {conf_dup_resp.status_code}")
print(f"Duplicate confirmation detail: {conf_dup_resp.json().get('detail')}")
assert conf_dup_resp.status_code == 409, f"Expected 409, got {conf_dup_resp.status_code}"
assert "already been confirmed" in conf_dup_resp.json().get("detail", "")
print("PASS: Repeated confirmation of identical measurements rejected with HTTP 409 Conflict.")

# 4.3 Verify legitimate new measurements can be added on visit2 (e.g. from a report with different vitals)
db = TestingSessionLocal()
report3 = MedicalReport(
    visit_id=visit2_id,
    file_name="Lab_Report_3_Cardiology.pdf",
    file_type="application/pdf",
    file_path=str(dummy_file),
    extracted_text="Cardiology Panel:\nHeart Rate: 84 bpm\nOxygen Saturation: 99%",
)
db.add(report3)
db.commit()
db.refresh(report3)
report3_id = report3.id
db.close()

conf3_resp = client.post(
    f"/medical-reports/{report3_id}/confirm-measurements",
    json={"patient_id": patient_id, "visit_id": visit2_id},
)
print(f"4.3 Additional distinct report confirmation status: {conf3_resp.status_code}")
assert conf3_resp.status_code == 200, f"Expected 200, got {conf3_resp.status_code}: {conf3_resp.text}"
print("PASS: Allowed new valid measurements to be confirmed for the same visit without rejection!")

# Clean up temporary test file, dependency overrides, and test database engine
try:
    dummy_file.unlink(missing_ok=True)
except Exception:
    pass

app.dependency_overrides.clear()
Base.metadata.drop_all(bind=test_engine)
test_engine.dispose()

print("\n" + "=" * 70)
print("ALL 4 FEATURES VERIFIED SUCCESSFULLY AND PASSED (ISOLATED IN-MEMORY DB)!")
print("=" * 70)
