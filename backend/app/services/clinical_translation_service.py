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

SUPPORTED_LANGUAGES = {
    "en": "English",
    "ta": "Tamil (தமிழ்)",
}


def build_translation_prompt(text: str, source_lang: str, target_lang: str) -> str:
    source_name = SUPPORTED_LANGUAGES.get(source_lang, source_lang)
    target_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

    return f"""You are CareTrack AI's specialized medical translation engine.
Your task is to provide a clinically faithful, professional bilingual translation between {source_name} and {target_name}.

TRANSLATION DIRECTION: {source_name} → {target_name}

CRITICAL CLINICAL SAFETY RULES:
1. NUMERICAL & UNIT PRESERVATION:
   - Preserve ALL numbers, vital signs, blood pressures (e.g. 142/90, 120/80), lab values, and scores exactly.
   - Preserve all units of measurement exactly (e.g., mmHg, mg/dL, bpm, %, °C, kg, g/dL).
   - Preserve all calendar dates (e.g. 2026-09-01, 2026-10-15) and time stamps exactly.

2. MEDICINE & DRUG NAMES:
   - Preserve all medication, drug, and clinical substance names (e.g., Metformin, Amlodipine, Paracetamol, Insulin, Atorvastatin) accurately. Retain English or international nonproprietary names (INN) clearly (e.g., transliterate with English name in parentheses if helpful for clinician verification).

3. PRESERVE CLINICAL UNCERTAINTY:
   - Faithfully preserve hedging, doubts, and uncertainty (e.g., "suspected", "possible", "unconfirmed", "rule out", "needs verification", "borderline").
   - Do NOT convert tentative findings into definitive diagnoses.

4. ABSOLUTELY NO HALLUCINATION OR EXTENSION:
   - Translate ONLY the provided clinical text.
   - Do NOT invent or infer missing patient history, diagnoses, treatments, or recommendations.
   - Do NOT add clinical commentary, disclaimers, or advice into the translation itself.

5. OUTPUT REQUIREMENT:
   - Return ONLY the translated text without conversational preamble, introductory remarks, or markdown code fences.

CLINICAL TEXT TO TRANSLATE:
{text}
"""


def translate_clinical_text(
    text: str,
    source_lang: str = "en",
    target_lang: str = "ta",
) -> str:
    """
    Translates clinical text between English and Tamil with strict preservation
    of clinical measurements, units, dates, drug names, and uncertainty.
    """
    cleaned_text = (text or "").strip()
    if not cleaned_text:
        raise ValueError("Translation text cannot be empty.")

    if source_lang not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported source language: '{source_lang}'. Supported: {list(SUPPORTED_LANGUAGES.keys())}")

    if target_lang not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported target language: '{target_lang}'. Supported: {list(SUPPORTED_LANGUAGES.keys())}")

    if source_lang == target_lang:
        raise ValueError("Source language and target language must be different.")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)
    prompt = build_translation_prompt(cleaned_text, source_lang, target_lang)

    last_exception = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            answer = response.text

            if not answer:
                raise RuntimeError("Translation model returned an empty response.")

            return answer.strip()

        except errors.ServerError as exc:
            last_exception = exc
            if attempt < MAX_RETRIES - 1:
                delay = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Gemini API transient ServerError (%s). Retrying translation in %.1fs (attempt %d/%d)...",
                    getattr(exc, "code", "unknown"),
                    delay,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(delay)
            else:
                logger.error("Gemini API retries exhausted for translation.")
                raise

        except errors.APIError as exc:
            last_exception = exc
            if getattr(exc, "code", None) in (429, 503, 504) and attempt < MAX_RETRIES - 1:
                delay = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Gemini API transient APIError (%s). Retrying translation in %.1fs (attempt %d/%d)...",
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
                    "Gemini API connection error (%s). Retrying translation in %.1fs (attempt %d/%d)...",
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
    raise RuntimeError("Clinical translation failed after retries.")
