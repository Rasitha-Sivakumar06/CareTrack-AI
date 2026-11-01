import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.security import create_access_token

client = TestClient(app)

print("=" * 70)
print("TESTING PATIENT HISTORY PDF GENERATION ENDPOINT")
print("=" * 70)

# Security verification: Anonymous access MUST be rejected with 401
print("\n0. Security Check: Anonymous Request Rejection...")
anon_resp = client.get("/patients/5/pdf")
assert anon_resp.status_code == 401, f"Expected 401, got {anon_resp.status_code}"
assert anon_resp.json()["detail"] == "Authentication token is missing."
print("PASS: Anonymous PDF download blocked with HTTP 401 Unauthorized.")

# Generate valid doctor session token for live tests
doctor_token = create_access_token(subject=1, role="doctor")
auth_headers = {"Authorization": f"Bearer {doctor_token}"}

# 1. Test PDF generation for Patient #5 (Arun Kumar - 3 visits)
print("\n1. Testing PDF Generation for Patient #5 (Arun Kumar)...")
resp = client.get("/patients/5/pdf", headers=auth_headers)
print("Status Code:", resp.status_code)
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

content_type = resp.headers.get("content-type")
print("Content-Type:", content_type)
assert "application/pdf" in content_type, f"Expected application/pdf, got {content_type}"

content_disp = resp.headers.get("content-disposition")
print("Content-Disposition:", content_disp)
assert "attachment" in content_disp
assert "CareTrack_Patient_DEMO-ARUN-001_History.pdf" in content_disp or "DEMO-ARUN-001" in content_disp

pdf_bytes = resp.content
print("PDF Size:", len(pdf_bytes), "bytes")
assert len(pdf_bytes) > 2000, "PDF payload unexpectedly small"
assert pdf_bytes.startswith(b"%PDF"), f"Invalid PDF signature: {pdf_bytes[:10]}"
print("PASS: Valid %PDF-1.4 binary received with correct attachment headers.")

# 2. Test Non-Existent Patient (Expect HTTP 404)
print("\n2. Testing PDF Generation for Non-Existent Patient (#99999)...")
resp_404 = client.get("/patients/99999/pdf", headers=auth_headers)
print("Status Code:", resp_404.status_code)
assert resp_404.status_code == 404, f"Expected 404, got {resp_404.status_code}"
assert resp_404.json()["detail"] == "Patient not found."
print("PASS: Correctly returns HTTP 404 Not Found.")

# 3. Test Patient with Single or Empty History (Patient #11)
print("\n3. Testing PDF Generation for Patient with No Visits (Patient #11)...")
resp_empty = client.get("/patients/11/pdf", headers=auth_headers)
print("Status Code:", resp_empty.status_code)
assert resp_empty.status_code == 200, f"Expected 200, got {resp_empty.status_code}"
assert resp_empty.content.startswith(b"%PDF")
print("PDF Size for Patient without visits:", len(resp_empty.content), "bytes")
print("PASS: Handled empty visit history gracefully without crashes.")

# 4. Verify PDF structure with pypdf
print("\n4. Verifying PDF Structure with pypdf...")
from pypdf import PdfReader
import io

reader = PdfReader(io.BytesIO(pdf_bytes))
print("Total Pages:", len(reader.pages))
assert len(reader.pages) >= 1, "PDF should have at least 1 page"

extracted_text = ""
for i, page in enumerate(reader.pages):
    page_text = page.extract_text()
    extracted_text += page_text
    print(f"  Page {i+1} extracted characters: {len(page_text)}")

# Check key text elements in PDF
assert "Arun Kumar" in extracted_text, "Patient name missing from PDF"
assert "DEMO-ARUN-001" in extracted_text, "Patient code missing from PDF"
assert "CONFIDENTIAL MEDICAL RECORD" in extracted_text, "Confidentiality notice missing from PDF"
assert "NOT A DIAGNOSIS" in extracted_text, "Clinical disclaimer missing from PDF"
assert "Blood Glucose" in extracted_text, "Vitals table missing from PDF"

print("PASS: All clinical fields, demographics, disclaimer, and vitals verified in PDF text.")

print("\n" + "=" * 70)
print("ALL PATIENT HISTORY PDF TESTS PASSED (100% SUCCESS)!")
print("=" * 70)
