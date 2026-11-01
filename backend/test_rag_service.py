"""
CareTrack AI — Phase 1 Test Suite for Structured RAG Service and Schemas

Tests:
1. Successful retrieval for a patient with multiple visits.
2. Correct chronological ordering of clinical encounters and measurements.
3. Source ID generation (sequential [S1], [S2], [S3] identifiers).
4. Correct source metadata (record_type, visit_id, visit_date, parameters, summary).
5. Patient-specific data isolation (strict boundary verification preventing cross-patient leakage).
6. Patient with zero visits (safe handling, zero hallucination, zero Gemini call).
7. Missing measurements and missing report text (graceful handling without invented values).
8. Gemini unavailable or API failure handling (safe error propagation).
9. Grounding and non-diagnostic prompt instructions (verification of safety guidelines in prompt).
"""

from datetime import date, datetime, timezone
from pathlib import Path
import sys
from unittest.mock import MagicMock

# Configure stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.clinical_measurement import ClinicalMeasurement
from app.models.medical_report import MedicalReport
from app.models.patient import Patient
from app.models.visit import Visit
from app.schemas.rag import (
    DataSummary,
    RAGQueryResponse,
    RAGQuestionRequest,
    RAGSourceRecord,
)
from app.services.rag_service import (
    AIServiceError,
    PatientNotFoundError,
    build_structured_evidence,
    execute_rag_query,
    generate_rag_answer,
    retrieve_patient_longitudinal_records,
)

# Map BigInteger to INTEGER in SQLite so autoincrement primary keys function properly in test memory
@compiles(BigInteger, "sqlite")
def compile_big_int_sqlite(type_, compiler, **kw):
    return "INTEGER"


def setup_test_db():
    """Create a clean in-memory SQLite database populated with controlled test fixtures."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()

    # --- Fixture 1: Patient A (Multi-Visit Longitudinal Patient) ---
    patient_a = Patient(
        id=1,
        patient_code="CARE-PAT-001",
        name="Arun Kumar",
        age=45,
        gender="Male",
        phone="9876543210",
        location="Coimbatore",
    )
    db.add(patient_a)

    # Visit 1 (Baseline - 2026-09-01)
    v1 = Visit(
        id=101,
        patient_id=1,
        visit_date=date(2026, 9, 1),
        symptoms="Mild fatigue, increased thirst",
        clinical_notes="Baseline consultation. Ordered fasting glucose and vitals.",
        follow_up_notes="Review in 4 weeks.",
    )
    # Visit 2 (Follow-up - 2026-10-15)
    v2 = Visit(
        id=102,
        patient_id=1,
        visit_date=date(2026, 10, 15),
        symptoms="Fatigue improved",
        clinical_notes="Follow-up consultation. Glucose reduced after lifestyle intervention.",
        follow_up_notes="Continue dietary monitoring.",
    )
    db.add_all([v1, v2])
    db.flush()

    # Measurements for Patient A
    m1 = ClinicalMeasurement(
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
    m2 = ClinicalMeasurement(
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
    db.add_all([m1, m2])

    # Report for Patient A Visit 1
    r1 = MedicalReport(
        id=501,
        visit_id=101,
        file_name="fasting_lab_report.pdf",
        file_type="application/pdf",
        extracted_text="LAB REPORT: Fasting Glucose 160 mg/dL, HbA1c 7.2%, Hemoglobin 13.5 g/dL",
    )
    db.add(r1)

    # --- Fixture 2: Patient B (Isolated Patient with distinct data) ---
    patient_b = Patient(
        id=2,
        patient_code="CARE-PAT-002",
        name="Lakshmi Priya",
        age=38,
        gender="Female",
        phone="9876543211",
        location="Madurai",
    )
    db.add(patient_b)

    v_b = Visit(
        id=201,
        patient_id=2,
        visit_date=date(2026, 10, 1),
        symptoms="Headache and dizziness",
        clinical_notes="Hypertension assessment.",
        follow_up_notes="Monitor BP daily.",
    )
    db.add(v_b)
    db.flush()

    m_b = ClinicalMeasurement(
        id=2001,
        patient_id=2,
        visit_id=201,
        blood_pressure="160/100",
        systolic_bp=160,
        diastolic_bp=100,
        blood_glucose=95.0,
        measured_at=datetime(2026, 10, 1, 11, 0, tzinfo=timezone.utc),
    )
    db.add(m_b)

    # --- Fixture 3: Patient C (Zero-Visit Patient) ---
    patient_c = Patient(
        id=3,
        patient_code="CARE-PAT-003",
        name="New Registration",
        age=29,
        gender="Male",
        phone="9876543212",
        location="Salem",
    )
    db.add(patient_c)

    # --- Fixture 4: Patient D (Missing Data Edge Cases) ---
    patient_d = Patient(
        id=4,
        patient_code="CARE-PAT-004",
        name="Incomplete Data Patient",
        age=50,
        gender="Female",
        phone="9876543213",
        location="Chennai",
    )
    db.add(patient_d)

    v_d = Visit(
        id=301,
        patient_id=4,
        visit_date=date(2026, 10, 20),
        symptoms=None,  # missing symptoms
        clinical_notes=None,  # missing notes
        follow_up_notes=None,
    )
    db.add(v_d)
    db.flush()

    m_d = ClinicalMeasurement(
        id=3001,
        patient_id=4,
        visit_id=301,
        blood_pressure=None,
        systolic_bp=None,
        diastolic_bp=None,
        blood_glucose=140.0,  # only glucose provided
        hemoglobin=None,
        heart_rate=None,
        temperature=None,
        oxygen_saturation=None,
        weight=None,
        measured_at=None,  # missing timestamp
    )
    r_d = MedicalReport(
        id=601,
        visit_id=301,
        file_name="empty_report.pdf",
        file_type="application/pdf",
        extracted_text=None,  # missing extracted text
    )
    db.add_all([m_d, r_d])

    db.commit()
    return db


def create_mock_gemini_client(return_text: str):
    """Create a mock Gemini client returning deterministic content."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = return_text
    mock_client.models.generate_content.return_value = mock_response
    return mock_client


def run_all_tests():
    print("=" * 75)
    print("CARETRACK AI — PHASE 1: STRUCTURED RAG SERVICE & SCHEMAS TEST SUITE")
    print("=" * 75)

    db = setup_test_db()
    passed = 0
    total = 9

    # -------------------------------------------------------------------------
    # TEST 1: Successful retrieval for a patient with multiple visits
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Successful retrieval for patient with multiple visits...")
    records = retrieve_patient_longitudinal_records(db=db, patient_id=1)
    assert records["patient"].id == 1, "Patient ID mismatch"
    assert len(records["visits"]) == 2, f"Expected 2 visits, found {len(records['visits'])}"
    assert len(records["measurements_by_visit"][101]) == 1, "Visit 101 measurement missing"
    assert len(records["measurements_by_visit"][102]) == 1, "Visit 102 measurement missing"
    assert len(records["reports_by_visit"][101]) == 1, "Visit 101 report missing"
    print("  [PASS] Retrieved patient record with 2 visits, 2 measurements, and 1 report.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 2: Correct chronological ordering
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Correct chronological ordering of longitudinal records...")
    visits = records["visits"]
    assert visits[0].visit_date < visits[1].visit_date, "Visits not in chronological order"
    assert visits[0].visit_date == date(2026, 9, 1), "Earliest visit date incorrect"
    assert visits[1].visit_date == date(2026, 10, 15), "Latest visit date incorrect"
    print(f"  [PASS] Chronological order verified: {visits[0].visit_date} -> {visits[1].visit_date}.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 3: Source ID generation ([S1], [S2], [S3], ...)
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Sequential source ID generation ([S1], [S2], ...)...")
    sources, data_summary, context = build_structured_evidence(
        patient=records["patient"],
        visits=records["visits"],
        measurements_by_visit=records["measurements_by_visit"],
        reports_by_visit=records["reports_by_visit"],
    )
    source_ids = [s.source_id for s in sources]
    expected_ids = ["S1", "S2", "S3", "S4", "S5"]
    assert source_ids == expected_ids, f"Expected {expected_ids}, got {source_ids}"
    assert "[S1]" in context, "[S1] missing from formatted context"
    assert "[S2]" in context, "[S2] missing from formatted context"
    print(f"  [PASS] Deterministic sequential source IDs verified: {source_ids}.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 4: Correct source metadata and parameters
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Correct source metadata and clinical parameters...")
    s1 = sources[0]  # Encounter Visit 1
    assert s1.record_type == "Clinical Encounter"
    assert s1.visit_id == 101
    assert s1.visit_date == date(2026, 9, 1)
    assert "Mild fatigue" in s1.summary

    s2 = sources[1]  # Measurement Visit 1
    assert s2.record_type == "Clinical Measurement"
    assert s2.parameters["blood_pressure"] == "140/90"
    assert s2.parameters["blood_glucose"] == 160.0
    assert s2.parameters["systolic_bp"] == 140

    s3 = sources[2]  # Report Visit 1
    assert s3.record_type == "Medical Report"
    assert s3.parameters["file_name"] == "fasting_lab_report.pdf"

    s4 = sources[3]  # Encounter Visit 2
    assert s4.record_type == "Clinical Encounter"
    assert s4.visit_id == 102

    s5 = sources[4]  # Measurement Visit 2
    assert s5.record_type == "Clinical Measurement"
    assert s5.parameters["blood_pressure"] == "125/80"
    assert s5.parameters["blood_glucose"] == 115.0

    assert data_summary.has_sufficient_history is True
    assert data_summary.total_visits_retrieved == 2
    assert data_summary.total_measurements_retrieved == 2
    assert data_summary.total_reports_retrieved == 1
    print("  [PASS] Source metadata verified (record_type, visit_id, visit_date, parameters).")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 5: Patient-specific data isolation (No cross-patient contamination)
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Patient-specific data isolation verification...")
    records_b = retrieve_patient_longitudinal_records(db=db, patient_id=2)
    sources_b, summary_b, context_b = build_structured_evidence(
        patient=records_b["patient"],
        visits=records_b["visits"],
        measurements_by_visit=records_b["measurements_by_visit"],
        reports_by_visit=records_b["reports_by_visit"],
    )

    # Verify Patient 2 context contains NO data from Patient 1
    assert "Arun Kumar" not in context_b, "Patient A name leaked into Patient B context!"
    assert "160.0 mg/dL" not in context_b, "Patient A glucose leaked into Patient B context!"
    assert "fasting_lab_report.pdf" not in context_b, "Patient A report leaked into Patient B context!"
    assert "Lakshmi Priya" in context_b, "Patient B name missing from Patient B context"
    assert "160/100" in context_b, "Patient B blood pressure missing from Patient B context"

    # Verify Patient 1 context contains NO data from Patient 2
    assert "Lakshmi Priya" not in context, "Patient B name leaked into Patient A context!"
    assert "160/100" not in context, "Patient B BP leaked into Patient A context!"
    print("  [PASS] Complete data isolation: zero leakage between Patient #1 and Patient #2.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 6: Patient with zero visits (Empty State Handling)
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Patient with zero visits (Safe non-hallucinating handling)...")
    records_c = retrieve_patient_longitudinal_records(db=db, patient_id=3)
    sources_c, summary_c, context_c = build_structured_evidence(
        patient=records_c["patient"],
        visits=records_c["visits"],
        measurements_by_visit=records_c["measurements_by_visit"],
        reports_by_visit=records_c["reports_by_visit"],
    )
    assert len(sources_c) == 0, "Expected 0 sources for patient with 0 visits"
    assert summary_c.total_visits_retrieved == 0
    assert summary_c.has_sufficient_history is False
    assert len(summary_c.data_gap_warnings) > 0

    # Ensure zero-visit query returns deterministic guidance without invoking Gemini
    mock_gemini = MagicMock()
    req_c = RAGQuestionRequest(patient_id=3, question="What was this patient's previous glucose level?")
    resp_c = execute_rag_query(db=db, request=req_c, gemini_client=mock_gemini)

    # Gemini must NOT have been called
    mock_gemini.models.generate_content.assert_not_called()
    assert "No documented clinical visits" in resp_c.answer
    assert resp_c.sources == []
    assert resp_c.data_summary.total_visits_retrieved == 0
    assert resp_c.retrieval_method == "structured_longitudinal_retrieval"
    print("  [PASS] Zero-visit patient returned safe clinical guidance without Gemini API call.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 7: Missing measurements and missing report text
    # -------------------------------------------------------------------------
    print("\n[TEST 7] Handling missing measurements, timestamps, and report text...")
    records_d = retrieve_patient_longitudinal_records(db=db, patient_id=4)
    sources_d, summary_d, context_d = build_structured_evidence(
        patient=records_d["patient"],
        visits=records_d["visits"],
        measurements_by_visit=records_d["measurements_by_visit"],
        reports_by_visit=records_d["reports_by_visit"],
    )
    # Check that missing timestamp was flagged in data gap warnings
    has_timestamp_warning = any("timestamp missing" in w for w in summary_d.data_gap_warnings)
    assert has_timestamp_warning, "Expected timestamp warning for missing measured_at"

    # Check that empty report text did not crash context builder
    report_sources = [s for s in sources_d if s.record_type == "Medical Report"]
    assert len(report_sources) == 1
    assert "empty_report.pdf" in report_sources[0].summary
    print("  [PASS] Missing values (BP=None, measured_at=None, text=None) handled gracefully.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 8: Gemini unavailable or API failure handling
    # -------------------------------------------------------------------------
    print("\n[TEST 8] Gemini API failure and exception handling...")
    failing_gemini = MagicMock()
    failing_gemini.models.generate_content.side_effect = RuntimeError("Service connection refused")

    req_fail = RAGQuestionRequest(patient_id=1, question="Compare glucose levels across visits.")
    try:
        execute_rag_query(db=db, request=req_fail, gemini_client=failing_gemini)
        assert False, "Expected AIServiceError was not raised!"
    except AIServiceError as err:
        assert "Failed to generate response" in str(err) or "AI generation failed" in str(err)
        print("  [PASS] AIServiceError safely raised and captured upon LLM failure.")
        passed += 1

    # -------------------------------------------------------------------------
    # TEST 9: Grounding, source citation, and non-diagnostic generation
    # -------------------------------------------------------------------------
    print("\n[TEST 9] Grounded generation with source markers and non-diagnostic disclaimers...")
    grounded_answer = (
        "Based on the patient's records, fasting blood glucose was 160.0 mg/dL during Visit #101 on September 1, 2026 [S2]. "
        "At the subsequent follow-up Visit #102 on October 15, 2026, glucose decreased to 115.0 mg/dL [S5], "
        "representing an improvement of -45.0 mg/dL. "
        "Blood pressure also decreased from 140/90 mmHg [S2] to 125/80 mmHg [S5]. "
        "These documented findings should be verified against the original laboratory reports [S3]. "
        "This response provides clinical decision support and does not constitute a medical diagnosis."
    )
    mock_gemini_success = create_mock_gemini_client(grounded_answer)

    req_grounded = RAGQuestionRequest(
        patient_id=1,
        question="How have the patient's glucose levels and blood pressure changed across visits?"
    )
    resp = execute_rag_query(db=db, request=req_grounded, gemini_client=mock_gemini_success)

    # Verify Pydantic response attributes
    assert isinstance(resp, RAGQueryResponse)
    assert resp.patient_id == 1
    assert resp.patient_code == "CARE-PAT-001"
    assert resp.patient_name == "Arun Kumar"
    assert resp.retrieval_method == "structured_longitudinal_retrieval"
    assert len(resp.sources) == 5
    assert "[S2]" in resp.answer
    assert "[S5]" in resp.answer
    assert resp.disclaimer is not None
    assert "clinical decision-support prototype" in resp.disclaimer

    # Inspect the prompt passed to Gemini to ensure safety guidelines were injected
    call_args = mock_gemini_success.models.generate_content.call_args
    passed_prompt = call_args.kwargs.get("contents", "")
    assert "STRICT CLINICAL SAFETY RULES:" in passed_prompt
    assert "Grounding: Answer ONLY using the retrieved patient record context" in passed_prompt
    assert "Zero Hallucination: NEVER invent patient history" in passed_prompt
    assert "Non-Diagnostic Boundary: Do not formulate autonomous medical diagnoses" in passed_prompt
    assert "Evidence Citations: Whenever citing a documented fact" in passed_prompt
    print("  [PASS] Grounded answer generated with [S2], [S5] citations, non-diagnostic disclaimers, and safety prompt rules.")
    passed += 1

    print("\n" + "=" * 75)
    print(f"PHASE 1 TEST RESULTS: {passed}/{total} TESTS PASSED (100% SUCCESS)!")
    print("=" * 75)
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    if not success:
        sys.exit(1)
