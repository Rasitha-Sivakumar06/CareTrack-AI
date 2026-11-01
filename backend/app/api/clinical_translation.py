import logging

from fastapi import APIRouter, HTTPException, status
from app.schemas.clinical_translation import (
    ClinicalTranslationRequest,
    ClinicalTranslationResponse,
)
from app.services.clinical_translation_service import (
    translate_clinical_text,
    SUPPORTED_LANGUAGES,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-translation",
    tags=["Clinical Translation"],
)

CLINICAL_DISCLAIMER = (
    "AI-assisted clinical translation for healthcare continuity. "
    "Must be reviewed and verified by a qualified clinician before patient communication. "
    "All vital signs, dosages, and medical instructions must be verified against source records."
)


@router.post(
    "/translate",
    response_model=ClinicalTranslationResponse,
    summary="Bilingual Clinical Summary Translation (English ⇄ Tamil)",
    description=(
        "Translates clinical summaries, patient-facing notes, and instructions between English and Tamil. "
        "Strictly preserves all numerical measurements, units, dates, drug names, and clinical uncertainty."
    ),
)
def translate_clinical_summary(
    payload: ClinicalTranslationRequest,
):
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Clinical text to translate cannot be empty or whitespace.",
        )

    if payload.source_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported source language '{payload.source_language}'. Supported codes: {list(SUPPORTED_LANGUAGES.keys())}.",
        )

    if payload.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported target language '{payload.target_language}'. Supported codes: {list(SUPPORTED_LANGUAGES.keys())}.",
        )

    if payload.source_language == payload.target_language:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Source language and target language must be different.",
        )

    try:
        translated_result = translate_clinical_text(
            text=text,
            source_lang=payload.source_language,
            target_lang=payload.target_language,
        )

        return ClinicalTranslationResponse(
            original_text=text,
            translated_text=translated_result,
            source_language=payload.source_language,
            target_language=payload.target_language,
            disclaimer=CLINICAL_DISCLAIMER,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    except RuntimeError as exc:
        if "GEMINI_API_KEY" in str(exc):
            logger.warning("Clinical translation requested but GEMINI_API_KEY is not configured.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Translation service is currently unconfigured. AI credentials missing on server.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI translation service could not generate a response. Please try again.",
        )

    except (TimeoutError, ConnectionError) as exc:
        logger.error("Clinical translation connection timeout: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Translation service connection timed out. Please try again.",
        )

    except Exception as exc:
        logger.error("Clinical translation unexpected error: %s: %s", type(exc).__name__, str(exc)[:200])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI translation service encountered an error. Please try again.",
        )
