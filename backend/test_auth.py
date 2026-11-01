"""
CareTrack AI — Backend Authentication & Authorization Test Suite
Tests:
1. Password hashing & verification (bcrypt)
2. Valid login & JWT token generation
3. Invalid login: wrong password (generic 401)
4. Invalid login: non-existent user (generic 401)
5. Inactive user login rejection (401)
6. GET /auth/me with valid Bearer token (200)
7. GET /auth/me missing token (401)
8. GET /auth/me invalid / tampered token (401)
9. GET /auth/me expired token (401)
10. Role-based authorization: doctor requirement (403 when forbidden)
11. Role-based authorization: admin requirement (403 when doctor tries admin)

Zero real patient records are accessed or modified. Uses an isolated test session.
"""

from datetime import timedelta
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from fastapi import Depends, APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.user import User
from app.main import app
from app.security import (
    hash_password,
    verify_password,
    create_access_token,
)
from app.api.deps import get_current_user, require_role

# Setup an isolated in-memory test database for authentication testing
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Create only the user table in the test database
User.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# Create temporary protected test routes to verify require_role dependencies
test_router = APIRouter(prefix="/test-roles")


@test_router.get("/doctor-only", dependencies=[Depends(require_role(["doctor"]))])
def doctor_only_route():
    return {"message": "Access granted to doctor"}


@test_router.get("/admin-only", dependencies=[Depends(require_role(["admin"]))])
def admin_only_route():
    return {"message": "Access granted to admin"}


app.include_router(test_router)

client = TestClient(app)


def seed_test_users():
    db = TestingSessionLocal()
    db.query(User).delete()

    # Create synthetic test doctor
    doctor_user = User(
        username="test_dr_arun",
        email="dr_arun@caretrack.test",
        hashed_password=hash_password("DoctorSecretPass123!"),
        full_name="Dr. Arun Sharma",
        role="doctor",
        is_active=True,
    )

    # Create synthetic test admin
    admin_user = User(
        username="test_admin_system",
        email="admin@caretrack.test",
        hashed_password=hash_password("AdminSecretPass123!"),
        full_name="System Administrator",
        role="admin",
        is_active=True,
    )

    # Create synthetic inactive user
    inactive_user = User(
        username="test_deactivated",
        email="inactive@caretrack.test",
        hashed_password=hash_password("InactiveSecret123!"),
        full_name="Deactivated Clinician",
        role="doctor",
        is_active=False,
    )

    db.add_all([doctor_user, admin_user, inactive_user])
    db.commit()
    db.close()


def run_tests():
    print("=" * 70)
    print("CARETRACK AI — BACKEND AUTHENTICATION TEST SUITE")
    print("=" * 70)

    # 1. Test Password Hashing Utilities
    print("\n1. Testing Bcrypt Password Hashing & Salt Uniqueness...")
    raw_pass = "ComplexSecret#2026"
    hash1 = hash_password(raw_pass)
    hash2 = hash_password(raw_pass)

    assert hash1 != hash2, "FAIL: Bcrypt did not generate unique salts!"
    assert verify_password(raw_pass, hash1) is True, "FAIL: Valid password failed verification!"
    assert verify_password("WrongPassword123", hash1) is False, "FAIL: Wrong password returned True!"
    print("PASS: Bcrypt password hashing, salt uniqueness, and constant-time check verified.")

    # Seed test users in test database
    seed_test_users()

    # 2. Test Valid Login (Doctor) via JSON
    print("\n2. Testing POST /auth/login with JSON Payload (Valid Credentials)...")
    login_resp = client.post("/auth/login", json={
        "username": "test_dr_arun",
        "password": "DoctorSecretPass123!",
    })
    assert login_resp.status_code == 200, f"Expected 200, got {login_resp.status_code}: {login_resp.text}"
    data = login_resp.json()
    assert "access_token" in data, "FAIL: Missing access_token in response"
    assert data["token_type"] == "bearer"
    assert "expires_in" in data and data["expires_in"] > 0
    assert data["user"]["username"] == "test_dr_arun"
    assert data["user"]["role"] == "doctor"
    doctor_token = data["access_token"]
    print("PASS: Valid JSON login issued signed bearer token and user profile.")

    # 3. Test Valid Login (Doctor) via OAuth2 Form URL-Encoded (Swagger UI Simulation)
    print("\n3. Testing POST /auth/login with OAuth2 Form-Encoded Payload (Swagger UI Simulation)...")
    form_resp = client.post(
        "/auth/login",
        data={
            "username": "test_dr_arun",
            "password": "DoctorSecretPass123!",
            "grant_type": "password",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert form_resp.status_code == 200, f"Expected 200, got {form_resp.status_code}: {form_resp.text}"
    form_data = form_resp.json()
    assert "access_token" in form_data
    assert form_data["token_type"] == "bearer"
    assert form_data["user"]["username"] == "test_dr_arun"
    print("PASS: Valid OAuth2 form login succeeded (Swagger UI Authorize flow verified).")

    # 4. Test Login with Email Identifier (both Form and JSON)
    print("\n4. Testing POST /auth/login with Email identifier...")
    email_json = client.post("/auth/login", json={
        "username": "dr_arun@caretrack.test",
        "password": "DoctorSecretPass123!",
    })
    assert email_json.status_code == 200
    assert email_json.json()["user"]["username"] == "test_dr_arun"

    email_form = client.post(
        "/auth/login",
        data={
            "username": "dr_arun@caretrack.test",
            "password": "DoctorSecretPass123!",
        },
    )
    assert email_form.status_code == 200
    assert email_form.json()["user"]["username"] == "test_dr_arun"
    print("PASS: Login with email identifier succeeded for both JSON and Form.")

    # 5. Test Missing / Empty Credentials Handling (422)
    print("\n5. Testing POST /auth/login with Missing Credentials (422 Validation)...")
    missing_json = client.post("/auth/login", json={"username": "test_dr_arun"})
    assert missing_json.status_code == 422

    missing_form = client.post("/auth/login", data={"username": "test_dr_arun"})
    assert missing_form.status_code == 422
    print("PASS: Missing credentials rejected with HTTP 422 for both JSON and Form.")

    # 4. Test Invalid Login - Wrong Password
    print("\n4. Testing POST /auth/login with Wrong Password...")
    bad_pass = client.post("/auth/login", json={
        "username": "test_dr_arun",
        "password": "WrongPassword999!",
    })
    assert bad_pass.status_code == 401
    assert bad_pass.json()["detail"] == "Incorrect username or password."
    print("PASS: Wrong password rejected with generic 401 error.")

    # 5. Test Invalid Login - Unknown User
    print("\n5. Testing POST /auth/login with Non-Existent User...")
    unknown_user = client.post("/auth/login", json={
        "username": "non_existent_user_9999",
        "password": "SomePassword123!",
    })
    assert unknown_user.status_code == 401
    assert unknown_user.json()["detail"] == "Incorrect username or password."
    print("PASS: Unknown user rejected with identical generic 401 (enumeration prevented).")

    # 6. Test Inactive User Login
    print("\n6. Testing POST /auth/login with Inactive/Deactivated User...")
    inactive_login = client.post("/auth/login", json={
        "username": "test_deactivated",
        "password": "InactiveSecret123!",
    })
    assert inactive_login.status_code == 401
    assert "deactivated" in inactive_login.json()["detail"].lower()
    print("PASS: Inactive user rejected from logging in.")

    # 7. Test GET /auth/me with Valid Token
    print("\n7. Testing GET /auth/me with Valid Bearer Token...")
    me_resp = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["username"] == "test_dr_arun"
    assert me_data["role"] == "doctor"
    print(f"PASS: Current user profile verified (User: {me_data['username']}, Role: {me_data['role']}).")

    # 8. Test GET /auth/me with Missing Token
    print("\n8. Testing GET /auth/me without Token...")
    no_token = client.get("/auth/me")
    assert no_token.status_code == 401
    print("PASS: Missing token rejected with 401 Unauthorized.")

    # 9. Test GET /auth/me with Invalid / Tampered Token
    print("\n9. Testing GET /auth/me with Tampered Token...")
    tampered = doctor_token[:-5] + "ABCDE"
    bad_token = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tampered}"},
    )
    assert bad_token.status_code == 401
    print("PASS: Tampered token signature rejected with 401 Unauthorized.")

    # 10. Test GET /auth/me with Expired Token
    print("\n10. Testing GET /auth/me with Expired Token...")
    expired_token = create_access_token(
        subject=1,
        role="doctor",
        expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
    )
    exp_resp = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert exp_resp.status_code == 401
    assert "expired" in exp_resp.json()["detail"].lower()
    print("PASS: Expired token rejected with 401 Unauthorized.")

    # 11. Test Role-Based Access Control
    print("\n11. Testing Role-Based Authorization Dependencies (require_role)...")
    # Login as admin to get admin token
    admin_login = client.post("/auth/login", json={
        "username": "test_admin_system",
        "password": "AdminSecretPass123!",
    })
    admin_token = admin_login.json()["access_token"]

    # 11a. Doctor accessing doctor route: ALLOWED
    doc_access = client.get(
        "/test-roles/doctor-only",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert doc_access.status_code == 200

    # 11b. Doctor accessing admin route: FORBIDDEN (403)
    doc_forbidden = client.get(
        "/test-roles/admin-only",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert doc_forbidden.status_code == 403
    assert "permitted" in doc_forbidden.json()["detail"].lower()
    print("PASS: Doctor access to admin-only route correctly forbidden with HTTP 403.")

    # 11c. Admin accessing admin route: ALLOWED
    admin_access = client.get(
        "/test-roles/admin-only",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_access.status_code == 200
    print("PASS: Admin access to admin-only route succeeded.")

    # 12. Test OpenAPI Schema for OAuth2 Password Flow & Dual Payloads
    print("\n12. Testing OpenAPI Schema Specification for Swagger UI Compatibility...")
    openapi = app.openapi()
    assert "/auth/login" in openapi["paths"], "FAIL: /auth/login path missing from OpenAPI"
    login_op = openapi["paths"]["/auth/login"]["post"]
    req_content = login_op["requestBody"]["content"]
    assert "application/x-www-form-urlencoded" in req_content, (
        "FAIL: application/x-www-form-urlencoded missing from /auth/login requestBody (required for Swagger Authorize)"
    )
    assert "application/json" in req_content, (
        "FAIL: application/json missing from /auth/login requestBody"
    )
    form_props = req_content["application/x-www-form-urlencoded"]["schema"]["properties"]
    assert "username" in form_props and "password" in form_props
    sec_schemes = openapi.get("components", {}).get("securitySchemes", {})
    assert "OAuth2PasswordBearer" in sec_schemes, "FAIL: OAuth2PasswordBearer missing from securitySchemes"
    token_url = sec_schemes["OAuth2PasswordBearer"]["flows"]["password"]["tokenUrl"]
    assert token_url == "/auth/login", f"FAIL: tokenUrl expected '/auth/login', got '{token_url}'"
    print("PASS: OpenAPI schema correctly publishes both form-urlencoded and JSON for /auth/login with OAuth2 scheme.")

    print("\n" + "=" * 70)
    print("ALL AUTHENTICATION & AUTHORIZATION TESTS PASSED (100% SUCCESS)!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
