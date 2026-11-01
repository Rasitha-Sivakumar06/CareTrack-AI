from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    Form,
    Query,
    HTTPException,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.medical_report import MedicalReport
from app.models.clinical_measurement import ClinicalMeasurement
from app.services.medical_report_service import (
    save_medical_report,
    extract_text_from_pdf,
    extract_text_from_image,
    UPLOAD_DIR,
)
from app.services.clinical_extraction_service import (
    extract_clinical_information,
)
from app.schemas.medical_report import MedicalReportResponse


router = APIRouter(
    prefix="/medical-reports",
    tags=["Medical Reports"],
)

MAX_FILE_SIZE = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png",
    ".bmp", ".tif", ".tiff",
}

ALLOWED_CONTENT_TYPES = {
    ".pdf": {"application/pdf"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".bmp": {"image/bmp", "image/x-ms-bmp"},
    ".tif": {"image/tiff"},
    ".tiff": {"image/tiff"},
}


class ConfirmMeasurementsRequest(BaseModel):
    patient_id: int = Field(gt=0)
    visit_id: int = Field(gt=0)


def validate_file_signature(file_bytes: bytes, extension: str) -> bool:
    if extension == ".pdf":
        return file_bytes.startswith(b"%PDF-")
    if extension in {".jpg", ".jpeg"}:
        return file_bytes.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".bmp":
        return file_bytes.startswith(b"BM")
    if extension in {".tif", ".tiff"}:
        return file_bytes.startswith(
            (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")
        )
    return False


def public_measurement(measurement: ClinicalMeasurement) -> dict:
    return {
        "id": measurement.id,
        "patient_id": measurement.patient_id,
        "visit_id": measurement.visit_id,
        "blood_pressure": measurement.blood_pressure,
        "systolic_bp": measurement.systolic_bp,
        "diastolic_bp": measurement.diastolic_bp,
        "hemoglobin": measurement.hemoglobin,
        "blood_glucose": measurement.blood_glucose,
        "heart_rate": measurement.heart_rate,
        "temperature": measurement.temperature,
        "oxygen_saturation": measurement.oxygen_saturation,
        "weight": measurement.weight,
        "measured_at": (
            measurement.measured_at.isoformat()
            if measurement.measured_at else None
        ),
        "created_at": (
            measurement.created_at.isoformat()
            if measurement.created_at else None
        ),
    }


def report_result(report, measurements=None):
    return {
        "id": report.id,
        "visit_id": report.visit_id,
        "file_name": report.file_name,
        "file_type": report.file_type,
        "extracted_text": report.extracted_text,
        "extracted_measurements": measurements,
    }


@router.post(
    "/upload",
    response_model=MedicalReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_medical_report(
    patient_id: int = Form(..., gt=0),
    visit_id: int = Form(..., gt=0),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    saved_file_path = None

    try:
        patient = db.query(Patient).filter(
            Patient.id == patient_id
        ).first()

        if patient is None:
            raise HTTPException(404, "Patient not found.")

        visit = db.query(Visit).filter(
            Visit.id == visit_id,
            Visit.patient_id == patient_id,
        ).first()

        if visit is None:
            raise HTTPException(
                404,
                "Visit not found for the selected patient.",
            )

        original_name = Path(file.filename or "").name
        if not original_name:
            raise HTTPException(400, "Please select a file.")

        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(415, "Unsupported file type.")

        content_type = (file.content_type or "").lower()
        if content_type not in ALLOWED_CONTENT_TYPES[extension]:
            raise HTTPException(
                415,
                "The file extension and content type do not match.",
            )

        file_bytes = await file.read(MAX_FILE_SIZE + 1)
        if not file_bytes:
            raise HTTPException(400, "The uploaded file is empty.")
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(413, "Maximum file size is 10 MB.")
        if not validate_file_signature(file_bytes, extension):
            raise HTTPException(
                415,
                "The file contents do not match the declared file type.",
            )

        saved_file_path = save_medical_report(
            file_bytes=file_bytes,
            file_name=original_name,
        )

        try:
            extracted_text = (
                extract_text_from_pdf(saved_file_path)
                if extension == ".pdf"
                else extract_text_from_image(saved_file_path)
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

        # Safe idempotency check: prevent duplicate report uploads for the same visit
        existing_duplicate = (
            db.query(MedicalReport)
            .filter(
                MedicalReport.visit_id == visit.id,
                MedicalReport.file_name == original_name,
                MedicalReport.extracted_text == extracted_text,
            )
            .first()
        )
        if existing_duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"A report named '{original_name}' with identical content has already "
                    f"been uploaded for visit #{visit.id}."
                ),
            )

        report = MedicalReport(
            visit_id=visit.id,
            file_name=original_name,
            file_type=content_type,
            file_path=saved_file_path,
            extracted_text=extracted_text,
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        # Extraction is returned for review only.
        # No clinical measurement is saved at this stage.
        extracted = extract_clinical_information(extracted_text or "")
        has_values = any(value is not None for value in extracted.values())

        return report_result(
            report,
            extracted if has_values else None,
        )

    except HTTPException:
        db.rollback()
        if saved_file_path:
            try:
                Path(saved_file_path).unlink(missing_ok=True)
            except OSError:
                pass
        raise

    except Exception as exc:
        db.rollback()
        print(f"Medical report upload failed: {exc}")
        if saved_file_path:
            try:
                Path(saved_file_path).unlink(missing_ok=True)
            except OSError:
                pass
        raise HTTPException(
            500,
            "Could not save the medical report. Check backend logs.",
        ) from exc

    finally:
        await file.close()


@router.post("/{report_id}/confirm-measurements")
def confirm_report_measurements(
    report_id: int,
    payload: ConfirmMeasurementsRequest,
    db: Session = Depends(get_db),
):
    patient = db.query(Patient).filter(
        Patient.id == payload.patient_id
    ).first()
    if patient is None:
        raise HTTPException(404, "Patient not found.")

    visit = db.query(Visit).filter(
        Visit.id == payload.visit_id,
        Visit.patient_id == payload.patient_id,
    ).first()
    if visit is None:
        raise HTTPException(
            404,
            "Visit not found for the selected patient.",
        )

    report = db.query(MedicalReport).filter(
        MedicalReport.id == report_id,
        MedicalReport.visit_id == visit.id,
    ).first()
    if report is None:
        raise HTTPException(
            404,
            "Report not found for the selected visit.",
        )

    extracted = extract_clinical_information(report.extracted_text or "")
    non_null_extracted = {
        key: val for key, val in extracted.items() if val is not None
    }
    if not non_null_extracted:
        raise HTTPException(
            422,
            "No supported measurements were extracted from this report.",
        )

    # Check existing measurements for this visit to prevent repeated identical confirmations
    existing_records = (
        db.query(ClinicalMeasurement)
        .filter(
            ClinicalMeasurement.patient_id == patient.id,
            ClinicalMeasurement.visit_id == visit.id,
        )
        .all()
    )

    # If all extracted metrics have already been recorded with identical values on an existing row,
    # reject as a duplicate confirmation to prevent repeated identical rows.
    for existing in existing_records:
        if all(
            getattr(existing, key, None) == val
            for key, val in non_null_extracted.items()
        ):
            raise HTTPException(
                409,
                (
                    "These clinical measurements have already been confirmed for this visit. "
                    "Existing records have been preserved."
                ),
            )

    try:
        measurement = ClinicalMeasurement(
            patient_id=patient.id,
            visit_id=visit.id,
            **extracted,
        )
        db.add(measurement)
        db.commit()
        db.refresh(measurement)
        return {
            "message": "Measurements saved for clinical review.",
            "measurement": public_measurement(measurement),
            "disclaimer": (
                "Confirm the values against the original document. "
                "These values are not a diagnosis."
            ),
        }
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            500,
            "Unable to save the confirmed measurements.",
        ) from exc


@router.get(
    "/visit/{visit_id}",
    response_model=list[MedicalReportResponse],
)
def get_medical_reports_by_visit(
    visit_id: int,
    db: Session = Depends(get_db),
):
    visit = db.query(Visit).filter(
        Visit.id == visit_id
    ).first()
    if visit is None:
        raise HTTPException(404, "Visit not found.")

    reports = (
        db.query(MedicalReport)
        .filter(MedicalReport.visit_id == visit_id)
        .order_by(MedicalReport.id.desc())
        .all()
    )

    results = []
    seen_report_keys = set()
    for report in reports:
        key = (report.file_name or "", (report.extracted_text or "").strip())
        if key in seen_report_keys:
            continue
        seen_report_keys.add(key)
        extracted = extract_clinical_information(
            report.extracted_text or ""
        )
        has_values = any(value is not None for value in extracted.values())
        results.append(
            report_result(
                report,
                extracted if has_values else None,
            )
        )

    return results


@router.get(
    "/{report_id}/file",
    summary="Secure Medical Report File Download / View",
    description=(
        "Retrieves the uploaded report document after verifying patient authorization "
        "and protecting against directory traversal."
    ),
)
def get_medical_report_file(
    report_id: int,
    patient_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
):
    """
    Security note:
    Production HIPAA environments require full user-session authentication (e.g. clinician JWT/OAuth2).
    In this platform architecture, report retrieval strictly verifies:
    1. Report exists and is linked to a valid visit.
    2. The visit's patient_id strictly matches the requesting patient_id.
    3. The file path is verified against directory traversal and confined to UPLOAD_DIR.
    """
    report = db.query(MedicalReport).filter(MedicalReport.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medical report not found.",
        )

    visit = db.query(Visit).filter(Visit.id == report.visit_id).first()
    if not visit or visit.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: you are not authorized to view reports for this patient.",
        )

    if not report.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file path not found in database.",
        )

    target_path = Path(report.file_path).resolve()
    upload_root = UPLOAD_DIR.resolve()

    # Prevent directory traversal attacks
    if not str(target_path).startswith(str(upload_root)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: invalid file path.",
        )

    if not target_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file does not exist on disk.",
        )

    # Sanitize download filename (basename only)
    safe_filename = Path(report.file_name or target_path.name).name

    return FileResponse(
        path=str(target_path),
        media_type=report.file_type or "application/octet-stream",
        filename=safe_filename,
        content_disposition_type="inline",
    )
