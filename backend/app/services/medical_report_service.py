from pathlib import Path
from uuid import uuid4

import pytesseract
from PIL import Image, ImageOps, ImageFilter
from pypdf import PdfReader


# Tesseract OCR executable on this Windows machine.
TESSERACT_PATH = Path(
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

if TESSERACT_PATH.exists():
    pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_PATH)


# Store uploads inside the backend directory, independent of
# the terminal's current working directory.
BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BACKEND_DIR / "uploads" / "medical_reports"


def save_medical_report(
    file_bytes: bytes,
    file_name: str,
    upload_directory: str | Path | None = None,
) -> str:
    """Save an uploaded report using a unique generated filename."""

    if not file_bytes:
        raise ValueError("The uploaded file is empty.")

    suffix = Path(file_name).suffix.lower()

    if not suffix:
        raise ValueError("The uploaded file must have a file extension.")

    unique_name = f"{uuid4().hex}{suffix}"

    destination_dir = (
        Path(upload_directory)
        if upload_directory is not None
        else UPLOAD_DIR
    )

    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / unique_name

    try:
        destination.write_bytes(file_bytes)
    except OSError as exc:
        raise ValueError(
            f"Could not save the uploaded file: {exc}"
        ) from exc

    return str(destination)


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract selectable text from a PDF.

    Scanned PDFs may contain no selectable text. OCR for PDF pages
    is not performed by this function.
    """

    try:
        reader = PdfReader(file_path, strict=False)

        if reader.is_encrypted:
            raise ValueError(
                "This PDF is encrypted. Upload an unlocked PDF."
            )

        pages = []

        for page in reader.pages:
            text = page.extract_text()

            if text and text.strip():
                pages.append(text.strip())

        return "\n\n".join(pages).strip()

    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            "Could not read this PDF. The file may be damaged or unsupported."
        ) from exc


def extract_text_from_image(file_path: str) -> str:
    """Extract English text from an image using Tesseract OCR."""

    try:
        with Image.open(file_path) as image:
            image.load()

            # Normalize the image for improved OCR readability.
            processed_image = ImageOps.exif_transpose(image)
            processed_image = ImageOps.grayscale(processed_image)
            processed_image = ImageOps.autocontrast(processed_image)
            processed_image = processed_image.filter(
                ImageFilter.SHARPEN
            )

            text = pytesseract.image_to_string(
                processed_image,
                lang="eng",
            )

        return text.strip()

    except pytesseract.TesseractNotFoundError as exc:
        raise ValueError(
            "Tesseract OCR was not found. Install Tesseract OCR "
            "or update TESSERACT_PATH in medical_report_service.py."
        ) from exc

    except Exception as exc:
        raise ValueError(
            "Could not extract text from this image. "
            "Check that the image is valid and readable."
        ) from exc
