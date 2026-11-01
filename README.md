# CareTrack AI — AI Longitudinal Healthcare Platform

CareTrack AI is a clinical decision-support platform designed for traveling physicians and longitudinal patient monitoring across dispersed community clinics. It aggregates historical visits, clinical measurements, OCR-extracted medical reports, and AI-powered clinical guidance into a unified clinical workspace.

---

## Key Features

1. **Health Change Radar (Unique Feature)**
   - **Multidimensional Comparison**: Compares baseline physiological parameters against recent check-in values across 8 clinical axes (Blood Glucose, Systolic/Diastolic BP, Heart Rate, Oxygen Saturation, Hemoglobin, Temperature, and Body Weight).
   - **Visual Trajectory**: Dual-polygon Recharts radar visualization displaying baseline vs. current physiological footprint.
   - **Explainable Change Alerts**: Transparent mathematical breakdown (`Current - Baseline = Δ (+%)`), measurement dates, threshold breach indicators, and clinician-oriented guidance.
   - **Data-Gap Awareness**: Missing or stale measurements are explicitly flagged as `DATA_GAP` rather than assumed normal.
   - **Evidence-Backed Narrative**: Factual longitudinal trajectory synthesized directly from database facts.

2. **Longitudinal Patient Timeline**
   - Chronological visit logs with recorded symptoms, clinical notes, doctor follow-up instructions, and associated vitals.

3. **Clinical Measurements & Longitudinal Trends**
   - Multi-metric historical trend line charts powered by Recharts.
   - Duplicate prevention (rejects identical repeated submissions with HTTP 409 Conflict).
   - Timestamp alignment checks flagging date discrepancies between measurements and visits.

4. **Medical Report OCR & Extraction**
   - Upload and view clinical documents (PDF, JPG, PNG).
   - Automated text extraction and measurement preview with clinician-in-the-loop confirmation.
   - Directory traversal protection and authorized access controls.

5. **AI Clinical Copilot**
   - Context-aware clinical question answering grounded in the active patient's stored longitudinal records.
   - Powered by Google Gemini (`gemini-2.5-flash`).
   - Server-side exception logging that strictly excludes sensitive clinical details, patient identifiers, and API keys.

6. **Longitudinal Patient History PDF Export**
   - High-fidelity, multi-page vector clinical summary compiled dynamically from database records via ReportLab.
   - Includes patient demographics, longitudinal trajectory, physiological radar shifts, chronological visits, vitals tables, and attached medical reports.
   - Explicitly flags omitted or missing vitals without assuming normal values.
   - Dynamic running header/footer with page numbering and clinical confidentiality notices.

---

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic v2
- **Database**: PostgreSQL (Supabase) via SQLAlchemy `SessionLocal`
- **Frontend**: React 19, Vite 8, React Router 7, Recharts, Lucide-React
- **AI / LLM**: Google GenAI SDK (`google-genai`)

---

## Project Structure

```
AI_Longitudinal_Healthcare/
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI route controllers
│   │   │   ├── patient.py          # Patient registration & roster
│   │   │   ├── visit.py            # Visit creation & retrieval
│   │   │   ├── clinical_measurement.py # Vitals entry & duplicate protection
│   │   │   ├── health_radar.py     # Health Change Radar & explainable shifts
│   │   │   ├── clinical_trend.py   # Historical trend points
│   │   │   ├── longitudinal_insights.py # Visit-to-visit delta comparison
│   │   │   ├── clinical_alerts.py  # Screening threshold flags
│   │   │   ├── medical_report.py   # OCR report upload & download
│   │   │   └── clinical_copilot.py # AI decision-support assistant
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── schemas/                # Pydantic validation schemas
│   │   ├── services/               # OCR & Gemini LLM services
│   │   ├── database.py             # Database engine & sessionmaker
│   │   └── main.py                 # FastAPI application factory
│   ├── test_health_radar.py        # Automated test suite for Health Radar
│   ├── test_phase2_remaining.py    # Automated test suite for core workflows
│   └── requirements.txt            # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/             # Reusable UI components
│   │   │   ├── HealthChangeRadar.jsx # Radar chart & explainable alert cards
│   │   │   ├── PatientSelector.jsx   # Global patient roster dropdown
│   │   │   ├── PatientRegistrationModal.jsx
│   │   │   ├── VisitRegistrationModal.jsx
│   │   │   └── ClinicalMeasurementModal.jsx
│   │   ├── context/
│   │   │   └── PatientContext.jsx  # Global active patient state
│   │   ├── pages/                  # Dashboard, Trends, Reports, Copilot
│   │   ├── config.js               # Centralized API URL configuration
│   │   ├── App.jsx                 # Main application routes
│   │   └── App.css                 # Global theme & glassmorphic styling
│   └── package.json
└── README.md
```

---

## Getting Started

### 1. Backend Setup

```bash
cd backend

# Activate virtual environment
.\.venv\Scripts\activate   # Windows
# or: source .venv/bin/activate  # Linux/Mac

# Install dependencies (if needed)
pip install -r requirements.txt

# Start backend server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend will be available at `http://127.0.0.1:8000`. Interactive API documentation (Swagger) is at `http://127.0.0.1:8000/docs`.

### 2. Frontend Setup

```bash
cd frontend

# Install npm dependencies
npm install

# Start Vite dev server
npm run dev
```

Frontend will be available at `http://localhost:5173`.

---

## Running Automated Tests

Run the backend automated verification test suites:

```bash
# 1. Verify Health Change Radar & Patient API Slash-Tolerance
.\backend\.venv\Scripts\python.exe backend\test_health_radar.py

# 2. Verify Visits, Measurements, Duplicate Detection, & Reports
.\backend\.venv\Scripts\python.exe backend\test_phase2_remaining.py

# 3. Verify Patient History PDF Export
.\backend\.venv\Scripts\python.exe backend\test_patient_pdf.py

# 4. Verify Frontend Production Build
cd frontend && npm run build
```

---

## Responsible AI & Clinical Disclaimer

- **Clinical Decision Support Only**: CareTrack AI and the Health Change Radar generate informational, decision-support indicators. They do **not** provide automated diagnoses, prescribe treatment plans, or replace qualified medical evaluation.
- **Human Confirmation**: All screening alerts, measurement deltas, and AI copilot observations must be interpreted and confirmed by a licensed healthcare professional.
- **Data Gap Handling**: Missing or omitted measurements are never assumed normal or stable.

CI protection test: verifying pull request checks.
