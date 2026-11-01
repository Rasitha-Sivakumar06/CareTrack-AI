"""
CareTrack AI — Backend API Protection Test Suite
Verifies:
1. Anonymous request rejection (401) on all sensitive clinical endpoints.
2. Public endpoints preservation (/, /health, /auth/login).
3. Invalid, tampered, and expired token rejection (401).
4. Deactivated user token rejection (401).
5. Role-based access control:
   - Doctor attempting DELETE /patients/{id} -> 403 Forbidden
   - Admin calling DELETE /patients/{id} -> Authorized past role gate
6. Authorized requests with valid Doctor token succeed on sensitive endpoints.
7. Zero modifications to live Supabase clinical records (isolated test database session).
"""

from datetime import timedelta
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db, settings
from app.models.user import User
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.clinical_measurement import ClinicalMeasurement
from app.main import app
from app.security import hash_password, create_access_token

# Setup isolated in-memory SQLite database
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Create tables in test database
Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

print("=" * 70)
print("CARETRACK AI — BACKEND API PROTECTION & AUTHORIZATION TEST SUITE")
print("=" * 70)

# Seed test users and test patient in isolated database
db = TestingSessionLocal()

# 1. Doctor account
doctor_user = User(
    username="dr_sharma",
    email="dr_sharma@caretrack.org",
    hashed_password=hash_password("DoctorSecret2026!"),
    full_name="Dr. Priya Sharma",
    role="doctor",
    is_active=True,
)
# 2. Admin account
admin_user = User(
    username="admin_kiran",
    email="admin_kiran@caretrack.org",
    hashed_password=hash_password("AdminSecret2026!"),
    full_name="Kiran Patel",
    role="admin",
    is_active=True,
)
# 3. Deactivated account
inactive_user = User(
    username="inactive_doc",
    email="inactive@caretrack.org",
    hashed_password=hash_password("InactiveSecret2026!"),
    full_name="Inactive Doctor",
    role="doctor",
    is_active=False,
)
# 4. Test patient
test_patient = Patient(
    patient_code="TEST-PAT-001",
    name="Ramesh Gupta",
    age=52,
    gender="Male",
    phone="555-0199",
    location="Pune",
)

db.add_all([doctor_user, admin_user, inactive_user, test_patient])
db.commit()
db.refresh(doctor_user)
db.refresh(admin_user)
db.refresh(inactive_user)
db.refresh(test_patient)

doctor_id = doctor_user.id
doctor_username = doctor_user.username
admin_id = admin_user.id
admin_username = admin_user.username
inactive_id = inactive_user.id

from datetime import date, timedelta

patient_id = test_patient.id

# Seed a visit and clinical measurement for patient
test_visit = Visit(
    patient_id=patient_id,
    visit_date=date(2026, 10, 20),
    symptoms="Routine checkup",
    clinical_notes="Hypertension monitoring",
)
db.add(test_visit)
db.commit()
db.refresh(test_visit)
visit_id = test_visit.id

test_meas = ClinicalMeasurement(
    id=1,
    patient_id=patient_id,
    visit_id=visit_id,
    systolic_bp=135.0,
    diastolic_bp=88.0,
    heart_rate=74.0,
    blood_glucose=105.0,
)
db.add(test_meas)
db.commit()
db.close()

# Generate tokens
valid_doctor_token = create_access_token(
    subject=doctor_id,
    role="doctor",
    expires_delta=timedelta(hours=1),
    extra_claims={"username": doctor_username},
)
valid_admin_token = create_access_token(
    subject=admin_id,
    role="admin",
    expires_delta=timedelta(hours=1),
    extra_claims={"username": admin_username},
)
expired_token = create_access_token(
    subject=doctor_id,
    role="doctor",
    expires_delta=timedelta(minutes=-10),  # expired 10 mins ago
)
inactive_user_token = create_access_token(
    subject=inactive_id,
    role="doctor",
    expires_delta=timedelta(hours=1),
)
tampered_token = valid_doctor_token[:-5] + "XXXXX"

doctor_headers = {"Authorization": f"Bearer {valid_doctor_token}"}
admin_headers = {"Authorization": f"Bearer {valid_admin_token}"}

total_tests = 0
passed_tests = 0


def record_pass(description):
    global total_tests, passed_tests
    total_tests += 1
    passed_tests += 1
    print(f"  [PASS] {description}")


def record_fail(description, error_detail):
    global total_tests
    total_tests += 1
    print(f"  [FAIL] {description} -> {error_detail}")
    raise AssertionError(f"{description} -> {error_detail}")


# -------------------------------------------------------------------
# 1. PUBLIC ENDPOINTS PRESERVATION
# -------------------------------------------------------------------
print("\n[SECTION 1] Public Endpoints Preservation")

resp = client.get("/")
assert resp.status_code == 200, f"Expected 200 on /, got {resp.status_code}"
record_pass("GET / is intentionally public (200 OK)")

resp = client.get("/health")
assert resp.status_code == 200, f"Expected 200 on /health, got {resp.status_code}"
assert resp.json().get("status") == "healthy"
record_pass("GET /health is intentionally public (200 OK)")

resp = client.post("/auth/login", json={"username": "dr_sharma", "password": "wrong_password"})
assert resp.status_code == 401, f"Expected 401 on bad credentials, got {resp.status_code}"
assert resp.json()["detail"] == "Incorrect username or password."
record_pass("POST /auth/login is public and validates credentials properly")


# -------------------------------------------------------------------
# 2. ANONYMOUS ACCESS REJECTION (401) ON SENSITIVE ENDPOINTS
# -------------------------------------------------------------------
print("\n[SECTION 2] Anonymous Access Rejection (401 Unauthorized)")

sensitive_endpoints = [
    ("GET", f"/patients/"),
    ("POST", f"/patients/"),
    ("GET", f"/patients/{patient_id}"),
    ("PUT", f"/patients/{patient_id}"),
    ("DELETE", f"/patients/{patient_id}"),
    ("GET", f"/patients/{patient_id}/pdf"),
    ("GET", f"/patients/{patient_id}/timeline"),
    ("GET", f"/patients/{patient_id}/clinical-trends"),
    ("GET", f"/patients/{patient_id}/longitudinal-insights"),
    ("GET", f"/patients/{patient_id}/clinical-alerts"),
    ("GET", f"/patients/{patient_id}/health-radar"),
    ("GET", f"/clinical-alerts/overview"),
    ("POST", f"/clinical-copilot/ask"),
    ("GET", f"/visits/patient/{patient_id}"),
    ("POST", f"/visits/"),
    ("POST", f"/clinical-measurements/"),
    ("GET", f"/medical-reports/visit/{visit_id}"),
    ("POST", f"/medical-reports/upload"),
    ("POST", f"/medical-reports/1/confirm-measurements"),
    ("GET", f"/medical-reports/1/file"),
    ("POST", f"/clinical-translation/translate"),
    ("GET", f"/patients/{patient_id}/health-trajectory"),
    ("GET", f"/auth/me"),
]

for method, path in sensitive_endpoints:
    if method == "GET":
        r = client.get(path)
    elif method == "POST":
        r = client.post(path, json={})
    elif method == "PUT":
        r = client.put(path, json={})
    elif method == "DELETE":
        r = client.delete(path)

    assert r.status_code == 401, f"Expected 401 on anonymous {method} {path}, got {r.status_code}: {r.text}"
    assert "Bearer" in r.headers.get("www-authenticate", "")
    assert r.json().get("detail") == "Authentication token is missing."
    record_pass(f"Anonymous {method} {path} strictly rejected with 401 Unauthorized")


# -------------------------------------------------------------------
# 3. INVALID, TAMPERED & EXPIRED TOKEN REJECTION
# -------------------------------------------------------------------
print("\n[SECTION 3] Invalid, Tampered & Expired Token Rejection")

# Tampered token
r = client.get(f"/patients/{patient_id}", headers={"Authorization": f"Bearer {tampered_token}"})
assert r.status_code == 401
assert r.json()["detail"] == "Could not validate credentials."
record_pass("Tampered JWT rejected with 401 (Could not validate credentials)")

# Expired token
r = client.get(f"/patients/{patient_id}", headers={"Authorization": f"Bearer {expired_token}"})
assert r.status_code == 401
assert r.json()["detail"] == "Authentication token has expired."
record_pass("Expired JWT rejected with 401 (Authentication token has expired)")

# Deactivated user token
r = client.get(f"/patients/{patient_id}", headers={"Authorization": f"Bearer {inactive_user_token}"})
assert r.status_code == 401
assert r.json()["detail"] == "User account is deactivated."
record_pass("Deactivated user token rejected with 401 (User account is deactivated)")


# -------------------------------------------------------------------
# 4. ROLE-BASED ACCESS CONTROL (DOCTOR VS ADMIN)
# -------------------------------------------------------------------
print("\n[SECTION 4] Role-Based Access Control on Patient Deletion")

# Doctor attempts DELETE /patients/{patient_id} -> 403 Forbidden
r_doctor_del = client.delete(f"/patients/{patient_id}", headers=doctor_headers)
assert r_doctor_del.status_code == 403, f"Expected 403 for doctor delete, got {r_doctor_del.status_code}: {r_doctor_del.text}"
assert "admin" in r_doctor_del.json()["detail"].lower()
record_pass(f"Doctor role denied deletion with 403 Forbidden ({r_doctor_del.json()['detail']})")

# Non-existent patient delete by doctor -> still denied 403 (role check happens first)
r_doctor_nonexistent = client.delete("/patients/99999", headers=doctor_headers)
assert r_doctor_nonexistent.status_code == 403
record_pass("Doctor role denied deletion on non-existent patient (role gate runs before DB query)")

# Admin attempts DELETE /patients/{patient_id} -> Passes role gate and deletes successfully (204)
r_admin_del = client.delete(f"/patients/{patient_id}", headers=admin_headers)
assert r_admin_del.status_code in (204, 200), f"Expected 204/200 for admin delete, got {r_admin_del.status_code}: {r_admin_del.text}"
record_pass("Admin role successfully authorized for DELETE /patients/{patient_id} (204 No Content)")


# -------------------------------------------------------------------
# 5. AUTHORIZED REQUESTS WITH VALID DOCTOR CREDENTIALS
# -------------------------------------------------------------------
print("\n[SECTION 5] Authorized Requests with Valid Doctor Credentials")

# Re-create patient for testing read routes
db = TestingSessionLocal()
p2 = Patient(
    patient_code="TEST-PAT-002",
    name="Sunita Deshmukh",
    age=44,
    gender="Female",
    phone="555-0211",
    location="Mumbai",
)
db.add(p2)
db.commit()
db.refresh(p2)
p2_id = p2.id

# Add visit and measurement for p2 so trends and radar have data
v2 = Visit(
    patient_id=p2_id,
    visit_date=date(2026, 10, 21),
    symptoms="Follow-up checkup",
    clinical_notes="Hypertension stable",
)
db.add(v2)
db.commit()
db.refresh(v2)

m2 = ClinicalMeasurement(
    id=2,
    patient_id=p2_id,
    visit_id=v2.id,
    systolic_bp=128.0,
    diastolic_bp=82.0,
    heart_rate=70.0,
    blood_glucose=98.0,
)
db.add(m2)
db.commit()
db.close()

# GET /patients/
r = client.get("/patients/", headers=doctor_headers)
assert r.status_code == 200
assert isinstance(r.json(), list)
record_pass(f"Doctor GET /patients/ authorized (200 OK, count: {len(r.json())})")

# GET /patients/{id}
r = client.get(f"/patients/{p2_id}", headers=doctor_headers)
assert r.status_code == 200
assert r.json()["patient_code"] == "TEST-PAT-002"
record_pass("Doctor GET /patients/{id} authorized (200 OK)")

# GET /patients/{id}/pdf
r = client.get(f"/patients/{p2_id}/pdf", headers=doctor_headers)
assert r.status_code == 200
assert "application/pdf" in r.headers["content-type"]
assert r.content.startswith(b"%PDF")
record_pass(f"Doctor GET /patients/{id}/pdf authorized (200 OK, {len(r.content)} bytes)")

# GET /clinical-alerts/overview
r = client.get("/clinical-alerts/overview", headers=doctor_headers)
assert r.status_code == 200
assert "rules" in r.json() and "summary" in r.json()
record_pass("Doctor GET /clinical-alerts/overview authorized (200 OK)")

# GET /patients/{id}/health-radar
r = client.get(f"/patients/{p2_id}/health-radar", headers=doctor_headers)
assert r.status_code == 200
assert "radar_metrics" in r.json()
record_pass("Doctor GET /patients/{id}/health-radar authorized (200 OK)")

# GET /patients/{id}/clinical-trends
r = client.get(f"/patients/{p2_id}/clinical-trends", headers=doctor_headers)
assert r.status_code == 200
record_pass("Doctor GET /patients/{id}/clinical-trends authorized (200 OK)")

# GET /patients/{id}/timeline
r = client.get(f"/patients/{p2_id}/timeline", headers=doctor_headers)
assert r.status_code == 200
record_pass("Doctor GET /patients/{id}/timeline authorized (200 OK)")

# GET /patients/{id}/clinical-alerts
r = client.get(f"/patients/{p2_id}/clinical-alerts", headers=doctor_headers)
assert r.status_code == 200
record_pass("Doctor GET /patients/{id}/clinical-alerts authorized (200 OK)")

# GET /patients/{id}/longitudinal-insights
r = client.get(f"/patients/{p2_id}/longitudinal-insights", headers=doctor_headers)
assert r.status_code == 200
record_pass("Doctor GET /patients/{id}/longitudinal-insights authorized (200 OK)")

# GET /patients/{id}/health-trajectory
r = client.get(f"/patients/{p2_id}/health-trajectory", headers=doctor_headers)
assert r.status_code == 200
assert "summary" in r.json() and "metrics" in r.json()
record_pass("Doctor GET /patients/{id}/health-trajectory authorized (200 OK)")

# GET /auth/me
r = client.get("/auth/me", headers=doctor_headers)
assert r.status_code == 200
assert r.json()["username"] == "dr_sharma"
assert r.json()["role"] == "doctor"
record_pass("Doctor GET /auth/me returns authenticated clinician profile")

# Admin GET /auth/me
r = client.get("/auth/me", headers=admin_headers)
assert r.status_code == 200
assert r.json()["username"] == "admin_kiran"
assert r.json()["role"] == "admin"
record_pass("Admin GET /auth/me returns authenticated admin profile")

print("\n" + "=" * 70)
print(f"RESULTS: {passed_tests}/{total_tests} TESTS PASSED (100% SUCCESS)!")
print("=" * 70)
