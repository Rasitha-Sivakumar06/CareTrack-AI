from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.schemas.visit import VisitCreate, VisitResponse


router = APIRouter(
    prefix="/visits",
    tags=["Visits"],
)


@router.post(
    "",
    response_model=VisitResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@router.post(
    "/",
    response_model=VisitResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_visit(
    visit: VisitCreate,
    db: Session = Depends(get_db),
):
    patient = (
        db.query(Patient)
        .filter(Patient.id == visit.patient_id)
        .first()
    )

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found. Create the patient before adding a visit.",
        )

    new_visit = Visit(
        patient_id=visit.patient_id,
        visit_date=visit.visit_date,
        symptoms=visit.symptoms,
        clinical_notes=visit.clinical_notes,
        follow_up_notes=visit.follow_up_notes,
    )

    try:
        db.add(new_visit)
        db.commit()
        db.refresh(new_visit)
        return new_visit

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save the visit record.",
        )


@router.get(
    "/patient/{patient_id}",
    response_model=list[VisitResponse],
)
def get_patient_visits(
    patient_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id)
        .first()
    )

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found.",
        )

    return (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_date.desc(), Visit.id.desc())
        .all()
    )


@router.get(
    "/{visit_id}",
    response_model=VisitResponse,
)
def get_visit(
    visit_id: int = Path(gt=0),
    db: Session = Depends(get_db),
):
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if visit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found.",
        )
    return visit
