from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.clinical_measurement import ClinicalMeasurement
from app.models.medical_report import MedicalReport
from app.schemas.patient import PatientCreate, PatientResponse
from app.services.pdf_generator_service import generate_patient_history_pdf
from app.api.health_radar import get_health_change_radar
from app.api.deps import require_role

router = APIRouter(
    prefix="/patients",
    tags=["Patients"],
)


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@router.post(
    "/",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_patient(
    patient: PatientCreate,
    db: Session = Depends(get_db),
):
    existing = (
        db.query(Patient)
        .filter(Patient.patient_code == patient.patient_code)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Patient code '{patient.patient_code}' is already registered.",
        )

    new_patient = Patient(
        patient_code=patient.patient_code,
        name=patient.name,
        age=patient.age,
        gender=patient.gender,
        phone=patient.phone,
        location=patient.location,
    )

    try:
        db.add(new_patient)
        db.commit()
        db.refresh(new_patient)
        return new_patient

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Patient code '{patient.patient_code}' is already registered.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save the patient record.",
        )


@router.get(
    "",
    response_model=list[PatientResponse],
    include_in_schema=False,
)
@router.get(
    "/",
    response_model=list[PatientResponse],
)
def get_patients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    if skip < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="skip must be zero or greater.",
        )

    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be between 1 and 500.",
        )

    return (
        db.query(Patient)
        .order_by(Patient.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
)
def get_patient(
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

    return patient


@router.get(
    "/{patient_id}/pdf",
    summary="Download Patient History PDF",
    description="Generates a downloadable longitudinal health history PDF for the selected patient.",
)
def download_patient_pdf(
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

    # Chronological visits
    visits = (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_date.asc(), Visit.id.asc())
        .all()
    )

    # Measurements
    measurements = (
        db.query(ClinicalMeasurement)
        .filter(ClinicalMeasurement.patient_id == patient_id)
        .order_by(ClinicalMeasurement.created_at.asc(), ClinicalMeasurement.id.asc())
        .all()
    )

    # Attached Medical Reports
    visit_ids = [v.id for v in visits]
    reports = (
        db.query(MedicalReport)
        .filter(MedicalReport.visit_id.in_(visit_ids))
        .order_by(MedicalReport.created_at.asc())
        .all()
        if visit_ids
        else []
    )

    # Retrieve radar trajectory data for summary
    try:
        radar_resp = get_health_change_radar(patient_id=patient_id, db=db)
        radar_data = radar_resp.model_dump()
    except Exception:
        radar_data = None

    pdf_bytes = generate_patient_history_pdf(
        patient=patient,
        visits=visits,
        measurements=measurements,
        reports=reports,
        radar_data=radar_data,
    )

    safe_code = "".join(c for c in patient.patient_code if c.isalnum() or c in ("-", "_"))
    filename = f"CareTrack_Patient_{safe_code}_History.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@router.put(
    "/{patient_id}",
    response_model=PatientResponse,
)
def update_patient(
    patient_data: PatientCreate,
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

    conflict = (
        db.query(Patient)
        .filter(
            Patient.patient_code == patient_data.patient_code,
            Patient.id != patient_id,
        )
        .first()
    )
    if conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Patient code '{patient_data.patient_code}' is already"
                " registered to another patient."
            ),
        )

    patient.patient_code = patient_data.patient_code
    patient.name = patient_data.name
    patient.age = patient_data.age
    patient.gender = patient_data.gender
    patient.phone = patient_data.phone
    patient.location = patient_data.location

    try:
        db.commit()
        db.refresh(patient)
        return patient

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patient code is already registered to another patient.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update the patient record.",
        )


@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(["admin"]))],
    summary="Delete Patient",
    description="Deletes a patient record. Restricted to administrators only.",
)
def delete_patient(
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

    try:
        db.delete(patient)
        db.commit()

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Unable to delete the patient record. "
                "Related records may need to be handled first."
            ),
        )

    return None
