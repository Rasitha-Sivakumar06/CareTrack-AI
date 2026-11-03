import ClinicalCopilot from "./pages/ClinicalCopilot";
import { useEffect, useState } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
} from "react-router-dom";
import { LogOut } from "lucide-react";

import "./App.css";

import { API_URL, authFetchJson } from "./config";
import { AuthProvider, useAuth } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import { PatientProvider, usePatient } from "./context/PatientContext";
import PatientSelector from "./components/PatientSelector";
import HealthChangeRadar from "./components/HealthChangeRadar";
import HealthTrajectoryPanel from "./components/HealthTrajectoryPanel";
import Dashboard from "./pages/Dashboard";
import MedicalReports from "./pages/MedicalReports";
import ClinicalTrends from "./pages/ClinicalTrends";
import Timeline from "./pages/Timeline";
import ClinicalAlertsDashboard from "./pages/ClinicalAlertsDashboard";
import FormattedClinicalText from "./components/ClinicalContentRenderer";

/* -------------------------------------------------------
   MAIN APPLICATION ROUTES
------------------------------------------------------- */

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <PatientProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/radar"
              element={
                <ProtectedRoute>
                  <RadarPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/trajectory"
              element={
                <ProtectedRoute>
                  <TrajectoryPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/alerts"
              element={
                <ProtectedRoute>
                  <ClinicalAlertsDashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/patients"
              element={
                <ProtectedRoute>
                  <PatientPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/reports"
              element={
                <ProtectedRoute>
                  <MedicalReports />
                </ProtectedRoute>
              }
            />
            <Route
              path="/trends"
              element={
                <ProtectedRoute>
                  <ClinicalTrends />
                </ProtectedRoute>
              }
            />
            <Route
              path="/timeline"
              element={
                <ProtectedRoute>
                  <Timeline />
                </ProtectedRoute>
              }
            />
            <Route
              path="/copilot"
              element={
                <ProtectedRoute>
                  <ClinicalCopilot />
                </ProtectedRoute>
              }
            />
            <Route
              path="/insights"
              element={
                <ProtectedRoute>
                  <LongitudinalInsightsPage />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </PatientProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

function DashboardPage() {
  const navigate = useNavigate();

  return <Dashboard navigate={navigate} />;
}

function RadarPage() {
  const apiStatus = useApiStatus();

  return (
    <main className="patient-workspace">
      <WorkspaceHeader apiStatus={apiStatus} />
      <WorkspaceIntro
        eyebrow="CARETRACK AI · HEALTH CHANGE RADAR"
        title="Multidimensional Health Trajectory"
        description="Visualize multi-axial physiological shifts between baseline and recent visits with explainable change calculations and decision support."
      />
      <PatientSelector />
      <HealthChangeRadar />
      <WorkspaceFooter />
    </main>
  );
}

function TrajectoryPage() {
  const apiStatus = useApiStatus();

  return (
    <main className="patient-workspace">
      <WorkspaceHeader apiStatus={apiStatus} />
      <WorkspaceIntro
        eyebrow="CARETRACK AI · HEALTHTRAJECTORY ENGINE"
        title="Longitudinal Trajectory & Change Detection"
        description="Explainable longitudinal clinical change detection comparing baseline, previous, and latest readings with transparent delta arithmetic."
      />
      <PatientSelector />
      <HealthTrajectoryPanel />
      <WorkspaceFooter />
    </main>
  );
}

/* -------------------------------------------------------
   API UTILITIES
------------------------------------------------------- */

async function fetchJson(url) {
  return authFetchJson(url);
}

function useApiStatus() {
  const [apiStatus, setApiStatus] = useState("Checking...");

  useEffect(() => {
    let active = true;

    fetchJson(`${API_URL}/health`)
      .then(() => {
        if (active) setApiStatus("Connected");
      })
      .catch(() => {
        if (active) setApiStatus("Disconnected");
      });

    return () => {
      active = false;
    };
  }, []);

  return apiStatus;
}

/* -------------------------------------------------------
   SHARED WORKSPACE COMPONENTS
------------------------------------------------------- */

function WorkspaceHeader({ apiStatus = "Connected" }) {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  return (
    <header className="workspace-header">
      <button
        type="button"
        className="back-button"
        onClick={() => navigate("/")}
      >
        ← Dashboard
      </button>

      <div className="header-actions-group">
        <span
          className={
            apiStatus === "Connected"
              ? "api-status"
              : "api-status offline"
          }
        >
          <span className="live-dot" />
          API: {apiStatus}
        </span>

        {user && (
          <div className="user-profile-badge">
            <span className={`user-role-tag ${user.role || ""}`}>
              {user.role}
            </span>
            <span className="user-name">
              {user.full_name || user.username}
            </span>
            <button
              type="button"
              className="logout-button"
              onClick={logout}
              title="Sign out of CareTrack AI"
            >
              <LogOut size={13} />
              <span>Sign out</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
}

function WorkspaceFooter() {
  return (
    <footer className="workspace-footer">
      CareTrack AI · Longitudinal Healthcare Platform
    </footer>
  );
}

function WorkspaceIntro({ eyebrow, title, description }) {
  return (
    <section className="workspace-intro">
      <span className="eyebrow">{eyebrow}</span>
      <h1>{title}</h1>
      <p>{description}</p>
    </section>
  );
}

function ErrorMessage({ children }) {
  if (!children) return null;

  return (
    <p className="workspace-error" role="alert">
      {children}
    </p>
  );
}

function LoadingMessage({ children }) {
  return <p role="status">{children}</p>;
}

function formatDate(value) {
  if (!value) return "Date unavailable";

  const dateOnly = String(value).match(
    /^(\d{4})-(\d{2})-(\d{2})$/
  );

  const date = dateOnly
    ? new Date(
        Number(dateOnly[1]),
        Number(dateOnly[2]) - 1,
        Number(dateOnly[3])
      )
    : new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/* -------------------------------------------------------
   PATIENT RECORDS
------------------------------------------------------- */

function PatientPage() {
  const { selectedPatientId, selectPatient } = usePatient();
  const [patientId, setPatientId] = useState(selectedPatientId || "");
  const [timeline, setTimeline] = useState(null);
  const [trends, setTrends] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [loadedPatientId, setLoadedPatientId] = useState("");

  const apiStatus = useApiStatus();
  const navigate = useNavigate();

  // Sync when selected patient changes
  useEffect(() => {
    if (selectedPatientId && selectedPatientId !== loadedPatientId) {
      setPatientId(selectedPatientId);
      loadPatientDataById(selectedPatientId);
    }
  }, [selectedPatientId]);

  async function loadPatientDataById(idToLoad) {
    const id = String(idToLoad).trim();

    if (!/^\d+$/.test(id) || Number(id) < 1) {
      setError("Enter a valid positive numeric patient ID.");
      return;
    }

    setError("");
    setTimeline(null);
    setTrends(null);
    setLoadedPatientId("");
    setLoading(true);

    try {
      const [timelineData, trendsData] = await Promise.all([
        fetchJson(`${API_URL}/patients/${id}/timeline`),
        fetchJson(`${API_URL}/patients/${id}/clinical-trends`),
      ]);

      setTimeline(timelineData);
      setTrends(trendsData);
      setLoadedPatientId(id);
      selectPatient(id);
    } catch (err) {
      setError(
        err.message ||
          "Could not load patient data. Check whether the backend is running."
      );
    } finally {
      setLoading(false);
    }
  }

  function loadPatientData(event) {
    event.preventDefault();
    loadPatientDataById(patientId);
  }

  const measurements = Array.isArray(trends?.measurements)
    ? trends.measurements
    : [];

  const fields = [
    ["Blood Pressure", "blood_pressure", "mmHg"],
    ["Systolic BP", "systolic_bp", "mmHg"],
    ["Diastolic BP", "diastolic_bp", "mmHg"],
    ["Hemoglobin", "hemoglobin", "g/dL"],
    ["Blood Glucose", "blood_glucose", "mg/dL"],
    ["Heart Rate", "heart_rate", "bpm"],
    ["Temperature", "temperature", "°C"],
    ["Oxygen Saturation", "oxygen_saturation", "%"],
    ["Weight", "weight", "kg"],
  ];

  const patientName =
    timeline?.patient?.name ||
    timeline?.name ||
    `Patient ${loadedPatientId}`;

  const patientVisits = Array.isArray(timeline?.visits)
    ? timeline.visits
    : [];

  return (
    <main className="patient-workspace">
      <WorkspaceHeader apiStatus={apiStatus} />

      <WorkspaceIntro
        eyebrow="CARETRACK AI · PATIENT RECORDS"
        title="Patient History"
        description="Retrieve longitudinal clinical information from the connected backend."
      />

      <PatientSelector showPdf onPatientChange={(newId) => loadPatientDataById(newId)} />

      <section className="workspace-panel">
        <form className="patient-search" onSubmit={loadPatientData}>
          <label htmlFor="patient-id">Patient ID</label>

          <div className="patient-search-row">
            <input
              id="patient-id"
              type="text"
              inputMode="numeric"
              value={patientId}
              onChange={(event) => setPatientId(event.target.value)}
              placeholder="Enter patient ID"
            />

            <button type="submit" disabled={loading}>
              {loading ? "Loading..." : "Load Patient →"}
            </button>
          </div>
        </form>
      </section>

      <ErrorMessage>{error}</ErrorMessage>

      {loading && (
        <LoadingMessage>Loading patient records...</LoadingMessage>
      )}

      {timeline && trends && (
        <>
          <section className="patient-summary">
            <div>
              <span className="eyebrow">PATIENT PROFILE</span>
              <h2>{patientName}</h2>
              <p>Patient ID: {loadedPatientId}</p>
            </div>

            <div className="summary-stat">
              <strong>{measurements.length}</strong>
              <span>Measurement entries</span>
            </div>
          </section>

          <section className="workspace-panel">
            <h2>Patient Workspaces</h2>

            <p className="panel-description">
              Open this patient's timeline, clinical trends, or longitudinal
              insights.
            </p>

            <div className="patient-search-row">
              <button
                type="button"
                onClick={() =>
                  navigate(`/timeline?patientId=${loadedPatientId}`)
                }
              >
                Patient Timeline →
              </button>

              <button
                type="button"
                onClick={() =>
                  navigate(`/trends?patientId=${loadedPatientId}`)
                }
              >
                Clinical Trends →
              </button>

              <button
                type="button"
                onClick={() =>
                  navigate(`/insights?patientId=${loadedPatientId}`)
                }
              >
                Longitudinal Insights →
              </button>
            </div>
          </section>

          <section className="workspace-panel">
            <h2>Clinical Measurements</h2>

            <p className="panel-description">
              Recorded values returned by the backend, grouped by visit.
            </p>

            {measurements.length === 0 ? (
              <p>
                No clinical measurements have been recorded for this patient.
              </p>
            ) : (
              measurements.map((item, index) => (
                <article
                  className="visit-card"
                  key={`${item.visit_id ?? "visit"}-${index}`}
                >
                  <div className="visit-heading">
                    <div>
                      <span className="eyebrow">CLINICAL VISIT</span>
                      <h3>Visit #{item.visit_id ?? "—"}</h3>
                    </div>

                    <span className="visit-date">
                      {formatDate(item.visit_date)}
                    </span>
                  </div>

                  <div className="clinical-measurement-grid">
                    {fields.map(([label, key, unit]) => {
                      const value = item[key];

                      return (
                        <div className="clinical-measurement" key={key}>
                          <span>{label}</span>
                          <strong>
                            {value !== null &&
                            value !== undefined &&
                            value !== ""
                              ? `${value} ${unit}`
                              : "—"}
                          </strong>
                        </div>
                      );
                    })}
                  </div>
                </article>
              ))
            )}
          </section>

          <section className="workspace-panel">
            <h2>Visit Summary</h2>

            <div className="visit-summary-row">
              <span>Recorded visits</span>
              <strong>{patientVisits.length}</strong>
            </div>

            <p className="clinical-disclaimer">
              These recorded values support clinical review and are not a
              diagnosis. A qualified healthcare professional must interpret
              the information.
            </p>
          </section>
        </>
      )}

      <WorkspaceFooter />
    </main>
  );
}

/* -------------------------------------------------------
   LONGITUDINAL INSIGHTS AND CLINICAL ALERTS
------------------------------------------------------- */

function LongitudinalInsightsPage() {
  const { selectedPatientId, selectPatient } = usePatient();
  const params = new URLSearchParams(window.location.search);
  const initialPatientId = params.get("patientId") || selectedPatientId || "";

  const [patientId, setPatientId] = useState(initialPatientId);
  const [insightsData, setInsightsData] = useState(null);
  const [alertsData, setAlertsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [loadedPatientId, setLoadedPatientId] = useState("");

  const apiStatus = useApiStatus();

  // Auto-sync when selected patient changes
  useEffect(() => {
    if (selectedPatientId && selectedPatientId !== loadedPatientId) {
      setPatientId(selectedPatientId);
      loadInsightsById(selectedPatientId);
    }
  }, [selectedPatientId]);

  async function loadInsightsById(idToLoad) {
    const id = String(idToLoad).trim();

    if (!/^\d+$/.test(id) || Number(id) < 1) {
      setError("Enter a valid positive numeric patient ID.");
      return;
    }

    setInsightsData(null);
    setAlertsData(null);
    setError("");
    setLoading(true);

    try {
      const [insights, alerts] = await Promise.all([
        fetchJson(`${API_URL}/patients/${id}/longitudinal-insights`),
        fetchJson(`${API_URL}/patients/${id}/clinical-alerts`),
      ]);

      setInsightsData(insights);
      setAlertsData(alerts);
      setLoadedPatientId(id);
      selectPatient(id);
    } catch (err) {
      setError(
        err.message ||
          "Could not load insights and alerts. Check the backend and patient ID."
      );
    } finally {
      setLoading(false);
    }
  }

  function loadInsights(event) {
    event.preventDefault();
    loadInsightsById(patientId);
  }

  const insights = Array.isArray(insightsData?.insights)
    ? insightsData.insights
    : [];

  const alerts = Array.isArray(alertsData?.alerts)
    ? alertsData.alerts
    : [];

  return (
    <main className="patient-workspace">
      <WorkspaceHeader apiStatus={apiStatus} />

      <WorkspaceIntro
        eyebrow="CARETRACK AI · DECISION SUPPORT"
        title="Longitudinal Insights"
        description="Compare recorded measurements across visits and review clinical screening alerts."
      />

      <PatientSelector onPatientChange={(newId) => loadInsightsById(newId)} />

      <section className="workspace-panel">
        <form className="patient-search" onSubmit={loadInsights}>
          <label htmlFor="insights-patient-id">Patient ID</label>

          <div className="patient-search-row">
            <input
              id="insights-patient-id"
              value={patientId}
              onChange={(event) => setPatientId(event.target.value)}
              inputMode="numeric"
              placeholder="Enter patient ID"
            />

            <button type="submit" disabled={loading}>
              {loading ? "Loading..." : "Load Insights →"}
            </button>
          </div>
        </form>
      </section>

      <ErrorMessage>{error}</ErrorMessage>

      {loading && (
        <LoadingMessage>
          Loading insights and clinical alerts...
        </LoadingMessage>
      )}

      {insightsData && alertsData && (
        <>
          <section className="patient-summary">
            <div>
              <span className="eyebrow">PATIENT</span>
              <h2>
                {insightsData.patient_name || `Patient ${patientId}`}
              </h2>
              <p>Patient ID: {insightsData.patient_id ?? patientId}</p>
            </div>

            <div className="summary-stat">
              <strong>{insights.length}</strong>
              <span>Metrics compared</span>
            </div>
          </section>

          <section className="workspace-panel">
            <h2>Comparison Summary</h2>

            <FormattedClinicalText
              text={
                insightsData.summary ||
                "No comparison summary was returned."
              }
            />

            <div className="visit-summary-row">
              <span>Previous visit</span>
              <strong>
                {formatDate(insightsData.previous_visit_date)}
              </strong>
            </div>

            <div className="visit-summary-row">
              <span>Current visit</span>
              <strong>
                {formatDate(insightsData.current_visit_date)}
              </strong>
            </div>
          </section>

          <section className="workspace-panel">
            <h2>Measurement Changes</h2>

            {insights.length === 0 ? (
              <p>
                {insightsData.summary ||
                  "There are not enough measurements to compare visits."}
              </p>
            ) : (
              insights.map((item, index) => (
                <article
                  className="visit-card"
                  key={`${item.metric}-${index}`}
                >
                  <div className="visit-heading">
                    <h3>{item.metric}</h3>
                    <span className="visit-date">
                      {item.status || "Review"}
                    </span>
                  </div>

                  <div className="clinical-measurement-grid">
                    <div className="clinical-measurement">
                      <span>Previous</span>
                      <strong>
                        {item.previous_value ?? "—"} {item.unit || ""}
                      </strong>
                    </div>

                    <div className="clinical-measurement">
                      <span>Current</span>
                      <strong>
                        {item.current_value ?? "—"} {item.unit || ""}
                      </strong>
                    </div>

                    <div className="clinical-measurement">
                      <span>Change</span>
                      <strong>
                        {item.change === null ||
                        item.change === undefined
                          ? "—"
                          : `${item.change > 0 ? "+" : ""}${item.change} ${item.unit || ""}`}
                      </strong>
                    </div>
                  </div>

                  <FormattedClinicalText
                    text={item.observation || "No observation provided."}
                  />
                </article>
              ))
            )}
          </section>

          <section className="workspace-panel">
            <h2>Clinical Screening Alerts</h2>

            <FormattedClinicalText
              text={
                alertsData.summary ||
                "No alert summary was returned."
              }
            />

            {alerts.length === 0 ? (
              <p>
                No recorded values crossed the configured clinical screening
                thresholds. This does not establish that the patient is healthy.
              </p>
            ) : (
              alerts.map((alert, index) => (
                <article
                  className="visit-card"
                  key={`${alert.metric}-${index}`}
                >
                  <div className="visit-heading">
                    <h3>
                      <FormattedClinicalText text={alert.metric} inline />
                    </h3>
                    <span className="visit-date">
                      {alert.severity || "Review"}
                    </span>
                  </div>

                  <div className="clinical-measurement-grid">
                    <div className="clinical-measurement">
                      <span>Recorded value</span>
                      <strong>
                        {alert.value} {alert.unit || ""}
                      </strong>
                    </div>

                    <div className="clinical-measurement">
                      <span>Alert threshold</span>
                      <strong>
                        {alert.threshold || "Not specified"}
                      </strong>
                    </div>
                  </div>

                  <FormattedClinicalText
                    text={
                      alert.reason ||
                      "Professional review is recommended."
                    }
                  />
                </article>
              ))
            )}

            <FormattedClinicalText
              text={
                alertsData.disclaimer ||
                "Clinical screening rules only. These alerts are not diagnoses. A qualified healthcare professional must review the results."
              }
              className="clinical-disclaimer"
            />
          </section>
        </>
      )}

      <WorkspaceFooter />
    </main>
  );
}
