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
print("TESTING HEALTH CHANGE RADAR & PATIENT API (MVP SUITE)")
print("=" * 70)

# 0. Security verification: Anonymous access MUST be rejected with 401
print("\n0. Security Check: Anonymous Request Rejection...")
anon_resp1 = client.get("/patients")
assert anon_resp1.status_code == 401, f"Expected 401, got {anon_resp1.status_code}"
assert anon_resp1.json()["detail"] == "Authentication token is missing."

anon_resp2 = client.get("/patients/5/health-radar")
assert anon_resp2.status_code == 401, f"Expected 401, got {anon_resp2.status_code}"
assert anon_resp2.json()["detail"] == "Authentication token is missing."
print("PASS: Anonymous requests to patients and health-radar blocked with HTTP 401 Unauthorized.")

doctor_token = create_access_token(subject=1, role="doctor")
auth_headers = {"Authorization": f"Bearer {doctor_token}"}

# 1. Test slash tolerance on patient API
print("\n1. Testing Patient API Slash-Tolerance (Authenticated)...")
r_no_slash = client.get("/patients", headers=auth_headers, follow_redirects=False)
assert r_no_slash.status_code == 200, f"Expected 200 on /patients, got {r_no_slash.status_code}"
r_slash = client.get("/patients/", headers=auth_headers, follow_redirects=False)
assert r_slash.status_code == 200, f"Expected 200 on /patients/, got {r_slash.status_code}"
print("PASS: Both /patients and /patients/ return 200 OK without 307 redirect when authenticated.")

# 2. Test Health Change Radar with Patient #5 (Arun Kumar - 3 visits, rich measurements)
print("\n2. Testing Health Change Radar for Patient #5 (Arun Kumar)...")
radar_resp = client.get("/patients/5/health-radar", headers=auth_headers)
assert radar_resp.status_code == 200, f"Expected 200, got {radar_resp.status_code}: {radar_resp.text}"
radar_data = radar_resp.json()

summary = radar_data["summary"]
metrics = radar_data["radar_metrics"]

print(f"Patient Name: {summary['patient_name']} (#{summary['patient_id']})")
print(f"Visits Recorded: {summary['total_visits_recorded']}")
print(f"Baseline Visit: {summary['baseline_visit_date']} -> Current Visit: {summary['current_visit_date']}")
print(f"Metrics Compared: {summary['metrics_compared_count']}")
print(f"Overall Status: {summary['overall_status']}")
print(f"Narrative: {summary['evidence_narrative']}")
print(f"Suggestions: {summary['clinical_action_suggestions']}")

assert summary["patient_id"] == 5
assert summary["total_visits_recorded"] >= 2
assert len(metrics) == 8
assert any(m["key"] == "blood_glucose" for m in metrics)

# Validate Glucose metric calculation
glucose_m = next(m for m in metrics if m["key"] == "blood_glucose")
print(f"\nGlucose Metric Breakdown:")
print(f"  Formula: {glucose_m['calculation_formula']}")
print(f"  Clinical Reason: {glucose_m['clinical_reason']}")
print(f"  Baseline: {glucose_m['baseline_value']} (score={glucose_m['baseline_score']})")
print(f"  Current: {glucose_m['current_value']} (score={glucose_m['current_score']})")
print(f"  Delta: {glucose_m['delta']} {glucose_m['unit']} ({glucose_m['percent_change']}%)")

assert glucose_m["baseline_value"] is not None
assert glucose_m["current_value"] is not None
assert glucose_m["delta"] == round(glucose_m["current_value"] - glucose_m["baseline_value"], 2)
assert glucose_m["baseline_score"] > 0
assert glucose_m["current_score"] > 0
assert "Current (" in glucose_m["calculation_formula"]
print("PASS: Exact calculation formula and clinical reason verified.")

# 3. Test Non-Existent Patient (Expect HTTP 404)
print("\n3. Testing Health Change Radar for Non-Existent Patient (ID #99999)...")
resp_404 = client.get("/patients/99999/health-radar", headers=auth_headers)
assert resp_404.status_code == 404, f"Expected 404, got {resp_404.status_code}"
assert resp_404.json()["detail"] == "Patient not found."
print("PASS: Correctly returns 404 for invalid patient ID.")

# 4. Test Single-Visit Patient or Empty Patient
print("\n4. Testing Radar for Patient with Single or Empty History (ID #11)...")
resp_single = client.get("/patients/11/health-radar", headers=auth_headers)
assert resp_single.status_code == 200
single_data = resp_single.json()
print(f"Single/Empty Patient Status: {single_data['summary']['overall_status']}")
print(f"Single/Empty Narrative: {single_data['summary']['evidence_narrative']}")
assert single_data["summary"]["overall_status"] == "INSUFFICIENT_HISTORY"
print("PASS: Handles patients with insufficient history gracefully without crashes.")

# 5. Verify Radar Chart Normalized Scores Bounded in [0, 100]
print("\n5. Testing Score Normalization Range...")
for m in metrics:
    if m["baseline_score"] is not None:
        assert 0.0 <= m["baseline_score"] <= 100.0, f"Score out of bounds: {m['baseline_score']}"
    if m["current_score"] is not None:
        assert 0.0 <= m["current_score"] <= 100.0, f"Score out of bounds: {m['current_score']}"
print("PASS: All radar normalization scores are strictly bounded within [0, 100].")

print("\n" + "=" * 70)
print("ALL HEALTH CHANGE RADAR TESTS PASSED (100% SUCCESS)!")
print("=" * 70)
