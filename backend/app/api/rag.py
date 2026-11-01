import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.rag import RAGQuestionRequest, RAGQueryResponse
from app.services.rag_service import (
    AIServiceError,
    PatientNotFoundError,
    execute_rag_query,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/rag",
    tags=["Patient History RAG Assistant"],
)


@router.post(
    "/ask",
    response_model=RAGQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask Patient History RAG Assistant",
    description=(
        "Retrieves longitudinal records for the specified patient, grounds the context "
        "with explicit source citations ([S1], [S2]...), and generates an evidence-based clinical answer."
    ),
)
def ask_patient_history_rag(
    request: RAGQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Execute structured RAG query:
    1. Authenticates clinician via JWT access token.
    2. Enforces patient boundary isolation.
    3. Retrieves chronological encounters, vitals, and reports.
    4. Generates grounded answer citing source identifiers.
    5. Returns structured sources, data summary, and safety disclaimers.
    """
    try:
        response = execute_rag_query(db=db, request=request)
        return response

    except PatientNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    except AIServiceError as exc:
        # Safe server-side exception logging: record error type and patient ID only.
        # Never log raw medical records, clinical question text, or API secrets.
        logger.error(
            "RAG generation failed for patient_id=%s. Error: %s",
            request.patient_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "The AI service could not generate a response. "
                "Please try again or review original records."
            ),
        ) from None

    except Exception as exc:
        logger.error(
            "Unexpected error in RAG query for patient_id=%s: %s",
            request.patient_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the clinical records query.",
        ) from None
