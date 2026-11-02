
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Activity, LogOut } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import "./ClinicalTrends.css";
import { API_URL, authFetch } from "../config";
import { usePatient } from "../context/PatientContext";
import { useAuth } from "../context/AuthContext";
import PatientSelector from "../components/PatientSelector";
import ClinicalMeasurementModal from "../components/ClinicalMeasurementModal";

const fields = [
  { label: "Blood Pressure", key: "blood_pressure", unit: "mmHg" },
  { label: "Hemoglobin", key: "hemoglobin", unit: "g/dL" },
  { label: "Blood Glucose", key: "blood_glucose", unit: "mg/dL" },
  { label: "Heart Rate", key: "heart_rate", unit: "bpm" },
  { label: "Temperature", key: "temperature", unit: "°C" },
  { label: "Oxygen Saturation", key: "oxygen_saturation", unit: "%" },
  { label: "Weight", key: "weight", unit: "kg" },
];

const chartConfigs = [
  {
    title: "Blood Glucose",
    key: "blood_glucose",
    unit: "mg/dL",
    color: "#0d9488",
  },
  {
    title: "Systolic Blood Pressure",
    key: "systolic_bp",
    unit: "mmHg",
    color: "#6366f1",
  },
  {
    title: "Diastolic Blood Pressure",
    key: "diastolic_bp",
    unit: "mmHg",
    color: "#8b5cf6",
  },
  {
    title: "Heart Rate",
    key: "heart_rate",
    unit: "bpm",
    color: "#ea580c",
  },
  {
    title: "Weight",
    key: "weight",
    unit: "kg",
    color: "#0284c7",
  },
];

function formatDate(value) {
  if (!value) return "Unknown date";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown date";
  }

  return date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

async function readResponse(response) {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();

  return {
    detail: text || "The server returned an unexpected response.",
  };
}

function getErrorMessage(data, fallback) {
  if (typeof data?.detail === "string") {
    return data.detail;
  }

  if (Array.isArray(data?.detail)) {
    return data.detail
      .map((item) => item.msg || "Invalid input")
      .join(", ");
  }

  return fallback;
}

function TrendChart({ config, measurements }) {
  // Ensure each visit is plotted as a single data point (revisions are not treated as separate visits)
  const latestByVisit = new Map();
  for (const item of measurements) {
    if (
      item[config.key] !== null &&
      item[config.key] !== undefined &&
      item[config.key] !== "" &&
      Number.isFinite(Number(item[config.key]))
    ) {
      latestByVisit.set(item.visit_id, item);
    }
  }

  const chartData = Array.from(latestByVisit.values()).map((item) => ({
    date: formatDate(item.visit_date),
    value: Number(item[config.key]),
    visit: `Visit #${item.visit_id}`,
  }));

  return (
    <section className="trend-chart-card">
      <div className="trend-chart-heading">
        <div>
          <span className="eyebrow">MEASUREMENT HISTORY</span>
          <h3>{config.title}</h3>
        </div>

        <span className="trend-unit">{config.unit}</span>
      </div>

      {chartData.length === 0 ? (
        <div className="chart-empty">
          No {config.title.toLowerCase()} measurements available.
        </div>
      ) : chartData.length === 1 ? (
        <>
          <div className="chart-single-value">
            <strong>
              {chartData[0].value} {config.unit}
            </strong>

            <span>
              {chartData[0].visit} · {chartData[0].date}
            </span>
          </div>

          <p className="chart-note">
            Record measurements from more visits to compare changes over time.
          </p>
        </>
      ) : (
        <div className="trend-chart">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart
              data={chartData}
              margin={{ top: 12, right: 16, left: 0, bottom: 8 }}
            >
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" />

              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: "#64748b" }}
                tickLine={false}
              />

              <YAxis
                width={58}
                tick={{ fontSize: 11, fill: "#64748b" }}
                tickLine={false}
                axisLine={false}
                domain={["auto", "auto"]}
              />

              <Tooltip
                formatter={(value) => [
                  `${value} ${config.unit}`,
                  config.title,
                ]}
                labelFormatter={(label) => `Visit date: ${label}`}
                contentStyle={{
                  borderRadius: 12,
                  border: "1px solid #dbe5ef",
                }}
              />

              <Legend />

              <Line
                type="monotone"
                dataKey="value"
                name={config.title}
                stroke={config.color}
                strokeWidth={3}
                dot={{ r: 5, fill: config.color }}
                activeDot={{ r: 7 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}

function InsightCard({ item }) {
  const change = Number(item.change);

  const direction =
    change > 0 ? "increased" : change < 0 ? "decreased" : "unchanged";

  const directionLabel =
    direction === "increased"
      ? "↑ Increased"
      : direction === "decreased"
        ? "↓ Decreased"
        : "→ Unchanged";

  return (
    <article className="insight-card">
      <div className="insight-card-top">
        <h3>{item.metric}</h3>

        <span className={`insight-badge ${direction}`}>
          {Number.isFinite(change) ? directionLabel : "Change unavailable"}
        </span>
      </div>

      <div className="insight-values">
        <div>
          <span>Previous</span>
          <strong>
            {item.previous_value ?? "—"}
            {item.unit ? ` ${item.unit}` : ""}
          </strong>
        </div>

        <div>
          <span>Latest</span>
          <strong>
            {item.current_value ?? "—"}
            {item.unit ? ` ${item.unit}` : ""}
          </strong>
        </div>

        <div>
          <span>Change</span>
          <strong>
            {Number.isFinite(change) ? `${change > 0 ? "+" : ""}${change}` : "—"}
            {Number.isFinite(change) && item.unit ? ` ${item.unit}` : ""}
          </strong>
        </div>
      </div>

      <p>{item.observation || "Review the measurements with a clinician."}</p>
      <small>Requires clinical interpretation</small>
    </article>
  );
}

function ClinicalAlertCard({ alert }) {
  const severity = String(alert.severity || "review").toLowerCase();

  return (
    <article className={`clinical-alert-card ${severity}`}>
      <div className="clinical-alert-heading">
        <h3>{alert.metric || "Clinical measurement"}</h3>

        <span className={`alert-severity ${severity}`}>
          {severity.toUpperCase()} REVIEW
        </span>
      </div>

      <div className="alert-measurement">
        <div>
          <span>Recorded value</span>
          <strong>
            {alert.value ?? "—"}
            {alert.unit ? ` ${alert.unit}` : ""}
          </strong>
        </div>

        <div>
          <span>Configured threshold</span>
          <strong>{alert.threshold ?? "—"}</strong>
        </div>
      </div>

      <p>{alert.reason || "Review this measurement with a clinician."}</p>
    </article>
  );
}

export default function ClinicalTrends() {
  const { selectedPatientId, selectPatient } = usePatient();
  const { user, logout } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const queryPatientId = searchParams.get("patientId");
  const initialPatientId =
    /^\d+$/.test(queryPatientId || "") && Number(queryPatientId) > 0
      ? queryPatientId
      : selectedPatientId || "";

  const [patientId, setPatientId] = useState(initialPatientId);
  const [loadedPatientId, setLoadedPatientId] = useState("");

  const [data, setData] = useState(null);
  const [insightData, setInsightData] = useState(null);
  const [alertData, setAlertData] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [insightError, setInsightError] = useState("");
  const [alertError, setAlertError] = useState("");
  const [measModalOpen, setMeasModalOpen] = useState(false);

  async function loadTrendsById(idToLoad) {
    const id = String(idToLoad).trim();

    if (!/^\d+$/.test(id) || Number(id) < 1) {
      setError("Enter a valid positive patient ID.");
      return;
    }

    setError("");
    setInsightError("");
    setAlertError("");

    setData(null);
    setInsightData(null);
    setAlertData(null);

    // Preserve the selected patient in the URL.
    setSearchParams({ patientId: id });
    setLoading(true);

    try {
      const [trendsResponse, insightsResponse, alertsResponse] =
        await Promise.all([
          authFetch(`${API_URL}/patients/${id}/clinical-trends`),
          authFetch(`${API_URL}/patients/${id}/longitudinal-insights`),
          authFetch(`${API_URL}/patients/${id}/clinical-alerts`),
        ]);

      const [trendsResult, insightsResult, alertsResult] = await Promise.all([
        readResponse(trendsResponse),
        readResponse(insightsResponse),
        readResponse(alertsResponse),
      ]);

      if (!trendsResponse.ok) {
        throw new Error(
          getErrorMessage(trendsResult, "Unable to load clinical trends.")
        );
      }

      setData(trendsResult);
      setLoadedPatientId(id);
      selectPatient(id);

      if (insightsResponse.ok) {
        setInsightData(insightsResult);
      } else {
        setInsightError(
          getErrorMessage(
            insightsResult,
            "Longitudinal insights could not be calculated."
          )
        );
      }

      if (alertsResponse.ok) {
        setAlertData(alertsResult);
      } else {
        setAlertError(
          getErrorMessage(
            alertsResult,
            "Clinical screening alerts could not be evaluated."
          )
        );
      }
    } catch (err) {
      setError(
        err.message ||
          "Could not connect to the backend. Check that the API is running."
      );
    } finally {
      setLoading(false);
    }
  }

  // Keep synchronized if URL or PatientContext changes
  useEffect(() => {
    const targetId = queryPatientId || selectedPatientId;
    if (targetId && targetId !== loadedPatientId && /^\d+$/.test(targetId) && Number(targetId) > 0) {
      setPatientId(targetId);
      loadTrendsById(targetId);
    }
  }, [queryPatientId, selectedPatientId]);

  function loadTrends(event) {
    event.preventDefault();
    loadTrendsById(patientId);
  }

  const measurements = Array.isArray(data?.measurements)
    ? data.measurements
    : [];

  const alerts = Array.isArray(alertData?.alerts) ? alertData.alerts : [];
  const insights = Array.isArray(insightData?.insights)
    ? insightData.insights
    : [];

  return (
    <main className="patient-workspace">
      <header className="workspace-header">
        <a className="back-button" href="/">
          ← Dashboard
        </a>

        <div className="header-actions-group">
          <span className="api-status">
            <span className="live-dot" />
            Clinical Trends
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

      <section className="workspace-intro">
        <span className="eyebrow">
          CARETRACK AI · LONGITUDINAL MONITORING
        </span>

        <h1>Clinical Trends</h1>

        <p>
          Review clinical measurements and changes recorded across patient
          visits.
        </p>
      </section>

      <PatientSelector onPatientChange={(newId) => loadTrendsById(newId)} />

      <section className="workspace-panel">
        <h2>Find patient measurements</h2>

        <form className="patient-search" onSubmit={loadTrends}>
          <label htmlFor="trends-patient-id">Patient ID</label>

          <div className="patient-search-row">
            <input
              id="trends-patient-id"
              type="number"
              min="1"
              step="1"
              required
              value={patientId}
              onChange={(event) => setPatientId(event.target.value)}
              placeholder="Enter patient ID"
            />

            <button type="submit" disabled={loading}>
              {loading ? "Loading..." : "Load Trends →"}
            </button>

            <button
              type="button"
              className="trends-action-btn"
              onClick={() => setMeasModalOpen(true)}
              disabled={!patientId}
              title="Record verified vitals and measurements"
            >
              <Activity size={15} />
              <span>Log Vitals</span>
            </button>
          </div>
        </form>
      </section>

      {error && (
        <p className="workspace-error" role="alert">
          {error}
        </p>
      )}

      {data && (
        <>
          <section className="patient-summary">
            <div>
              <span className="eyebrow">PATIENT PROFILE</span>
              <h2>{data.patient_name || `Patient ${data.patient_id}`}</h2>
              <p>Patient ID: {data.patient_id}</p>
            </div>

            <div className="summary-stat">
              <strong>{measurements.length}</strong>
              <span>Measurement entries</span>
            </div>
          </section>

          <section className="workspace-panel">
            <span className="eyebrow">CLINICAL REVIEW</span>
            <h2>Clinical Alerts</h2>

            <p className="panel-description">
              Review measurements that cross configured clinical screening
              thresholds. These alerts support clinical review and are not
              diagnoses.
            </p>

            {alertError && (
              <p className="workspace-error" role="alert">
                {alertError}
              </p>
            )}

            {!alertData && !alertError && <p>Loading clinical alerts...</p>}

            {alertData && (
              <>
                <div className="alert-summary">
                  <strong>
                    {alerts.length === 0
                      ? "No threshold alerts"
                      : `${alerts.length} alert(s) to review`}
                  </strong>

                  <p>
                    {alertData.summary ||
                      "Review available alerts with a clinician."}
                  </p>

                  {alertData.visit_date && (
                    <small>
                      Latest visit: {formatDate(alertData.visit_date)}
                    </small>
                  )}
                </div>

                {alerts.length > 0 ? (
                  <div className="clinical-alert-list">
                    {alerts.map((alert, index) => (
                      <ClinicalAlertCard
                        key={`${alert.metric || "alert"}-${index}`}
                        alert={alert}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="chart-empty">
                    No recorded values crossed the configured clinical screening
                    thresholds. This does not establish that the patient is
                    healthy.
                  </div>
                )}

                {alertData.disclaimer && (
                  <p className="clinical-disclaimer">
                    {alertData.disclaimer}
                  </p>
                )}
              </>
            )}
          </section>

          <section className="workspace-panel">
            <span className="eyebrow">LONGITUDINAL ANALYTICS</span>
            <h2>Clinical Trend Charts</h2>

            <p className="panel-description">
              Explore recorded values across visits. Charts show available
              measurements over time.
            </p>

            <div className="trend-chart-grid">
              {chartConfigs.map((config) => (
                <TrendChart
                  key={config.key}
                  config={config}
                  measurements={measurements}
                />
              ))}
            </div>
          </section>

          <section className="workspace-panel">
            <span className="eyebrow">MEASUREMENT COMPARISON</span>
            <h2>Longitudinal Insights</h2>

            <p className="panel-description">
              Compare measurements across visits when enough historical data is
              available.
            </p>

            {insightError && (
              <p className="workspace-error" role="alert">
                {insightError}
              </p>
            )}

            {!insightData && !insightError && (
              <p>Loading longitudinal insights...</p>
            )}

            {insightData && (
              <>
                <div className="insight-summary">
                  <span className="eyebrow">COMPARISON SUMMARY</span>

                  <p>
                    {insightData.summary ||
                      "No comparison summary is available."}
                  </p>

                  {insightData.previous_visit_date &&
                    insightData.current_visit_date && (
                      <p className="insight-date-range">
                        {formatDate(insightData.previous_visit_date)}
                        {" → "}
                        {formatDate(insightData.current_visit_date)}
                      </p>
                    )}
                </div>

                {insights.length > 0 ? (
                  <div className="insight-grid">
                    {insights.map((item, index) => (
                      <InsightCard
                        key={`${item.metric || "metric"}-${index}`}
                        item={item}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="chart-empty">
                    {insightData.summary ||
                      "More visits with recorded measurements are needed for comparison."}
                  </div>
                )}

                {insightData.disclaimer && (
                  <p className="clinical-disclaimer">
                    {insightData.disclaimer}
                  </p>
                )}
              </>
            )}
          </section>

          <section className="workspace-panel">
            <h2>Recorded Measurements</h2>

            {measurements.length === 0 ? (
              <p>
                No clinical measurements have been recorded for this patient.
              </p>
            ) : (
              measurements.map((item, index) => (
                <article
                  className="visit-card"
                  key={`${item.visit_id}-${index}`}
                >
                  <div className="visit-heading">
                    <div>
                      <span className="eyebrow">CLINICAL VISIT</span>
                      <h3>Visit #{item.visit_id}</h3>
                    </div>

                    <span className="visit-date">
                      {formatDate(item.visit_date)}
                    </span>
                  </div>

                  <div className="clinical-measurement-grid">
                    {fields.map((field) => {
                      const value = item[field.key];

                      return (
                        <div
                          className="clinical-measurement"
                          key={field.key}
                        >
                          <span>{field.label}</span>

                          <strong>
                            {value !== null && value !== undefined
                              ? `${value} ${field.unit}`
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
        </>
      )}

      <footer className="workspace-footer">
        CareTrack AI · Longitudinal Healthcare Platform
      </footer>

      <ClinicalMeasurementModal
        isOpen={measModalOpen}
        onClose={() => setMeasModalOpen(false)}
        initialPatientId={patientId}
        onMeasurementCreated={() => {
          loadTrendsById(patientId);
        }}
      />
    </main>
  );
}