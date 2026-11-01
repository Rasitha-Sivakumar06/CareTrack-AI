import logging
import os
from pathlib import Path
import time
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import errors
from sqlalchemy.orm import Session

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

logger = logging.getLogger(__name__)

# Load environment configuration from backend/.env
BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(BACKEND_ENV)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0


class PatientNotFoundError(ValueError):
    """Raised when the requested patient is not found in the database."""
    pass


class AIServiceError(RuntimeError):
    """Raised when the LLM service fails to generate a response."""
    pass


def retrieve_patient_longitudinal_records(
    db: Session,
    patient_id: int,
) -> dict[str, Any]:
    """
    Retrieve all clinical records strictly belonging to the requested patient.

    Security & Data Isolation:
    - Queries the Patient table specifically for patient_id.
    - Queries Visits strictly where Visit.patient_id == patient_id.
    - Queries ClinicalMeasurements strictly where ClinicalMeasurement.patient_id == patient_id.
    - Queries MedicalReports strictly for visit_ids that belong to this patient.
    Cross-patient record contamination is physically impossible.
    """
    # 1. Verify patient exists
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise PatientNotFoundError(f"Patient with ID {patient_id} does not exist.")

    # 2. Retrieve all visits in chronological order
    visits = (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_date.asc(), Visit.id.asc())
        .all()
    )

    visit_ids = [v.id for v in visits]

    # 3. Retrieve clinical measurements strictly for this patient and their visits
    measurements_by_visit: dict[int, list[ClinicalMeasurement]] = {vid: [] for vid in visit_ids}
    if visit_ids:
        measurements = (
            db.query(ClinicalMeasurement)
            .filter(
                ClinicalMeasurement.patient_id == patient_id,
                ClinicalMeasurement.visit_id.in_(visit_ids),
            )
            .order_by(
                ClinicalMeasurement.measured_at.asc().nullslast(),
                ClinicalMeasurement.created_at.asc(),
                ClinicalMeasurement.id.asc(),
            )
            .all()
        )
        for m in measurements:
            if m.visit_id in measurements_by_visit:
                measurements_by_visit[m.visit_id].append(m)

    # 4. Retrieve medical reports strictly attached to this patient's visits
    reports_by_visit: dict[int, list[MedicalReport]] = {vid: [] for vid in visit_ids}
    if visit_ids:
        reports = (
            db.query(MedicalReport)
            .filter(MedicalReport.visit_id.in_(visit_ids))
            .order_by(MedicalReport.created_at.asc(), MedicalReport.id.asc())
            .all()
        )
        # Deduplicate reports that share identical file_name and extracted_text
        seen_reports: set[tuple[int, str, str]] = set()
        for r in reports:
            key = (r.visit_id, r.file_name or "", (r.extracted_text or "").strip())
            if key not in seen_reports:
                seen_reports.add(key)
                reports_by_visit[r.visit_id].append(r)

    return {
        "patient": patient,
        "visits": visits,
        "measurements_by_visit": measurements_by_visit,
        "reports_by_visit": reports_by_visit,
    }


def build_structured_evidence(
    patient: Patient,
    visits: list[Visit],
    measurements_by_visit: dict[int, list[ClinicalMeasurement]],
    reports_by_visit: dict[int, list[MedicalReport]],
) -> tuple[list[RAGSourceRecord], DataSummary, str]:
    """
    Transform raw database records into indexed clinical evidence chunks with
    deterministic source identifiers ([S1], [S2], ...), structured metadata,
    and a formatted prompt context.
    """
    sources: list[RAGSourceRecord] = []
    data_gap_warnings: list[str] = []
    source_counter = 1

    # Edge case: Patient has zero recorded visits
    if not visits:
        summary = DataSummary(
            total_visits_retrieved=0,
            total_measurements_retrieved=0,
            total_reports_retrieved=0,
            has_sufficient_history=False,
            earliest_visit_date=None,
            latest_visit_date=None,
            data_gap_warnings=["No documented clinical visits found for this patient."],
        )
        context = (
            f"PATIENT PROFILE:\n"
            f"- Name: {patient.name}\n"
            f"- Patient Code: {patient.patient_code}\n"
            f"- Age: {patient.age if patient.age is not None else 'Unrecorded'}\n"
            f"- Gender: {patient.gender or 'Unrecorded'}\n"
            f"- Location: {patient.location or 'Unrecorded'}\n\n"
            f"LONGITUDINAL CLINICAL RECORDS:\n"
            f"No clinical visits, measurements, encounter notes, or medical reports are on record."
        )
        return sources, summary, context

    total_measurements = 0
    total_reports = 0
    context_chunks: list[str] = []

    context_chunks.append(
        f"PATIENT PROFILE:\n"
        f"- Name: {patient.name}\n"
        f"- Patient Code: {patient.patient_code}\n"
        f"- Age: {patient.age if patient.age is not None else 'Unrecorded'}\n"
        f"- Gender: {patient.gender or 'Unrecorded'}\n"
        f"- Location: {patient.location or 'Unrecorded'}\n"
    )
    context_chunks.append("RETRIEVED LONGITUDINAL CLINICAL RECORDS (CHRONOLOGICAL ORDER):")

    for visit in visits:
        v_date_str = visit.visit_date.isoformat() if visit.visit_date else "Unknown Date"
        visit_header = f"--- Visit #{visit.id} (Date: {v_date_str}) ---"
        context_chunks.append(visit_header)

        # 1. Clinical Encounter Notes Chunk
        encounter_has_content = bool(visit.symptoms or visit.clinical_notes or visit.follow_up_notes)
        if encounter_has_content:
            source_id = f"S{source_counter}"
            source_counter += 1

            symptoms_text = visit.symptoms.strip() if visit.symptoms else "None recorded"
            notes_text = visit.clinical_notes.strip() if visit.clinical_notes else "None recorded"
            follow_up_text = visit.follow_up_notes.strip() if visit.follow_up_notes else "None recorded"

            encounter_summary = (
                f"Encounter #{visit.id} on {v_date_str}: Symptoms: {symptoms_text}; "
                f"Clinical Notes: {notes_text}; Follow-up: {follow_up_text}"
            )

            sources.append(
                RAGSourceRecord(
                    source_id=source_id,
                    record_type="Clinical Encounter",
                    visit_id=visit.id,
                    visit_date=visit.visit_date,
                    summary=encounter_summary,
                    parameters={
                        "symptoms": visit.symptoms,
                        "clinical_notes": visit.clinical_notes,
                        "follow_up_notes": visit.follow_up_notes,
                    },
                )
            )

            context_chunks.append(
                f"[{source_id}] Visit #{visit.id} ({v_date_str}) — Clinical Encounter:\n"
                f"  - Symptoms: {symptoms_text}\n"
                f"  - Clinical Notes: {notes_text}\n"
                f"  - Follow-up Notes: {follow_up_text}"
            )

        # 2. Clinical Measurements Chunks
        visit_measurements = measurements_by_visit.get(visit.id, [])
        total_measurements += len(visit_measurements)

        for m in visit_measurements:
            source_id = f"S{source_counter}"
            source_counter += 1

            # Format parameters and inspect missing values
            params: dict[str, Any] = {}
            parts: list[str] = []

            if m.blood_pressure or (m.systolic_bp and m.diastolic_bp):
                bp_display = m.blood_pressure or f"{m.systolic_bp}/{m.diastolic_bp}"
                parts.append(f"Blood Pressure: {bp_display} mmHg")
                params["blood_pressure"] = bp_display
            if m.systolic_bp is not None:
                params["systolic_bp"] = m.systolic_bp
            if m.diastolic_bp is not None:
                params["diastolic_bp"] = m.diastolic_bp

            if m.blood_glucose is not None:
                parts.append(f"Blood Glucose: {m.blood_glucose} mg/dL")
                params["blood_glucose"] = m.blood_glucose

            if m.hemoglobin is not None:
                parts.append(f"Hemoglobin: {m.hemoglobin} g/dL")
                params["hemoglobin"] = m.hemoglobin

            if m.heart_rate is not None:
                parts.append(f"Heart Rate: {m.heart_rate} bpm")
                params["heart_rate"] = m.heart_rate

            if m.temperature is not None:
                parts.append(f"Temperature: {m.temperature} °C")
                params["temperature"] = m.temperature

            if m.oxygen_saturation is not None:
                parts.append(f"SpO2: {m.oxygen_saturation}%")
                params["oxygen_saturation"] = m.oxygen_saturation

            if m.weight is not None:
                parts.append(f"Weight: {m.weight} kg")
                params["weight"] = m.weight

            time_desc = (
                m.measured_at.strftime("%Y-%m-%d %H:%M:%S")
                if m.measured_at
                else "Measurement time unrecorded"
            )
            if not m.measured_at:
                data_gap_warnings.append(
                    f"Visit #{visit.id} Measurement #{m.id}: timestamp missing."
                )

            params["measured_at"] = m.measured_at.isoformat() if m.measured_at else None

            meas_summary = (
                f"Measurements on {v_date_str} (Timing: {time_desc}): "
                + ("; ".join(parts) if parts else "No specific vitals recorded")
            )

            sources.append(
                RAGSourceRecord(
                    source_id=source_id,
                    record_type="Clinical Measurement",
                    visit_id=visit.id,
                    visit_date=visit.visit_date,
                    summary=meas_summary,
                    parameters=params,
                )
            )

            details_lines = "\n".join(f"  - {p}" for p in parts) if parts else "  - (No vital values recorded)"
            context_chunks.append(
                f"[{source_id}] Visit #{visit.id} ({v_date_str}) — Clinical Measurement (Recorded: {time_desc}):\n"
                f"{details_lines}"
            )

        # 3. Medical Reports Chunks
        visit_reports = reports_by_visit.get(visit.id, [])
        total_reports += len(visit_reports)

        for r in visit_reports:
            source_id = f"S{source_counter}"
            source_counter += 1

            extracted_snippet = (
                r.extracted_text.strip()
                if r.extracted_text and r.extracted_text.strip()
                else "No extracted text available for this report."
            )
            # Limit snippet size in context to prevent overflowing prompt while preserving key findings
            short_snippet = extracted_snippet[:500] + ("..." if len(extracted_snippet) > 500 else "")

            rep_summary = (
                f"Medical Report on {v_date_str}: {r.file_name or 'Document'} "
                f"({r.file_type or 'Unknown type'}). Snippet: {short_snippet[:150]}"
            )

            sources.append(
                RAGSourceRecord(
                    source_id=source_id,
                    record_type="Medical Report",
                    visit_id=visit.id,
                    visit_date=visit.visit_date,
                    summary=rep_summary,
                    parameters={
                        "file_name": r.file_name,
                        "file_type": r.file_type,
                        "report_id": r.id,
                    },
                )
            )

            context_chunks.append(
                f"[{source_id}] Visit #{visit.id} ({v_date_str}) — Medical Report ({r.file_name or 'Document'}, {r.file_type or 'type'}):\n"
                f"  Extracted content:\n  {short_snippet}"
            )

    earliest_date = visits[0].visit_date if visits else None
    latest_date = visits[-1].visit_date if visits else None
    has_sufficient_history = len(visits) >= 2

    if not has_sufficient_history:
        data_gap_warnings.append(
            "Only 1 visit on record. There is insufficient longitudinal data to establish a visit-to-visit trajectory."
        )

    summary = DataSummary(
        total_visits_retrieved=len(visits),
        total_measurements_retrieved=total_measurements,
        total_reports_retrieved=total_reports,
        has_sufficient_history=has_sufficient_history,
        earliest_visit_date=earliest_date,
        latest_visit_date=latest_date,
        data_gap_warnings=data_gap_warnings,
    )

    full_context = "\n\n".join(context_chunks)
    return sources, summary, full_context


def generate_rag_answer(
    question: str,
    patient_context: str,
    has_history: bool,
    gemini_client: Any | None = None,
) -> str:
    """
    Generate a grounded clinical response using the retrieved records.
    If the patient has no recorded visits, returns safe deterministic advice
    without unnecessary external API invocation.
    """
    # Safe zero-visit shortcut: zero hallucination, zero API latency
    if not has_history:
        return (
            "No documented clinical visits, measurements, or medical reports are currently "
            "available in CareTrack AI for this patient. There is no historical clinical data "
            "available to answer your question. Please register an initial clinical visit and "
            "record baseline vital signs."
        )

    # Initialize Gemini client if not injected (dependency injection enabled for unit testing)
    client = gemini_client
    if client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise AIServiceError("GEMINI_API_KEY is not configured in the backend environment.")
        client = genai.Client(api_key=api_key)

    prompt = f"""
You are CareTrack AI, an AI-powered longitudinal healthcare and clinical decision-support assistant.
You are assisting a licensed physician who is reviewing a patient's historical medical records.

STRICT CLINICAL SAFETY RULES:
1. Grounding: Answer ONLY using the retrieved patient record context provided below.
2. Zero Hallucination: NEVER invent patient history, measurements, vital signs, lab values, dates, visit IDs, diagnoses, or prescriptions.
3. Missing Information: If any information asked by the doctor is missing, unrecorded, or insufficient, state explicitly that it is not documented in the available records.
4. Facts vs Inferences: Clearly distinguish documented clinical facts from general clinical observations.
5. Non-Diagnostic Boundary: Do not formulate autonomous medical diagnoses or prescribe medications/dosages. Frame your response as clinical decision support.
6. Evidence Citations: Whenever citing a documented fact, measurement, visit date, or report finding, include the corresponding source identifier (e.g. [S1], [S2]) directly in your sentence.
7. Longitudinal Comparison: When comparing measurements across visits (e.g., earlier vs latest), clearly cite both sources (e.g., [S1] and [S3]) with their respective visit dates and numerical deltas.
8. Clinician Responsibility: Clinical review, diagnosis, and treatment decisions remain the sole responsibility of the treating clinician.

RETRIEVED PATIENT RECORD CONTEXT:
{patient_context}

DOCTOR'S QUESTION:
{question}

Provide a concise, professional, evidence-based clinical answer citing the source identifiers ([S1], [S2], etc.) for each factual statement.
"""

    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            answer_text = response.text
            if not answer_text or not answer_text.strip():
                raise AIServiceError("Gemini returned an empty response.")
            return answer_text.strip()

        except errors.ServerError as exc:
            last_exception = exc
            if attempt < MAX_RETRIES - 1:
                delay = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Gemini ServerError (%s). Retrying in %.1fs (attempt %d/%d)...",
                    getattr(exc, "code", "unknown"),
                    delay,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(delay)
            else:
                logger.error("Gemini retries exhausted.")
                raise AIServiceError(f"AI service temporarily unavailable: {exc}") from exc

        except errors.APIError as exc:
            last_exception = exc
            if getattr(exc, "code", None) in (429, 503, 504) and attempt < MAX_RETRIES - 1:
                delay = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Gemini API rate limit or service error (%s). Retrying in %.1fs...",
                    exc.code,
                    delay,
                )
                time.sleep(delay)
            else:
                raise AIServiceError(f"Gemini API error: {exc.message if hasattr(exc, 'message') else exc}") from exc

        except (TimeoutError, ConnectionError) as exc:
            last_exception = exc
            if attempt < MAX_RETRIES - 1:
                delay = INITIAL_BACKOFF * (2 ** attempt)
                time.sleep(delay)
            else:
                raise AIServiceError("Network connection to Gemini AI timed out.") from exc

        except Exception as exc:
            # Re-raise if already an AIServiceError
            if isinstance(exc, AIServiceError):
                raise
            logger.error("Unexpected error in Gemini generation: %s", type(exc).__name__)
            raise AIServiceError(f"Failed to generate response: {type(exc).__name__}") from exc

    if last_exception:
        raise AIServiceError(f"AI generation failed: {last_exception}")
    raise AIServiceError("AI generation failed after maximum retries.")


def execute_rag_query(
    db: Session,
    request: RAGQuestionRequest,
    gemini_client: Any | None = None,
) -> RAGQueryResponse:
    """
    End-to-End Structured Longitudinal RAG Workflow:
    1. Retrieve records only for requested patient ID.
    2. Build structured evidence chunks, source IDs ([S1], [S2]...), and context.
    3. Generate grounded answer via Gemini (or safe deterministic answer if 0 visits).
    4. Return complete RAGQueryResponse.
    """
    # 1. Retrieval
    records = retrieve_patient_longitudinal_records(db=db, patient_id=request.patient_id)
    patient: Patient = records["patient"]
    visits: list[Visit] = records["visits"]
    measurements_by_visit = records["measurements_by_visit"]
    reports_by_visit = records["reports_by_visit"]

    # 2. Evidence Chunking & Context Formulation
    sources, data_summary, context = build_structured_evidence(
        patient=patient,
        visits=visits,
        measurements_by_visit=measurements_by_visit,
        reports_by_visit=reports_by_visit,
    )

    # 3. Grounded Answer Generation
    answer = generate_rag_answer(
        question=request.question.strip(),
        patient_context=context,
        has_history=data_summary.total_visits_retrieved > 0,
        gemini_client=gemini_client,
    )

    # 4. Assemble Response
    return RAGQueryResponse(
        patient_id=patient.id,
        patient_code=patient.patient_code,
        patient_name=patient.name,
        question=request.question.strip(),
        answer=answer,
        sources=sources,
        retrieval_method="structured_longitudinal_retrieval",
        data_summary=data_summary,
    )
