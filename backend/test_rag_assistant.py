"""
CareTrack AI — Phase 2 API Integration Test Suite for Patient History RAG Assistant

Tests:
1. Anonymous request to POST /rag/ask returns HTTP 401 Unauthorized.
2. Authenticated valid request returns HTTP 200 OK.
3. Correct response schema is returned (RAGQueryResponse).
4. Non-existent patient returns HTTP 404 Not Found.
5. Invalid patient ID or question returns HTTP 422 Unprocessable Entity.
6. Patient data isolation is maintained (zero cross-patient record leakage).
7. Patient with zero visits receives a safe clinical guidance response without Gemini call.
8. Source identifiers ([S1], [S2]...) and structured metadata are returned.
9. Retrieval method is explicitly 'structured_longitudinal_retrieval'.
10. Gemini API failure is handled safely (HTTP 502 without stack trace or secret leaks).
11. Clinical safety disclaimer is present in the response.
12. Existing Clinical Copilot endpoint (POST /clinical-copilot/ask) remains functional.
"""

from datetime import date, datetime, timezone
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock

# Configure stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
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

# Map BigInteger to INTEGER in SQLite so autoincrement primary keys function properly in test memory
@compiles(BigInteger, "sqlite")
def compile_big_int_sqlite(type_, compiler, **kw):
    return "INTEGER"


def setup_test_environment():
    """Create isolated SQLite database and seed test accounts and clinical records."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    db = TestingSession()

    # 1. Seed Doctor User
    doctor_password = "DoctorSecurePass2026!"
    doctor = User(
        id=1,
        username="dr_rag_tester",
        email="dr_rag@caretrack.org",
        hashed_password=hash_password(doctor_password),
        full_name="Dr. RAG Evaluator",
        role="doctor",
        is_active=True,
    )
    db.add(doctor)

    # 2. Seed Multi-Visit Patient (Patient #1)
    patient_1 = Patient(
        id=1,
        patient_code="CARE-PAT-001",
        name="Arun Kumar",
        age=45,
        gender="Male",
        phone="9876543210",
        location="Coimbatore",
    )
    db.add(patient_1)

    v1_p1 = Visit(
        id=101,
        patient_id=1,
        visit_date=date(2026, 9, 1),
        symptoms="Mild fatigue, polydipsia",
        clinical_notes="Baseline visit. Initial screening.",
        follow_up_notes="Repeat blood glucose in 4 weeks.",
    )
    v2_p1 = Visit(
        id=102,
        patient_id=1,
        visit_date=date(2026, 10, 15),
        symptoms="Fatigue resolved",
        clinical_notes="Follow-up consultation. Improved lifestyle control.",
        follow_up_notes="Continue current regimen.",
    )
    db.add_all([v1_p1, v2_p1])
    db.flush()

    m1_p1 = ClinicalMeasurement(
        id=1001,
        patient_id=1,
        visit_id=101,
        blood_pressure="140/90",
        systolic_bp=140,
        diastolic_bp=90,
        blood_glucose=160.0,
        hemoglobin=13.5,
        heart_rate=78.0,
        temperature=37.0,
        oxygen_saturation=98.0,
        weight=74.0,
        measured_at=datetime(2026, 9, 1, 9, 30, tzinfo=timezone.utc),
    )
    m2_p1 = ClinicalMeasurement(
        id=1002,
        patient_id=1,
        visit_id=102,
        blood_pressure="125/80",
        systolic_bp=125,
        diastolic_bp=80,
        blood_glucose=115.0,
        hemoglobin=13.8,
        heart_rate=72.0,
        temperature=36.8,
        oxygen_saturation=99.0,
        weight=73.2,
        measured_at=datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc),
    )
    r1_p1 = MedicalReport(
        id=501,
        visit_id=101,
        file_name="lab_glucose_report.pdf",
        file_type="application/pdf",
        extracted_text="LAB REPORT: Fasting Blood Glucose 160 mg/dL, HbA1c 7.2%",
    )
    db.add_all([m1_p1, m2_p1, r1_p1])

    # 3. Seed Isolated Patient (Patient #2)
    patient_2 = Patient(
        id=2,
        patient_code="CARE-PAT-002",
        name="Lakshmi Priya",
        age=38,
        gender="Female",
        phone="9876543211",
        location="Madurai",
    )
    db.add(patient_2)

    v1_p2 = Visit(
        id=201,
        patient_id=2,
        visit_date=date(2026, 10, 1),
        symptoms="Severe headaches",
        clinical_notes="Hypertension assessment.",
        follow_up_notes="Daily BP recording.",
    )
    db.add(v1_p2)
    db.flush()

    m1_p2 = ClinicalMeasurement(
        id=2001,
        patient_id=2,
        visit_id=201,
        blood_pressure="160/100",
        systolic_bp=160,
        diastolic_bp=100,
        blood_glucose=95.0,
        measured_at=datetime(2026, 10, 1, 11, 0, tzinfo=timezone.utc),
    )
    db.add(m1_p2)

    # 4. Seed Zero-Visit Patient (Patient #3)
    patient_3 = Patient(
        id=3,
        patient_code="CARE-PAT-003",
        name="Zero Visit Patient",
        age=30,
        gender="Other",
        phone="9876543212",
        location="Trichy",
    )
    db.add(patient_3)

    db.commit()
    db.close()

    return client, doctor_password


def run_api_tests():
    print("=" * 75)
    print("CARETRACK AI — PHASE 2: RAG API INTEGRATION & AUTOMATED TEST SUITE")
    print("=" * 75)

    client, doctor_password = setup_test_environment()
    passed = 0
    total = 12

    # Obtain Doctor JWT Token
    login_resp = client.post(
        "/auth/login",
        data={"username": "dr_rag_tester", "password": doctor_password},
    )
    assert login_resp.status_code == 200, "Doctor login failed"
    token = login_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # -------------------------------------------------------------------------
    # TEST 1: Anonymous request returns HTTP 401 Unauthorized
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Anonymous request to POST /rag/ask returns HTTP 401...")
    anon_resp = client.post(
        "/rag/ask",
        json={"patient_id": 1, "question": "Summarize this patient's medical history."},
    )
    assert anon_resp.status_code == 401, f"Expected 401, got {anon_resp.status_code}"
    print("  [PASS] Anonymous request strictly rejected with HTTP 401 Unauthorized.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 2: Authenticated valid request returns HTTP 200 OK
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Authenticated valid request returns HTTP 200 OK...")
    mock_answer = (
        "Patient Arun Kumar has 2 documented visits [S1, S4]. "
        "Fasting blood glucose decreased from 160.0 mg/dL at baseline on Sep 1, 2026 [S2] "
        "to 115.0 mg/dL on Oct 15, 2026 [S5]. Blood pressure decreased from 140/90 [S2] "
        "to 125/80 mmHg [S5]. Lab reports also confirm glucose reduction [S3]."
    )

    with patch("app.services.rag_service.generate_rag_answer", return_value=mock_answer):
        auth_resp = client.post(
            "/rag/ask",
            headers=auth_headers,
            json={"patient_id": 1, "question": "How have the patient's glucose levels changed across visits?"},
        )
    assert auth_resp.status_code == 200, f"Expected 200, got {auth_resp.status_code}: {auth_resp.text}"
    print("  [PASS] Authenticated request accepted and returned HTTP 200 OK.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 3: Correct response schema is returned (RAGQueryResponse)
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Response schema matches RAGQueryResponse specification...")
    data = auth_resp.json()
    assert data["patient_id"] == 1
    assert data["patient_code"] == "CARE-PAT-001"
    assert data["patient_name"] == "Arun Kumar"
    assert "glucose" in data["question"]
    assert "answer" in data and len(data["answer"]) > 10
    assert "sources" in data and isinstance(data["sources"], list)
    assert "retrieval_method" in data
    assert "data_summary" in data
    assert "disclaimer" in data
    print("  [PASS] Response conforms strictly to RAGQueryResponse schema.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 4: Non-existent patient returns HTTP 404 Not Found
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Non-existent patient returns HTTP 404 Not Found...")
    not_found_resp = client.post(
        "/rag/ask",
        headers=auth_headers,
        json={"patient_id": 99999, "question": "What is the patient's medical history?"},
    )
    assert not_found_resp.status_code == 404, f"Expected 404, got {not_found_resp.status_code}"
    assert "does not exist" in not_found_resp.json()["detail"]
    print("  [PASS] Non-existent patient safely rejected with HTTP 404 Not Found.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 5: Invalid patient ID / question returns HTTP 422 Unprocessable Entity
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Invalid request parameters return HTTP 422...")
    invalid_id_resp = client.post(
        "/rag/ask",
        headers=auth_headers,
        json={"patient_id": 0, "question": "Valid length question"},
    )
    assert invalid_id_resp.status_code == 422, f"Expected 422, got {invalid_id_resp.status_code}"

    invalid_q_resp = client.post(
        "/rag/ask",
        headers=auth_headers,
        json={"patient_id": 1, "question": "hi"},  # question < 3 chars
    )
    assert invalid_q_resp.status_code == 422, f"Expected 422, got {invalid_q_resp.status_code}"
    print("  [PASS] Invalid inputs (patient_id=0, question < 3 chars) rejected with HTTP 422.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 6: Patient data isolation is maintained
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Patient data isolation verification...")
    mock_answer_p2 = (
        "Patient Lakshmi Priya had a visit on Oct 1, 2026 [S1] presenting with headaches. "
        "Blood pressure was recorded as 160/100 mmHg [S2] with glucose 95.0 mg/dL."
    )
    with patch("app.services.rag_service.generate_rag_answer", return_value=mock_answer_p2):
        resp_p2 = client.post(
            "/rag/ask",
            headers=auth_headers,
            json={"patient_id": 2, "question": "Summarize this patient's medical history."},
        )
    assert resp_p2.status_code == 200
    data_p2 = resp_p2.json()

    # Verify Patient 2 response and sources NEVER contain Patient 1 information
    assert data_p2["patient_name"] == "Lakshmi Priya"
    assert "Arun Kumar" not in str(data_p2)
    assert "CARE-PAT-001" not in str(data_p2)
    assert "140/90" not in str(data_p2)
    assert "lab_glucose_report.pdf" not in str(data_p2)
    print("  [PASS] Strict patient isolation maintained: Patient #2 response contains zero Patient #1 data.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 7: Patient with zero visits receives safe response
    # -------------------------------------------------------------------------
    print("\n[TEST 7] Patient with zero visits receives safe non-hallucinating response...")
    resp_zero = client.post(
        "/rag/ask",
        headers=auth_headers,
        json={"patient_id": 3, "question": "What were the patient's previous clinical measurements?"},
    )
    assert resp_zero.status_code == 200
    data_zero = resp_zero.json()
    assert data_zero["patient_id"] == 3
    assert data_zero["sources"] == []
    assert data_zero["data_summary"]["total_visits_retrieved"] == 0
    assert "No documented clinical visits" in data_zero["answer"]
    print("  [PASS] Zero-visit patient returned safe deterministic advice with 0 sources.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 8: Source identifiers and source metadata are returned
    # -------------------------------------------------------------------------
    print("\n[TEST 8] Source identifiers and source metadata verification...")
    sources = data["sources"]
    assert len(sources) == 5, f"Expected 5 sources, got {len(sources)}"
    source_ids = [s["source_id"] for s in sources]
    assert source_ids == ["S1", "S2", "S3", "S4", "S5"]

    # Verify source details
    meas_source = next(s for s in sources if s["source_id"] == "S2")
    assert meas_source["record_type"] == "Clinical Measurement"
    assert meas_source["visit_id"] == 101
    assert meas_source["visit_date"] == "2026-09-01"
    assert meas_source["parameters"]["systolic_bp"] == 140
    assert meas_source["parameters"]["blood_glucose"] == 160.0

    report_source = next(s for s in sources if s["source_id"] == "S3")
    assert report_source["record_type"] == "Medical Report"
    assert report_source["parameters"]["file_name"] == "lab_glucose_report.pdf"
    print("  [PASS] Structured sources returned with deterministic IDs, dates, and parameters.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 9: Retrieval method is 'structured_longitudinal_retrieval'
    # -------------------------------------------------------------------------
    print("\n[TEST 9] Retrieval method identifier verification...")
    assert data["retrieval_method"] == "structured_longitudinal_retrieval"
    assert data_zero["retrieval_method"] == "structured_longitudinal_retrieval"
    print("  [PASS] Retrieval method explicitly identified as 'structured_longitudinal_retrieval'.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 10: Gemini API failure is handled safely
    # -------------------------------------------------------------------------
    print("\n[TEST 10] Gemini API failure handled safely without exposing secrets/stack traces...")
    from app.services.rag_service import AIServiceError

    with patch("app.services.rag_service.generate_rag_answer", side_effect=AIServiceError("AI generation failed")):
        error_resp = client.post(
            "/rag/ask",
            headers=auth_headers,
            json={"patient_id": 1, "question": "Compare clinical measurements."},
        )
    assert error_resp.status_code == 502, f"Expected 502, got {error_resp.status_code}"
    err_body = error_resp.json()
    assert "The AI service could not generate a response" in err_body["detail"]
    assert "Traceback" not in error_resp.text
    assert "GEMINI_API_KEY" not in error_resp.text
    print("  [PASS] LLM failure gracefully mapped to HTTP 502 Bad Gateway without leaking internal details.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 11: Clinical safety disclaimer is present
    # -------------------------------------------------------------------------
    print("\n[TEST 11] Mandatory clinical safety disclaimer verification...")
    disclaimer = data["disclaimer"]
    assert "clinical decision-support prototype" in disclaimer
    assert "not an autonomous diagnostic system" in disclaimer
    assert "responsibility of the licensed healthcare professional" in disclaimer
    print("  [PASS] Mandatory healthcare decision-support safety disclaimer verified.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 12: Existing Clinical Copilot endpoint remains functional
    # -------------------------------------------------------------------------
    print("\n[TEST 12] Existing Clinical Copilot endpoint (POST /clinical-copilot/ask) compatibility...")
    copilot_mock_answer = "CareTrack AI Copilot: Patient Arun Kumar has documented visits."
    with patch("app.api.clinical_copilot.ask_clinical_copilot", return_value=copilot_mock_answer):
        copilot_resp = client.post(
            "/clinical-copilot/ask",
            headers=auth_headers,
            json={"patient_id": 1, "question": "Summarize the patient's documented visits."},
        )
    assert copilot_resp.status_code == 200, f"Copilot failed: {copilot_resp.status_code}: {copilot_resp.text}"
    copilot_data = copilot_resp.json()
    assert copilot_data["patient_id"] == 1
    assert copilot_data["patient_name"] == "Arun Kumar"
    assert "CareTrack AI Copilot" in copilot_data["answer"]
    print("  [PASS] Existing Clinical Copilot endpoint operates normally with 100% backward compatibility.")
    passed += 1

    print("\n" + "=" * 75)
    print(f"PHASE 2 TEST RESULTS: {passed}/{total} TESTS PASSED (100% SUCCESS)!")
    print("=" * 75)
    return passed == total


if __name__ == "__main__":
    success = run_api_tests()
    if not success:
        sys.exit(1)
