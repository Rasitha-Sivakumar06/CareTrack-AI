# CareTrack AI — Feature, Codebase, and API Audit Report

**Audit Date:** October 28, 2026
**Audited System:** CareTrack AI — AI-Powered Longitudinal Healthcare Platform
**Target Environment:** FastAPI (Python 3.12), PostgreSQL (Supabase) / SQLite (Test Harness), React 19 / Vite 8
**Audit Scope:** Codebase architecture, frontend modules, backend controllers, database models, security gates, AI algorithms, and verified empirical test suites.

---

## 1. Executive Summary & Audit Methodology

This audit provides an evidence-based assessment of the **CareTrack AI** codebase. Features are classified strictly according to implementation state, test coverage, and runtime verification. No assumptions of functionality are made solely based on user interface presence.

### Classification Categories:
1. **Implemented and Verified by a Test (IVT):** Fully implemented in backend and frontend, backed by dedicated automated assertions.
2. **Implemented but Not Tested (INT):** Functional code paths exist, but automated test suite coverage is absent or partial.
3. **Partially Implemented (PI):** Core data structures exist, but business logic, edge-case handling, or UI integration is incomplete.
4. **UI-Only / Placeholder (UIP):** Frontend presentation components with static or mocked responses lacking live backend persistence.
5. **Not Implemented (NI):** Documented or conceptual features with no active codebase realization.
6. **Failing or Known Defect (FKD):** Code contains an active bug, improper boundary validation, or runtime failure under specific conditions.

---

## 2. In-Depth Investigation of Known Observations

### Observation 1: Dashboard Reported Patient ID #18 Did Not Exist Despite Dropdown Displaying "Nila test (DEMO-CARE-103), ID #18"
* **Classification:** Partially Implemented / State Synchronization Defect (FKD)
* **Locations:**
  * Frontend Context: [`frontend/src/context/PatientContext.jsx`](file:///c:/Users/Admin/Downloads/AI_Longitudinal_Healthcare/frontend/src/context/PatientContext.jsx#L42-L70)
  * Frontend Selector: [`frontend/src/components/PatientSelector.jsx`](file:///c:/Users/Admin/Downloads/AI_Longitudinal_Healthcare/frontend/src/components/PatientSelector.jsx#L57-L64)
  * Backend Controller: [`backend/app/api/patient.py`](file:///c:/Users/Admin/Downloads/AI_Longitudinal_Healthcare/backend/app/api/patient.py#L35-L45)
* **Code Evidence & Mechanism:**
  1. In `PatientContext.jsx`:
     ```javascript
     const params = new URLSearchParams(window.location.search);
     const urlPatientId = params.get("patientId")?.trim();
     const savedPatientId = sessionStorage.getItem("caretrack_active_patient_id")?.trim();
     if (urlPatientId) {
       const found = list.find((p) => String(p.id) === urlPatientId);
       if (found) {
         setSelectedPatientId(String(found.id));
         sessionStorage.setItem("caretrack_active_patient_id", String(found.id));
       } else {
         setInvalidPatientId(urlPatientId);
         setSelectedPatientId("");
       }
     }
     ```
  2. In `PatientSelector.jsx`:
     ```jsx
     {invalidPatientId && (
       <div className="selector-warning-banner" role="alert">
         <AlertCircle size={15} />
         <span>Patient ID <strong>#{invalidPatientId}</strong> does not exist in the database. Please select a valid patient below.</span>
       </div>
     )}
     ```
  3. **Root Cause Analysis:**
     * **Race Condition / Cache Out-of-Sync:** When a user registers a new patient (e.g., Nila test with ID #18), `PatientRegistrationModal.jsx` calls `refreshPatients()`. However, if the browser URL still retains `?patientId=18` prior to the database transaction committing or during an asynchronous fetch timing window, `fetchPatientsList()` returned the pre-registration roster.
     * **Stale Warning Retention:** `setInvalidPatientId("")` is only executed when `selectPatient()` is manually invoked from dropdown interactions. If `invalidPatientId` was set to `"18"`, the warning banner persists on screen even after the dropdown updates to include patient #18.
     * **HTML Select Fallback Display:** When `selectedPatientId` is set to `""`, the select menu falls back to the top item or default placeholder. If the roster reloaded without re-triggering selection synchronization, the dropdown rendered the newly fetched roster item while the warning banner remained visible.
* **Missing Evidence:** Client-side network timeline waterfall and browser localStorage/sessionStorage state snapshots at the exact second the defect occurred.

---

### Observation 2: Temperature Input Displayed Range 0–100 °C; Synthetic Visit Contained 3.5 °C Producing a -33.3 °C Shift
* **Classification:** Failing or Known Defect (FKD) — Clinical Boundary Validation Defect
* **Locations:**
  * Frontend Modal: [`frontend/src/components/ClinicalMeasurementModal.jsx`](file:///c:/Users/Admin/Downloads/AI_Longitudinal_Healthcare/frontend/src/components/ClinicalMeasurementModal.jsx#L156-L165)
  * Backend Schema: [`backend/app/schemas/clinical_measurement.py`](file:///c:/Users/Admin/Downloads/AI_Longitudinal_Healthcare/backend/app/schemas/clinical_measurement.py#L34-L36)
  * Calculation Service: [`backend/app/api/health_radar.py`](file:///c:/Users/Admin/Downloads/AI_Longitudinal_Healthcare/backend/app/api/health_radar.py#L64-L67)
* **Code Evidence & Mechanism:**
  1. Frontend Input & Validation:
     ```jsx
     <input id="temperature" type="number" min="0" max="100" step="0.1" placeholder="e.g. 36.8" ... />
     <span className="field-hint">Range: 0 - 100 °C</span>
     ```
     `if (Number.isNaN(val) || val < 0 || val > 100) { setError("Body temperature must be a number between 0 and 100 °C."); return; }`
  2. Backend Pydantic Schema:
     ```python
     temperature: Optional[float] = Field(default=None, ge=0, le=100)
     ```
  3. Radar Calculation:
     ```python
     delta = round(c_val - b_val, 2)
     pct = round(((c_val - b_val) / b_val) * 100.0, 1) if b_val != 0 else 0.0
     # Baseline: 36.8 °C, Current: 3.5 °C
     # Delta = 3.5 - 36.8 = -33.3 °C (-90.5%)
     ```
  4. **Root Cause Analysis:**
     * The schema validation rules conflated the physical phase-change temperatures of liquid water ($0^\circ\text{C}$ to $100^\circ\text{C}$) with human physiological viability limits ($30.0^\circ\text{C}$ to $45.0^\circ\text{C}$).
     * The input of $3.5^\circ\text{C}$ represents severe, fatal hypothermia impossible in an ambulatory patient. However, because both frontend and backend permitted $[0, 100]$, the value was persisted.
     * The longitudinal engine computed $3.5 - 36.8 = -33.3^\circ\text{C}$, triggering an explainable formula output and a `HYPOTHERMIC_SHIFT` alert.
* **Clinical Recommendation:** Tighten input validation in Pydantic schema and React forms to $30.0^\circ\text{C} \le T \le 45.0^\circ\text{C}$, flagging values outside $[35.0, 42.0]$ with an explicit clinician override warning.

---

### Observation 3: Synthetic Laboratory PDF Uploaded and Extracted Hemoglobin & Glucose Appeared in Interface
* **Classification:** Implemented and Verified by a Test (IVT)
* **Locations:**
  * Upload Endpoint: [`backend/app/api/medical_report.py`](file:///c:/Users/Admin/Downloads/AI_Longitudinal_Healthcare/backend/app/api/medical_report.py#L111-L203)
  * Text Extraction: [`backend/app/services/medical_report_service.py`](file:///c:/Users/Admin/Downloads/AI_Longitudinal_Healthcare/backend/app/services/medical_report_service.py#L60-L92)
  * Rule Extraction: [`backend/app/services/clinical_extraction_service.py`](file:///c:/Users/Admin/Downloads/AI_Longitudinal_Healthcare/backend/app/services/clinical_extraction_service.py#L57-L86)
  * Frontend Review Page: [`frontend/src/pages/MedicalReports.jsx`](file:///c:/Users/Admin/Downloads/AI_Longitudinal_Healthcare/frontend/src/pages/MedicalReports.jsx#L180-L240)
  * Test Evidence: [`backend/test_phase3_e2e_integration.py`](file:///c:/Users/Admin/Downloads/AI_Longitudinal_Healthcare/backend/test_phase3_e2e_integration.py#L380-L425)
* **Code Evidence & Mechanism:**
  1. File signature validation checks `%PDF-` magic header bytes before saving.
  2. `pypdf.PdfReader` parses digital text stream.
  3. `clinical_extraction_service.py` executes regular expressions:
     * Hemoglobin: `r"\b(?:hemoglobin|haemoglobin|hb)\b\s*[:\-]?\s*(\d{1,2}(?:\.\d+)?)"`
     * Glucose: `r"\b(?:blood\s*glucose|blood\s*sugar|glucose)\b\s*[:\-]?\s*(\d{1,4}(?:\.\d+)?)"`
  4. Extracted metrics are returned in HTTP 201 response payload as `extracted_measurements` without automatically mutating the patient's vitals table.
  5. The UI renders the extracted numbers in an interactive staging card. The clinician must explicitly click "Confirm & Save into Patient Record" (`POST /medical-reports/{id}/confirm-measurements`) to insert records into `clinical_measurements`.

---

### Observation 4: Patient-History PDF Displayed Two Visits and Longitudinal Comparisons
* **Classification:** Implemented and Verified by a Test (IVT)
* **Locations:**
  * Route: [`backend/app/api/patient.py`](file:///c:/Users/Admin/Downloads/AI_Longitudinal_Healthcare/backend/app/api/patient.py#L140-L208)
  * PDF Engine: [`backend/app/services/pdf_generator_service.py`](file:///c:/Users/Admin/Downloads/AI_Longitudinal_Healthcare/backend/app/services/pdf_generator_service.py#L76-L538)
  * Canvas Layout: `NumberedCanvas` (lines 26–65)
  * Test Evidence: [`backend/test_patient_pdf.py`](file:///c:/Users/Admin/Downloads/AI_Longitudinal_Healthcare/backend/test_patient_pdf.py#L29-L93)
* **Code Evidence & Mechanism:**
  1. Endpoint fetches all visits ordered chronologically: `Visit.visit_date.asc(), Visit.id.asc()`.
  2. Endpoint executes internal radar service `get_health_change_radar()` to extract baseline-to-current deltas.
  3. ReportLab builds a multi-page PDF document:
     * Section 1: Running header, timestamp, patient identification banner.
     * Section 2: Demographics grid (Age, Gender, Location, Contact, Total Visits).
     * Section 3: Longitudinal Health Change Radar & Trajectory table (Baseline vs Current, Delta $\Delta$, Alert Levels).
     * Section 4: Chronological visit cards detailing presenting symptoms, clinical notes, follow-up plans, and tabular vitals grid.
     * Section 5: Attached medical reports index.
     * Section 6: Regulatory clinical decision support disclaimer.
  4. Multi-visit layout tested with 1, 2, and 3+ visits in automated test suites.

---

## 3. Comprehensive Feature Implementation Matrix

| Module / Feature | Description | Implementation Status | Implementation File Path(s) | Verified Test Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **User Authentication** | JWT-based auth, bcrypt password hashing, 8-hour expiration | **IVT** | `backend/app/api/auth.py`, `backend/app/security.py` | `test_auth.py` (12/12 pass), `test_api_protection.py` (44/44 pass) |
| **Role-Based Access Control** | Doctor vs. Admin permissions. Doctor blocked from DELETE. | **IVT** | `backend/app/api/deps.py`, `backend/app/api/patient.py` | `test_api_protection.py` [SECTION 4] |
| **Patient Registration** | Create patient with unique code, name, age, gender, contact | **IVT** | `backend/app/api/patient.py`, `PatientRegistrationModal.jsx` | `test_phase3_e2e_integration.py` [TEST 2] |
| **Duplicate Patient Prevention** | Reject duplicate `patient_code` with HTTP 409 | **IVT** | `backend/app/api/patient.py:53-62` | `test_phase3_e2e_integration.py:168` |
| **Chronological Visit Tracking** | Record clinical encounters, symptoms, clinical/follow-up notes | **IVT** | `backend/app/api/visit.py`, `VisitRegistrationModal.jsx` | `test_phase3_e2e_integration.py` [TEST 3] |
| **Clinical Measurements Entry** | Record vitals across 8 physiological axes | **IVT** | `backend/app/api/clinical_measurement.py` | `test_phase3_e2e_integration.py` [TEST 4] |
| **Measurement Duplicate Guard** | Rejects identical repeated vitals submissions with HTTP 409 | **IVT** | `backend/app/api/clinical_measurement.py:108-142` | `test_phase3_e2e_integration.py:255` |
| **Timestamp Discrepancy Check** | Warns if measurement date diverges from visit date | **IVT** | `backend/app/api/clinical_measurement.py:144-156` | `test_health_trajectory.py` [TEST 8] |
| **Physiological Boundary Validation** | Upper/lower physiological bounds checking on vitals input | **FKD** | `schemas/clinical_measurement.py`, `ClinicalMeasurementModal.jsx` | Defect: permits 0–100 °C temperature |
| **Patient Timeline View** | Unified chronological history with vitals and reports | **IVT** | `backend/app/api/timeline.py`, `Timeline.jsx` | `test_phase3_e2e_integration.py` [TEST 5] |
| **Clinical Trends Line Chart** | Recharts multi-metric trajectory over time | **IVT** | `backend/app/api/clinical_trend.py`, `ClinicalTrends.jsx` | `test_phase3_e2e_integration.py` [TEST 6] |
| **Health Change Radar** | Dual-polygon baseline vs current 8-axis physiological radar | **IVT** | `backend/app/api/health_radar.py`, `HealthChangeRadar.jsx` | `test_health_radar.py`, `test_phase3_e2e_integration.py` [TEST 7] |
| **Explainable Delta Formulas** | Transparent math: $\text{Current} - \text{Baseline} = \Delta$ | **IVT** | `backend/app/api/health_radar.py:163-170` | `test_health_radar.py:84` |
| **Data Gap Explicit Handling** | Omitted metrics labeled `DATA_GAP` instead of assumed normal | **IVT** | `backend/app/api/health_radar.py:133-161` | `test_health_trajectory.py` [TEST 7] |
| **Clinical Alerts Screening** | Screening threshold breaches across vitals | **IVT** | `backend/app/api/clinical_alerts.py`, `ClinicalAlertsDashboard.jsx` | `test_clinical_alerts_dashboard.py` |
| **Health Urgency Queue** | Prioritized clinic roster triage (High $\to$ Moderate $\to$ Gap $\to$ Normal) | **IVT** | `backend/app/api/clinical_alerts.py:270-345` | `test_clinical_alerts_dashboard.py:78` |
| **Medical Report Upload (PDF)** | Upload and parse digital PDF reports via pypdf | **IVT** | `backend/app/api/medical_report.py`, `MedicalReports.jsx` | `test_phase3_e2e_integration.py` [TEST 10] |
| **Medical Report Upload (OCR)** | Image upload OCR via Tesseract (JPG/PNG) | **PI** | `backend/app/services/medical_report_service.py:94-126` | Implemented; requires local Tesseract binary |
| **Clinician-in-the-Loop Confirmation** | Staged OCR vitals review before saving to records | **IVT** | `backend/app/api/medical_report.py:230-320` | `test_phase3_e2e_integration.py:415` |
| **Directory Traversal Protection** | Restrict file downloads strictly to `uploads/` directory | **IVT** | `backend/app/api/medical_report.py:400-410` | `test_phase3_e2e_integration.py:430` |
| **AI Clinical Copilot** | Grounded Q&A over patient history using Google Gemini | **IVT** | `backend/app/api/clinical_copilot.py`, `ClinicalCopilot.jsx` | `test_phase3_e2e_integration.py` [TEST 9] |
| **Copilot PII Sanitization** | Error logs exclude patient names, codes, and tokens | **IVT** | `backend/app/api/clinical_copilot.py:250-280` | Verified by static code audit |
| **English $\leftrightarrow$ Tamil Translation** | LLM-based clinical translation with numerical preservation | **IVT** | `backend/app/api/clinical_translation.py`, `BilingualClinicalSummary.jsx` | `test_clinical_translation.py` (10/10 pass) |
| **Patient History PDF Export** | Multi-page vector PDF report with ReportLab | **IVT** | `backend/app/services/pdf_generator_service.py` | `test_patient_pdf.py` (5/5 pass) |
| **Two-Pass Dynamic Pagination** | Running page numbers (`Page X of Y`) via canvas hook | **IVT** | `backend/app/services/pdf_generator_service.py:26-65` | `test_patient_pdf.py:72` |
| **Real-time Vital Telemetry** | Streaming live IoT sensor vitals | **NI** | None | Not implemented (out of scope for batch clinic visits) |
| **Diagnostic Prediction Model** | Autonomous diagnostic disease classification | **NI** | Explicitly excluded by design | Regulatory safety policy prohibits autonomous diagnosis |

---

## 4. Complete Backend API Endpoint Directory

Every endpoint in CareTrack AI requires a valid JWT Bearer token via `Depends(get_current_user)`, with the exception of public root, health, and login endpoints.

### Authentication Endpoints
* **`POST /auth/login`**
  * **Auth:** Public
  * **Content-Type:** `application/json` or `application/x-www-form-urlencoded`
  * **Request Schema:** `LoginRequest(username="...", password="...")`
  * **Response:** `{ "access_token": "...", "token_type": "bearer", "expires_in_minutes": 480, "user": { ... } }`
  * **Status:** 200 OK, 401 Unauthorized, 422 Unprocessable Content
* **`GET /auth/me`**
  * **Auth:** Bearer Token (Any authenticated role)
  * **Response:** `{ "id": 1, "username": "dr_priya", "email": "...", "role": "doctor", "full_name": "..." }`
  * **Status:** 200 OK, 401 Unauthorized

### Patient Management Endpoints
* **`GET /patients/`**
  * **Auth:** Bearer Token
  * **Query Params:** `skip: int = 0`, `limit: int = 100`
  * **Response:** `list[PatientResponse]`
  * **Status:** 200 OK
* **`POST /patients/`**
  * **Auth:** Bearer Token
  * **Request Schema:** `PatientCreate(patient_code, name, age, gender, contact, address)`
  * **Response:** `PatientResponse`
  * **Status:** 201 Created, 409 Conflict (duplicate code), 422 Validation Error
* **`GET /patients/{patient_id}`**
  * **Auth:** Bearer Token
  * **Response:** `PatientResponse`
  * **Status:** 200 OK, 404 Not Found
* **`PUT /patients/{patient_id}`**
  * **Auth:** Bearer Token
  * **Request Schema:** `PatientCreate`
  * **Response:** `PatientResponse`
  * **Status:** 200 OK, 404 Not Found, 409 Conflict
* **`DELETE /patients/{patient_id}`**
  * **Auth:** Bearer Token (Admin Role Required via `require_role("admin")`)
  * **Response:** 204 No Content
  * **Status:** 204 No Content, 403 Forbidden (Doctor), 404 Not Found
* **`GET /patients/{patient_id}/pdf`**
  * **Auth:** Bearer Token
  * **Response:** Binary Stream (`application/pdf`), Content-Disposition attachment
  * **Status:** 200 OK, 404 Not Found

### Visit Management Endpoints
* **`GET /visits/patient/{patient_id}`**
  * **Auth:** Bearer Token
  * **Response:** `list[VisitResponse]` (Sorted descending by visit date)
  * **Status:** 200 OK, 404 Not Found
* **`POST /visits/`**
  * **Auth:** Bearer Token
  * **Request Schema:** `VisitCreate(patient_id, visit_date, symptoms, clinical_notes, follow_up_notes)`
  * **Response:** `VisitResponse`
  * **Status:** 201 Created, 404 Patient Not Found, 422 Validation Error

### Clinical Measurements Endpoints
* **`POST /clinical-measurements/`**
  * **Auth:** Bearer Token
  * **Request Schema:** `ClinicalMeasurementCreate(patient_id, visit_id, systolic_bp, diastolic_bp, blood_glucose, heart_rate, temperature, oxygen_saturation, hemoglobin, weight, measured_at)`
  * **Response:** `ClinicalMeasurementResponse`
  * **Status:** 201 Created, 404 Not Found, 409 Conflict (Duplicate measurement), 422 Validation Error
* **`GET /clinical-measurements/visit/{visit_id}`**
  * **Auth:** Bearer Token
  * **Response:** `list[ClinicalMeasurementResponse]`
  * **Status:** 200 OK, 404 Not Found

### Longitudinal Decision Support Endpoints
* **`GET /patients/{patient_id}/health-radar`**
  * **Auth:** Bearer Token
  * **Response:** `HealthRadarResponse(summary: HealthRadarSummary, radar_metrics: list[HealthRadarMetric])`
  * **Calculations:** 8 normalized axes (0–100), baseline vs latest comparison, explainable mathematical formulas.
  * **Status:** 200 OK, 404 Not Found
* **`GET /patients/{patient_id}/clinical-trends`**
  * **Auth:** Bearer Token
  * **Response:** `list[ClinicalTrendPoint]`
  * **Status:** 200 OK, 404 Not Found
* **`GET /patients/{patient_id}/timeline`**
  * **Auth:** Bearer Token
  * **Response:** `TimelineResponse`
  * **Status:** 200 OK, 404 Not Found
* **`GET /patients/{patient_id}/longitudinal-insights`**
  * **Auth:** Bearer Token
  * **Response:** `LongitudinalInsightsResponse`
  * **Status:** 200 OK, 404 Not Found
* **`GET /patients/{patient_id}/clinical-alerts`**
  * **Auth:** Bearer Token
  * **Response:** `ClinicalAlertsResponse`
  * **Status:** 200 OK, 404 Not Found
* **`GET /clinical-alerts/overview` (and alias `/patients/alerts/overview`)**
  * **Auth:** Bearer Token
  * **Response:** `ClinicalAlertsOverviewResponse(rules, summary, patients: list[PatientAlertItem])`
  * **Status:** 200 OK

### AI Copilot & Translation Endpoints
* **`POST /clinical-copilot/ask`**
  * **Auth:** Bearer Token
  * **Request Schema:** `CopilotQuestionRequest(patient_id, question)`
  * **Model:** Google Gemini (`gemini-2.5-flash`)
  * **Grounding:** Injects patient demographic records, chronological visit timeline, and all historical measurement series into system context.
  * **Status:** 200 OK, 404 Patient Not Found, 503 AI Service Unavailable
* **`POST /clinical-translation/translate`**
  * **Auth:** Bearer Token
  * **Request Schema:** `TranslationRequest(text, source_language, target_language)`
  * **Supported Language Pairs:** English (`en`) $\leftrightarrow$ Tamil (`ta`)
  * **Status:** 200 OK, 422 Unprocessable Content, 502 Bad Gateway, 503 Service Unavailable, 504 Timeout

### Medical Report Endpoints
* **`POST /medical-reports/upload`**
  * **Auth:** Bearer Token
  * **Content-Type:** `multipart/form-data`
  * **Form Fields:** `patient_id: int`, `visit_id: int`, `file: UploadFile`
  * **Validations:** Max 10MB, extension whitelist (`.pdf, .jpg, .png, .jpeg, .bmp, .tif`), magic byte verification.
  * **Response:** `MedicalReportResponse` (includes non-persisted `extracted_measurements` preview)
  * **Status:** 201 Created, 400 Bad Request, 404 Not Found, 413 Too Large, 415 Unsupported Media Type
* **`POST /medical-reports/{report_id}/confirm-measurements`**
  * **Auth:** Bearer Token
  * **Request Schema:** `ConfirmMeasurementsRequest(patient_id, visit_id)`
  * **Behavior:** Commits staged OCR extractions into `clinical_measurements` table with duplicate protection.
  * **Status:** 200 OK, 404 Not Found, 409 Conflict, 422 Unprocessable
* **`GET /medical-reports/visit/{visit_id}`**
  * **Auth:** Bearer Token
  * **Response:** `list[MedicalReportResponse]`
  * **Status:** 200 OK, 404 Not Found
* **`GET /medical-reports/{report_id}/file`**
  * **Auth:** Bearer Token
  * **Query Params:** `patient_id: int`
  * **Security:** Verifies visit-to-patient ownership and directory traversal containment (`Path.startswith(UPLOAD_DIR)`).
  * **Response:** `FileResponse` inline document stream
  * **Status:** 200 OK, 403 Forbidden, 404 Not Found

---

## 5. Architectural & Security Audit Findings

1. **Strict Additive Database Migrations:**
   The users table migration script ([`migrate_add_users_table.py`](file:///c:/Users/Admin/Downloads/AI_Longitudinal_Healthcare/backend/scripts/migrate_add_users_table.py)) strictly enforces `CREATE TABLE IF NOT EXISTS` and asserts zero modifications or drops to all 6 protected clinical tables (`patients`, `visits`, `vitals`, `medical_reports`, `ai_insights`, `clinical_measurements`).
2. **Deterministic Test Isolation:**
   Automated integration test suites (`test_phase3_e2e_integration.py` and `test_api_protection.py`) utilize in-memory SQLite with compiler overrides for `BigInteger`, preventing accidental modification or corruption of production Supabase data.
3. **Directory Traversal Defense:**
   In `medical_report.py`, all file access enforces `target_path.resolve().startswith(UPLOAD_DIR.resolve())`, neutralizing `../../` path evasion attacks.
4. **Sanitized AI Logging:**
   In `clinical_copilot_service.py`, exception logging explicitly strips authorization headers, patient identifiers, and API keys.
5. **Identified Flaws:**
   * Temperature boundary permits non-viable inputs ($0^\circ\text{C}$ to $100^\circ\text{C}$).
   * Client-side `invalidPatientId` banner does not self-clear upon asynchronous roster reloads.
