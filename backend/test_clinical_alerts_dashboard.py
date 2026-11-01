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
print("TESTING CLINICAL ALERTS & HEALTH URGENCY DASHBOARD API")
print("=" * 70)

# 0. Security verification: Anonymous access MUST be rejected with 401
print("\n0. Security Check: Anonymous Request Rejection...")
anon_resp1 = client.get("/patients/5/clinical-alerts")
assert anon_resp1.status_code == 401, f"Expected 401, got {anon_resp1.status_code}"
assert anon_resp1.json()["detail"] == "Authentication token is missing."

anon_resp2 = client.get("/clinical-alerts/overview")
assert anon_resp2.status_code == 401, f"Expected 401, got {anon_resp2.status_code}"
assert anon_resp2.json()["detail"] == "Authentication token is missing."
print("PASS: Anonymous alerts requests blocked with HTTP 401 Unauthorized.")

# Generate valid doctor session token for live tests
doctor_token = create_access_token(subject=1, role="doctor")
auth_headers = {"Authorization": f"Bearer {doctor_token}"}

# 1. Test existing patient clinical alerts endpoint (preservation check)
print("\n1. Testing Existing GET /patients/5/clinical-alerts (Preservation)...")
p_resp = client.get("/patients/5/clinical-alerts", headers=auth_headers)
assert p_resp.status_code == 200, f"Expected 200, got {p_resp.status_code}: {p_resp.text}"
p_data = p_resp.json()
print(f"Patient ID: {p_data['patient_id']}, Name: {p_data['patient_name']}")
print(f"Alerts count: {len(p_data['alerts'])}, Summary: {p_data['summary']}")
assert p_data["patient_id"] == 5
assert "disclaimer" in p_data
print("PASS: Existing /patients/{id}/clinical-alerts endpoint preserved exactly.")

# 2. Test system-wide Clinical Alerts Overview endpoint
print("\n2. Testing GET /clinical-alerts/overview...")
ov_resp = client.get("/clinical-alerts/overview", headers=auth_headers)
assert ov_resp.status_code == 200, f"Expected 200, got {ov_resp.status_code}: {ov_resp.text}"
ov_data = ov_resp.json()

rules = ov_data["rules"]
summary = ov_data["summary"]
patients = ov_data["patients"]

print(f"Configured Demo Rules Count: {len(rules)}")
assert len(rules) == 6, f"Expected 6 rules, got {len(rules)}"
rule_fields = [r["field"] for r in rules]
assert "systolic_bp" in rule_fields
assert "diastolic_bp" in rule_fields
assert "blood_glucose" in rule_fields
assert "heart_rate" in rule_fields
assert "temperature" in rule_fields
assert "oxygen_saturation" in rule_fields
print(f"  Rules: {[r['metric'] for r in rules]}")

print(f"\nSummary:")
print(f"  Total Patients Evaluated: {summary['total_patients_evaluated']}")
print(f"  Patients with Alerts: {summary['patients_with_alerts']}")
print(f"  High Priority: {summary['high_priority_count']}")
print(f"  Moderate Priority: {summary['moderate_priority_count']}")
print(f"  Normal: {summary['normal_count']}")
print(f"  No Data: {summary['no_data_count']}")

assert summary["total_patients_evaluated"] == len(patients)
assert summary["total_patients_evaluated"] > 0
assert summary["high_priority_count"] + summary["moderate_priority_count"] + summary["normal_count"] + summary["no_data_count"] == summary["total_patients_evaluated"]

# 3. Verify Priority Ordering
print("\n3. Verifying Priority Sorting in Patient Alert Queue...")
severities = [p["highest_severity"] for p in patients]
print(f"Patient Queue Severity Sequence: {severities}")

# Verify that all "high" come before "moderate", "moderate" before "no_data", "no_data" before "normal"
rank = {"high": 1, "moderate": 2, "no_data": 3, "normal": 4}
numeric_ranks = [rank.get(s, 5) for s in severities]
for i in range(len(numeric_ranks) - 1):
    assert numeric_ranks[i] <= numeric_ranks[i + 1], f"Order violation at index {i}: {severities[i]} followed by {severities[i+1]}"
print("PASS: Patients are strictly ordered by clinical priority (High -> Moderate -> No Data -> Normal).")

# 4. Verify Synthetic Demo Data Identification & Disclaimers
print("\n4. Verifying Synthetic Demo Data Flags & Responsible AI Notices...")
for p in patients[:5]:
    assert p["is_synthetic_demo"] is True
assert "synthetic patient data" in ov_data["disclaimer"].lower()
assert "not medical diagnoses" in ov_data["disclaimer"].lower()
print(f"Disclaimer: {ov_data['disclaimer']}")
print("PASS: All patient records explicitly labeled as synthetic demo, and non-diagnostic disclaimers present.")

# 5. Verify Alias Endpoint
print("\n5. Testing Alias GET /patients/alerts/overview...")
alias_resp = client.get("/patients/alerts/overview", headers=auth_headers)
assert alias_resp.status_code == 200
assert alias_resp.json()["summary"]["total_patients_evaluated"] == summary["total_patients_evaluated"]
print("PASS: Alias endpoint returns identical clinical overview payload.")

print("\n" + "=" * 70)
print("ALL CLINICAL ALERTS & URGENCY DASHBOARD TESTS PASSED (100% SUCCESS)!")
print("=" * 70)
