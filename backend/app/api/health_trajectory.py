from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.health_trajectory import HealthTrajectoryResponse
from app.services.health_trajectory_service import compute_health_trajectory

router = APIRouter(
    prefix="/patients",
    tags=["HealthTrajectory AI"],
)


@router.get(
    "/{patient_id}/health-trajectory",
    response_model=HealthTrajectoryResponse,
    summary="Longitudinal Health Trajectory Clinical Change Detection",
    description=(
        "Compares multi-visit longitudinal clinical measurements ordered chronologically. "
        "Calculates exact mathematical deltas, distinguishes concerning shifts from improving or stable trends, "
        "identifies missing data and timestamp discrepancies, and provides transparent clinician decision support."
    ),
)
def get_patient_health_trajectory(
    patient_id: int = Path(gt=0, description="Positive integer patient identifier"),
    db: Session = Depends(get_db),
):
    result = compute_health_trajectory(patient_id=patient_id, db=db)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found.",
        )
    return result
