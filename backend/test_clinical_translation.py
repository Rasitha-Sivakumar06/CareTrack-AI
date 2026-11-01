"""
CareTrack AI — Phase 4 Clinical Translation Automated Test Suite

Tests:
1. Anonymous request rejection with HTTP 401 on /clinical-translation/translate.
2. Authenticated English -> Tamil clinical translation (deterministic mock).
3. Authenticated Tamil -> English clinical translation (deterministic mock).
4. Numerical & clinical measurement preservation (BP 142/90, glucose 140 mg/dL, 2026-09-01).
5. Validation errors:
   - Empty string -> 422
   - Whitespace-only string -> 422
   - Unsupported language code (e.g. 'fr') -> 422
   - Identical source and target language -> 422
6. Missing AI credentials handling -> 503 Service Unavailable.
7. External AI failure / timeout handling -> 502 Bad Gateway / 504 Gateway Timeout.
8. Non-diagnostic and clinical review disclaimers present in response payload.

Zero database records are accessed or altered.
"""

import sys
from pathlib import Path
from unittest.mock import patch

# Configure stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.security import create_access_token

client = TestClient(app)

print("=" * 70)
print("CARETRACK AI — CLINICAL TRANSLATION (ENGLISH ⇄ TAMIL) TEST SUITE")
print("=" * 70)

# Generate valid doctor session token
doctor_token = create_access_token(subject=1, role="doctor")
auth_headers = {"Authorization": f"Bearer {doctor_token}"}

# -------------------------------------------------------------------
# 1. Anonymous Access Rejection (HTTP 401)
# -------------------------------------------------------------------
print("\n1. Testing Anonymous Access Rejection...")
anon_resp = client.post(
    "/clinical-translation/translate",
    json={"text": "Patient has elevated blood pressure.", "source_language": "en", "target_language": "ta"},
)
assert anon_resp.status_code == 401, f"Expected 401, got {anon_resp.status_code}"
assert anon_resp.json()["detail"] == "Authentication token is missing."
print("  [PASS] Anonymous translation request blocked with HTTP 401 Unauthorized.")

# -------------------------------------------------------------------
# 2. English -> Tamil Translation with Mocked Gemini Service
# -------------------------------------------------------------------
print("\n2. Testing Authenticated English -> Tamil Translation...")
english_text = (
    "Patient Ananya Roy presented on 2026-09-01 with blood pressure of 142/90 mmHg "
    "and blood glucose of 140 mg/dL. Metformin 500mg was prescribed. "
    "Suspected mild dizziness noted upon standing. Follow-up scheduled in 6 weeks."
)

mock_tamil_translation = (
    "நோயாளி அனன்யா ராய் 2026-09-01 அன்று இரத்த அழுத்தம் 142/90 mmHg "
    "மற்றும் இரத்த சர்க்கரை 140 mg/dL உடன் வந்தார். மெட்ஃபோர்மின் (Metformin) 500mg பரிந்துரைக்கப்பட்டது. "
    "எழுந்து நிற்கும் போது லேசான தலைச்சுற்றல் இருக்கலாம் என்று சந்தேகிக்கப்படுகிறது. 6 வாரங்களில் பின்தொடர் சந்திப்பு திட்டமிடப்பட்டுள்ளது."
)

with patch("app.api.clinical_translation.translate_clinical_text", return_value=mock_tamil_translation) as mock_service:
    resp = client.post(
        "/clinical-translation/translate",
        json={
            "text": english_text,
            "source_language": "en",
            "target_language": "ta",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()

    assert data["source_language"] == "en"
    assert data["target_language"] == "ta"
    assert data["original_text"] == english_text
    assert "142/90" in data["translated_text"]
    assert "140" in data["translated_text"]
    assert "Metformin" in data["translated_text"] or "மெட்ஃபோர்மின்" in data["translated_text"]
    assert "clinician" in data["disclaimer"].lower()

    # Verify mock was called with exact arguments
    mock_service.assert_called_once_with(
        text=english_text,
        source_lang="en",
        target_lang="ta",
    )
    print("  [PASS] English -> Tamil translation returned structured response with disclaimer.")

# -------------------------------------------------------------------
# 3. Tamil -> English Translation with Mocked Gemini Service
# -------------------------------------------------------------------
print("\n3. Testing Authenticated Tamil -> English Translation...")
tamil_text = (
    "நோயாளிக்கு தலைவலி குறைந்துள்ளது. இரத்த அழுத்தம் 120/80 mmHg, "
    "இரத்த சர்க்கரை 105 mg/dL. அடுத்த பரிசோதனை 2026-10-15."
)

mock_english_translation = (
    "Patient reports headache has resolved. Blood pressure is 120/80 mmHg, "
    "blood glucose is 105 mg/dL. Next evaluation scheduled on 2026-10-15."
)

with patch("app.api.clinical_translation.translate_clinical_text", return_value=mock_english_translation) as mock_service:
    resp = client.post(
        "/clinical-translation/translate",
        json={
            "text": tamil_text,
            "source_language": "ta",
            "target_language": "en",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_language"] == "ta"
    assert data["target_language"] == "en"
    assert "120/80" in data["translated_text"]
    assert "105" in data["translated_text"]
    assert "2026-10-15" in data["translated_text"]
    print("  [PASS] Tamil -> English translation verified with exact numerical preservation.")

# -------------------------------------------------------------------
# 4. Input Validation & Edge Cases
# -------------------------------------------------------------------
print("\n4. Testing Input Validations & Rejections...")

# 4a. Empty text
resp_empty = client.post(
    "/clinical-translation/translate",
    json={"text": "", "source_language": "en", "target_language": "ta"},
    headers=auth_headers,
)
assert resp_empty.status_code == 422
print("  [PASS] Empty text rejected with HTTP 422.")

# 4b. Whitespace-only text
resp_spaces = client.post(
    "/clinical-translation/translate",
    json={"text": "    \n\t  ", "source_language": "en", "target_language": "ta"},
    headers=auth_headers,
)
assert resp_spaces.status_code == 422
assert "empty or whitespace" in resp_spaces.json()["detail"].lower()
print("  [PASS] Whitespace text rejected with HTTP 422.")

# 4c. Unsupported source language
resp_bad_src = client.post(
    "/clinical-translation/translate",
    json={"text": "Valid medical note", "source_language": "fr", "target_language": "ta"},
    headers=auth_headers,
)
assert resp_bad_src.status_code == 422
assert "unsupported source language" in resp_bad_src.json()["detail"].lower()
print("  [PASS] Unsupported source language rejected with HTTP 422.")

# 4d. Same source and target language
resp_same = client.post(
    "/clinical-translation/translate",
    json={"text": "Valid medical note", "source_language": "en", "target_language": "en"},
    headers=auth_headers,
)
assert resp_same.status_code == 422
assert "must be different" in resp_same.json()["detail"].lower()
print("  [PASS] Identical source and target language rejected with HTTP 422.")

# -------------------------------------------------------------------
# 5. Missing AI Credentials Graceful Handling (503)
# -------------------------------------------------------------------
print("\n5. Testing Missing AI Credentials Handling...")
with patch(
    "app.api.clinical_translation.translate_clinical_text",
    side_effect=RuntimeError("GEMINI_API_KEY is not configured."),
):
    resp_no_key = client.post(
        "/clinical-translation/translate",
        json={"text": "Blood pressure 120/80", "source_language": "en", "target_language": "ta"},
        headers=auth_headers,
    )
    assert resp_no_key.status_code == 503
    assert "missing" in resp_no_key.json()["detail"].lower() or "unconfigured" in resp_no_key.json()["detail"].lower()
    print("  [PASS] Missing API key handled gracefully with HTTP 503 Service Unavailable.")

# -------------------------------------------------------------------
# 6. External Timeout & Error Handling (504 & 502)
# -------------------------------------------------------------------
print("\n6. Testing External AI Timeout & Server Failure Handling...")

with patch(
    "app.api.clinical_translation.translate_clinical_text",
    side_effect=TimeoutError("Request timed out"),
):
    resp_timeout = client.post(
        "/clinical-translation/translate",
        json={"text": "Blood pressure 120/80", "source_language": "en", "target_language": "ta"},
        headers=auth_headers,
    )
    assert resp_timeout.status_code == 504
    print("  [PASS] AI timeout handled gracefully with HTTP 504 Gateway Timeout.")

with patch(
    "app.api.clinical_translation.translate_clinical_text",
    side_effect=Exception("Unknown upstream failure"),
):
    resp_err = client.post(
        "/clinical-translation/translate",
        json={"text": "Blood pressure 120/80", "source_language": "en", "target_language": "ta"},
        headers=auth_headers,
    )
    assert resp_err.status_code == 502
    print("  [PASS] Upstream AI failure handled gracefully with HTTP 502 Bad Gateway.")

print("\n" + "=" * 70)
print("ALL CLINICAL TRANSLATION TESTS PASSED (100% SUCCESS)!")
print("=" * 70)
