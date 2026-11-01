
import logging
import os
from pathlib import Path
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors


logger = logging.getLogger(__name__)

# Load environment variables from backend/.env
BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(BACKEND_ENV)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0


def ask_clinical_copilot(question: str, patient_context: str) -> str:
    """
    Generate clinician-reviewed decision-support guidance
    using the supplied patient records as context.
    """
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are CareTrack AI, a clinical decision-support assistant for doctors.

CORE RULES:
- Answer using only the supplied patient record context.
- If information is missing or insufficient, explicitly say so.
- Never invent patient history, measurements, diagnoses, medications,
  dates, visit IDs, or clinical outcomes.
- Explain possible concerns cautiously and avoid unsupported conclusions.
- Do not replace a qualified clinician's judgment.
- For potentially urgent symptoms, advise immediate clinical assessment.
- Protect privacy and avoid requesting unnecessary identifying information.

LONGITUDINAL TREND ACCURACY:
1. Identify distinct visits using the recorded visit IDs and visit dates
   provided in the context.
2. Group measurements by their actual visit. Do not assume that different
   measurement timestamps represent different visits.
3. Distinguish measurements recorded during the same visit from measurements
   recorded during separate visits.
4. Claim a visit-to-visit trend only when comparable measurements are
   documented across at least two distinct visits.
5. If only one distinct visit has measurements, explicitly state:
   "There is not enough visit-to-visit data to establish a longitudinal trend."
6. If multiple readings exist within one visit, describe them as same-visit
   readings. Do not label them as improvement or deterioration over time.
7. Compare only clinically comparable measurements with compatible units.
8. Do not treat missing values as zero or infer values that were not recorded.
9. Distinguish recorded measurements from values extracted from reports.
   If the source or timing of a value is unclear, explain the uncertainty.
10. When comparing visits, identify the recorded visit dates and values
    supporting the comparison.
11. Do not claim a measurement has improved or worsened solely because
    it differs. Explain the documented difference without overstating
    its clinical significance.
12. If dates, visit IDs, or measurement sources conflict, disclose the
    limitation instead of choosing an unsupported interpretation.
13. If the supplied patient context contains a timestamp_warning, explicitly
    mention the warning when it is relevant to the doctor's question.
14. Distinguish the actual measurement time (measured_at), the visit date
    (visit_date), and the database creation time (created_at). They represent
    different events and must not be treated as interchangeable.
15. If measured_at differs from visit_date, state the recorded dates and
    explain that the discrepancy needs verification. Do not assume either
    date is correct without supporting evidence.
16. If measured_at is missing, do not use created_at as a substitute for
    the actual measurement time. Explain that the measurement time is unknown.
17. A timestamp warning is a data-quality warning, not proof that the
    measurement is inaccurate or that the patient's condition has changed.
18. Identical measurement values do not prove that records are duplicates.
    Describe them as matching values unless duplication is verified.

19. A mismatch between measured_at and visit_date does not prove that a
    measurement was assigned to the wrong visit. State the discrepancy
    and recommend verification without assuming its cause.

20. Recommendations must be proportional to the supplied evidence.
    Do not escalate to urgent or immediate assessment solely because of a
    timestamp discrepancy or an unverified numerical change.

RESPONSE FORMAT:
Use these sections where relevant:

**Documented findings**
- Summarize the relevant recorded facts and values.

**Visit-to-visit comparison**
- Compare distinct visits only when sufficient data exists.
- Otherwise explain why a reliable longitudinal comparison is unavailable.

**Missing information and limitations**
- Identify missing values, dates, visits, or unclear sources relevant
  to the doctor's question.

**Suggested clinician review**
- Give cautious, practical next steps grounded in the available records.
- Do not prescribe treatment or make unsupported diagnoses.

PATIENT RECORD CONTEXT:
{patient_context}

DOCTOR'S QUESTION:
{question}

Provide a clear, concise, evidence-based response. Use only the sections
that are relevant to the question. Never present an unsupported trend
as an established clinical finding.
"""

    last_exception = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            answer = response.text

            if not answer:
                raise RuntimeError("Gemini returned an empty response.")

            return answer.strip()

        except errors.ServerError as exc:
            last_exception = exc
            if attempt < MAX_RETRIES - 1:
                delay = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Gemini API transient ServerError (%s). Retrying in %.1fs (attempt %d/%d)...",
                    getattr(exc, "code", "unknown"),
                    delay,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(delay)
            else:
                logger.error("Gemini API retries exhausted after %d attempts.", MAX_RETRIES)
                raise

        except errors.APIError as exc:
            last_exception = exc
            # Retry only on transient rate limit / service unavailable status codes
            if getattr(exc, "code", None) in (429, 503, 504) and attempt < MAX_RETRIES - 1:
                delay = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Gemini API transient APIError (%s). Retrying in %.1fs (attempt %d/%d)...",
                    exc.code,
                    delay,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(delay)
            else:
                raise

        except (TimeoutError, ConnectionError) as exc:
            last_exception = exc
            if attempt < MAX_RETRIES - 1:
                delay = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Gemini API connection error (%s). Retrying in %.1fs (attempt %d/%d)...",
                    type(exc).__name__,
                    delay,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(delay)
            else:
                raise

    if last_exception:
        raise last_exception
    raise RuntimeError("Gemini API call failed after retries.")
