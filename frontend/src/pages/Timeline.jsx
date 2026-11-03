import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CalendarPlus, Activity, FileDown, LogOut } from "lucide-react";
import { API_URL, authFetch } from "../config";
import { usePatient } from "../context/PatientContext";
import { useAuth } from "../context/AuthContext";
import PatientSelector from "../components/PatientSelector";
import VisitRegistrationModal from "../components/VisitRegistrationModal";
import ClinicalMeasurementModal from "../components/ClinicalMeasurementModal";
import FormattedClinicalText from "../components/ClinicalContentRenderer";

function formatDate(value) {
  if (!value) return "Date unavailable";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Date unavailable";
  }

  return date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatDateTime(value) {
  if (!value) return "Date unavailable";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Date unavailable";
  }

  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getErrorMessage(data, fallback) {
  if (typeof data?.detail === "string") {
    return data.detail;
  }

  if (Array.isArray(data?.detail)) {
    return data.detail.map((item) => item.msg).join(", ");
  }

  return fallback;
}

async function readResponse(response) {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  return {
    detail: await response.text(),
  };
}

function getVisitDate(visit) {
  return (
    visit.visit_date ||
    visit.date ||
    visit.created_at ||
    visit.visit_datetime ||
    null
  );
}

function getReports(visit) {
  if (Array.isArray(visit.reports)) {
    return visit.reports;
  }

  if (Array.isArray(visit.medical_reports)) {
    return visit.medical_reports;
  }

  return [];
}

function getMeasurements(visit) {
  if (Array.isArray(visit.measurements)) {
    return visit.measurements;
  }

  if (visit.measurements && typeof visit.measurements === "object") {
    return [visit.measurements];
  }

  if (Array.isArray(visit.clinical_measurements)) {
    return visit.clinical_measurements;
  }

  return [];
}

function MeasurementList({ measurements, visitDate }) {
  if (!measurements.length) {
    return (
      <p className="timeline-muted">
        No measurements are recorded for this visit.
      </p>
    );
  }

  const labels = {
    blood_pressure: ["Blood Pressure", "mmHg"],
    systolic_bp: ["Systolic BP", "mmHg"],
    diastolic_bp: ["Diastolic BP", "mmHg"],
    hemoglobin: ["Hemoglobin", "g/dL"],
    blood_glucose: ["Blood Glucose", "mg/dL"],
    heart_rate: ["Heart Rate", "bpm"],
    temperature: ["Temperature", "°C"],
    oxygen_saturation: ["Oxygen Saturation", "%"],
    weight: ["Weight", "kg"],
  };

  const primary = measurements[0];
  const revisions = measurements.slice(1);

  return (
    <div className="timeline-measurements-container">
      {/* Primary / Latest Reading */}
      <div className="timeline-measurement-card timeline-measurement-primary">
        <div className="timeline-measurement-card-header">
          <span className="timeline-reading-badge timeline-reading-badge-primary">
            {revisions.length > 0 ? "Latest Measurement (Active)" : "Measurement"}
          </span>
          <span className="timeline-timing-note">
            {primary.measured_at
              ? `Measured: ${formatDateTime(primary.measured_at)}`
              : `Visit Date: ${formatDate(visitDate)} (intra-day time unrecorded)`}
          </span>
        </div>

        <div className="timeline-measurement-grid">
          {Object.entries(labels).map(([key, [label, unit]]) => {
            const value = primary[key];

            if (value === null || value === undefined || value === "") {
              return null;
            }

            return (
              <div className="timeline-measurement-row" key={key}>
                <span>{label}</span>
                <strong>
                  {value}
                  {unit ? ` ${unit}` : ""}
                </strong>
              </div>
            );
          })}
        </div>
      </div>

      {/* Earlier Revision History */}
      {revisions.length > 0 && (
        <details className="timeline-revisions-details">
          <summary className="timeline-revisions-summary">
            View Revision History ({revisions.length} earlier reading{revisions.length > 1 ? "s" : ""})
          </summary>
          <div className="timeline-revisions-list">
            {revisions.map((rev, revIdx) => (
              <div
                className="timeline-measurement-card timeline-measurement-revision"
                key={rev.id ?? revIdx}
              >
                <div className="timeline-measurement-card-header">
                  <span className="timeline-reading-badge timeline-reading-badge-superseded">
                    Earlier Reading #{rev.id ?? revIdx + 1}
                  </span>
                  <span className="timeline-timing-note">
                    {rev.measured_at
                      ? `Measured: ${formatDateTime(rev.measured_at)}`
                      : rev.created_at
                        ? `Recorded: ${formatDateTime(rev.created_at)}`
                        : `Visit: ${formatDate(visitDate)}`}
                  </span>
                </div>

                <div className="timeline-measurement-grid">
                  {Object.entries(labels).map(([key, [label, unit]]) => {
                    const value = rev[key];

                    if (value === null || value === undefined || value === "") {
                      return null;
                    }

                    return (
                      <div className="timeline-measurement-row" key={key}>
                        <span>{label}</span>
                        <strong>
                          {value}
                          {unit ? ` ${unit}` : ""}
                        </strong>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function TimelineEntry({ visit, index }) {
  const reports = getReports(visit);
  const measurements = getMeasurements(visit);
  const visitDate = getVisitDate(visit);

  // Safe deduplication for display
  const uniqueReports = [];
  const seenReports = new Set();
  for (const r of reports) {
    const k = `${r.file_name || ""}_${(r.extracted_text || "").trim()}`;
    if (!seenReports.has(k)) {
      seenReports.add(k);
      uniqueReports.push(r);
    }
  }

  return (
    <article className="timeline-entry">
      <div className="timeline-marker" />

      <div className="timeline-entry-card">
        <div className="timeline-entry-header">
          <div>
            <span className="timeline-entry-label">
              VISIT {index + 1}
            </span>

            <h3>
              {visit.title ||
                visit.visit_type ||
                `Patient Visit #${visit.id ?? index + 1}`}
            </h3>
          </div>

          <span className="timeline-date">
            {formatDate(visitDate)}
          </span>
        </div>

        {visit.symptoms && (
          <div className="timeline-section">
            <h4>Symptoms</h4>
            <FormattedClinicalText text={visit.symptoms} />
          </div>
        )}

        {visit.clinical_notes && (
          <div className="timeline-section">
            <h4>Clinical Notes</h4>
            <FormattedClinicalText text={visit.clinical_notes} />
          </div>
        )}

        {visit.follow_up_notes && (
          <div className="timeline-section">
            <h4>Follow-up Notes</h4>
            <FormattedClinicalText text={visit.follow_up_notes} />
          </div>
        )}

        <div className="timeline-section">
          <h4>Clinical Measurements</h4>
          <MeasurementList measurements={measurements} visitDate={visitDate} />
        </div>

        <div className="timeline-section">
          <h4>Medical Reports</h4>

          {uniqueReports.length > 0 ? (
            <ul className="timeline-report-list">
              {uniqueReports.map((report, reportIndex) => (
                <li key={report.id ?? reportIndex}>
                  <strong>
                    {report.file_name ||
                      `Report #${report.id ?? reportIndex + 1}`}
                  </strong>

                  {report.file_type && (
                    <span>{report.file_type}</span>
                  )}

                  {report.extracted_text && (
                    <details>
                      <summary>View extracted text</summary>
                      <pre>{report.extracted_text}</pre>
                    </details>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="timeline-muted">
              No medical reports are recorded for this visit.
            </p>
          )}
        </div>
      </div>
    </article>
  );
}

export default function Timeline() {
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
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [visitModalOpen, setVisitModalOpen] = useState(false);
  const [measModalOpen, setMeasModalOpen] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  async function handleDownloadPdf() {
    const targetId = patientId || selectedPatientId;
    if (!targetId) return;

    setDownloadingPdf(true);
    try {
      const response = await authFetch(`${API_URL}/patients/${targetId}/pdf`);
      if (!response.ok) {
        throw new Error(`Failed to generate PDF (${response.status})`);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const code = timeline?.patient_code || targetId;
      a.download = `CareTrack_Patient_${code}_History.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      alert("Error generating patient PDF: " + (err.message || "Unknown error"));
    } finally {
      setDownloadingPdf(false);
    }
  }

  async function loadTimelineById(idToLoad) {
    const id = String(idToLoad).trim();

    if (!/^[1-9]\d*$/.test(id)) {
      setError("Enter a valid positive patient ID.");
      return;
    }

    setError("");
    setTimeline(null);
    setSearchParams({ patientId: id });
    setLoading(true);

    try {
      const response = await authFetch(
        `${API_URL}/patients/${id}/timeline`
      );

      const data = await readResponse(response);

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data, "Could not load the patient timeline.")
        );
      }

      setTimeline(data);
      setLoadedPatientId(id);
      selectPatient(id);
    } catch (err) {
      setError(
        err.message || "Could not connect to the backend."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const targetId = queryPatientId || selectedPatientId;
    if (targetId && targetId !== loadedPatientId && /^\d+$/.test(targetId) && Number(targetId) > 0) {
      setPatientId(targetId);
      loadTimelineById(targetId);
    }
  }, [queryPatientId, selectedPatientId]);

  function loadTimeline(event) {
    event.preventDefault();
    loadTimelineById(patientId);
  }

  const patient =
    timeline?.patient ||
    timeline?.patient_info ||
    timeline?.data?.patient ||
    null;

  const visits = Array.isArray(timeline?.visits)
    ? timeline.visits
    : Array.isArray(timeline?.timeline)
      ? timeline.timeline
      : Array.isArray(timeline?.data?.visits)
        ? timeline.data.visits
        : Array.isArray(timeline)
          ? timeline
          : [];

  const patientName =
    patient?.name ||
    timeline?.patient_name ||
    timeline?.name ||
    `Patient ${patientId}`;

  return (
    <main className="patient-workspace">
      <style>{`
        .timeline-search-row {
          display: flex;
          flex-wrap: wrap;
          gap: 12px;
          align-items: end;
        }

        .timeline-search-row .timeline-input-group {
          flex: 1;
          min-width: 200px;
        }

        .timeline-input-group label {
          display: block;
          margin-bottom: 8px;
        }

        .timeline-input-group input {
          width: 100%;
          box-sizing: border-box;
          padding: 12px;
          border: 1px solid #cbd5e1;
          border-radius: 10px;
        }

        .timeline-search-button {
          padding: 12px 18px;
          border: none;
          border-radius: 10px;
          background: #0f766e;
          color: white;
          font-weight: 600;
          cursor: pointer;
        }

        .timeline-search-button:disabled {
          opacity: .6;
          cursor: wait;
        }

        .timeline-action-button {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 12px 16px;
          border: 1px solid #0f766e;
          border-radius: 10px;
          background: #f0fdfa;
          color: #0f766e;
          font-size: .88rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .timeline-action-button:hover:not(:disabled) {
          background: #ccfbf1;
        }

        .timeline-action-button:disabled {
          opacity: .5;
          cursor: not-allowed;
        }

        .timeline-profile {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 16px;
          padding: 22px;
          border: 1px solid #dbe5ef;
          border-radius: 16px;
          margin-bottom: 24px;
        }

        .timeline-profile h2 {
          margin: 8px 0;
        }

        .timeline-profile p {
          margin: 6px 0;
          overflow-wrap: anywhere;
        }

        .timeline-muted {
          color: #64748b;
          font-size: .92rem;
        }

        .timeline-list {
          position: relative;
          padding-left: 28px;
        }

        .timeline-list::before {
          content: "";
          position: absolute;
          left: 7px;
          top: 12px;
          bottom: 12px;
          width: 2px;
          background: #cbd5e1;
        }

        .timeline-entry {
          position: relative;
          margin-bottom: 24px;
        }

        .timeline-marker {
          position: absolute;
          left: -27px;
          top: 22px;
          width: 14px;
          height: 14px;
          border-radius: 50%;
          background: #0f766e;
          border: 3px solid #ccfbf1;
          box-sizing: content-box;
        }

        .timeline-entry-card {
          padding: 20px;
          border: 1px solid #dbe5ef;
          border-radius: 16px;
          background: white;
          overflow-wrap: anywhere;
        }

        .timeline-entry-header {
          display: flex;
          flex-wrap: wrap;
          justify-content: space-between;
          gap: 12px;
          align-items: start;
        }

        .timeline-entry-header h3 {
          margin: 8px 0;
        }

        .timeline-entry-label {
          font-size: .75rem;
          font-weight: 700;
          letter-spacing: .08em;
          color: #0f766e;
        }

        .timeline-date {
          font-size: .88rem;
          color: #64748b;
        }

        .timeline-section {
          margin-top: 20px;
          padding-top: 14px;
          border-top: 1px solid #e2e8f0;
        }

        .timeline-section h4 {
          margin: 0 0 10px;
        }

        .timeline-section p {
          white-space: pre-wrap;
        }

        .timeline-measurements-container {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .timeline-measurement-card {
          padding: 14px;
          border-radius: 10px;
          background: #f8fafc;
          border: 1px solid #e2e8f0;
        }

        .timeline-measurement-primary {
          background: #f0fdfa;
          border: 1px solid #99f6e4;
        }

        .timeline-measurement-card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;
          margin-bottom: 10px;
          padding-bottom: 8px;
          border-bottom: 1px solid #e2e8f0;
        }

        .timeline-reading-badge {
          display: inline-block;
          font-size: .75rem;
          font-weight: 700;
          padding: 2px 8px;
          border-radius: 6px;
        }

        .timeline-reading-badge-primary {
          background: #ccfbf1;
          color: #0f766e;
        }

        .timeline-reading-badge-superseded {
          background: #f1f5f9;
          color: #64748b;
        }

        .timeline-timing-note {
          font-size: .80rem;
          color: #64748b;
        }

        .timeline-measurement-grid {
          display: grid;
          grid-template-columns: repeat(
            auto-fit,
            minmax(min(100%, 200px), 1fr)
          );
          gap: 10px;
        }

        .timeline-measurement-row {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          padding: 6px 0;
          border-bottom: 1px solid #e2e8f0;
        }

        .timeline-measurement-row:last-child {
          border-bottom: none;
        }

        .timeline-revisions-details {
          margin-top: 6px;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          padding: 8px 12px;
          background: #ffffff;
        }

        .timeline-revisions-summary {
          font-size: .85rem;
          font-weight: 600;
          color: #0f766e;
          cursor: pointer;
        }

        .timeline-revisions-list {
          margin-top: 10px;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .timeline-measurement-revision {
          background: #f8fafc;
          border: 1px solid #e2e8f0;
        }

        .timeline-report-list {
          padding-left: 20px;
        }

        .timeline-report-list li {
          margin: 10px 0;
        }

        .timeline-report-list li > span {
          display: block;
          margin-top: 4px;
          color: #64748b;
          font-size: .85rem;
        }

        .timeline-report-list details {
          margin-top: 8px;
        }

        .timeline-report-list pre {
          white-space: pre-wrap;
          overflow-wrap: anywhere;
          padding: 12px;
          background: #f8fafc;
          border-radius: 8px;
          max-height: 260px;
          overflow: auto;
        }

        @media (max-width: 600px) {
          .timeline-entry-card {
            padding: 14px;
          }

          .timeline-measurement-row {
            flex-direction: column;
            gap: 4px;
          }
        }
      `}</style>

      <header className="workspace-header">
        <a className="back-button" href="/">
          ← Dashboard
        </a>

        <div className="header-actions-group">
          <span className="api-status">
            <span className="live-dot" />
            CareTrack AI
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
          CARETRACK AI · LONGITUDINAL RECORDS
        </span>

        <h1>Patient Timeline</h1>

        <p>
          Review patient history, clinical measurements and medical reports
          recorded across visits.
        </p>
      </section>

      <PatientSelector onPatientChange={loadTimelineById} />

      <section className="workspace-panel">
        <h2>Find Patient History</h2>

        <form onSubmit={loadTimeline}>
          <div className="timeline-search-row">
            <div className="timeline-input-group">
              <label htmlFor="timeline-patient-id">
                Patient ID
              </label>

              <input
                id="timeline-patient-id"
                type="number"
                min="1"
                step="1"
                required
                value={patientId}
                onChange={(event) => setPatientId(event.target.value)}
                placeholder="Enter patient ID"
              />
            </div>

            <button
              className="timeline-search-button"
              type="submit"
              disabled={loading}
            >
              {loading ? "Loading..." : "Load Timeline"}
            </button>

            <button
              type="button"
              className="timeline-action-button"
              onClick={() => setVisitModalOpen(true)}
              disabled={!patientId}
              title="Record a new visit for this patient"
            >
              <CalendarPlus size={15} />
              <span>Record Visit</span>
            </button>

            <button
              type="button"
              className="timeline-action-button"
              onClick={() => setMeasModalOpen(true)}
              disabled={!patientId}
              title="Log vitals/measurements for this patient"
            >
              <Activity size={15} />
              <span>Log Vitals</span>
            </button>

            <button
              type="button"
              className="timeline-action-button"
              onClick={handleDownloadPdf}
              disabled={!patientId || downloadingPdf}
              title="Export complete patient history as PDF"
            >
              <FileDown size={15} />
              <span>{downloadingPdf ? "Generating..." : "Export PDF"}</span>
            </button>
          </div>
        </form>
      </section>

      {error && (
        <p className="workspace-error" role="alert">
          {error}
        </p>
      )}

      {timeline && (
        <>
          <section className="timeline-profile">
            <div>
              <span className="eyebrow">PATIENT PROFILE</span>
              <h2>{patientName}</h2>

              <p>
                Patient ID:{" "}
                {patient?.id ?? timeline?.patient_id ?? patientId}
              </p>

              <p>
                Age: {timeline?.age ?? patient?.age ?? "Not recorded"}
                {" · "}
                Gender:{" "}
                {timeline?.gender ?? patient?.gender ?? "Not recorded"}
              </p>

              <p>
                Location:{" "}
                {timeline?.location ?? patient?.location ?? "Not recorded"}
              </p>

              <p>
                Phone:{" "}
                {timeline?.phone ?? patient?.phone ?? "Not recorded"}
              </p>
            </div>

            <div>
              <strong>{visits.length}</strong>
              <p className="timeline-muted">
                Timeline entries returned
              </p>
            </div>
          </section>

          <section className="workspace-panel">
            <h2>Medical History</h2>

            {visits.length === 0 ? (
              <p className="timeline-muted">
                No visit entries were returned for this patient.
              </p>
            ) : (
              <div className="timeline-list">
                {visits.map((visit, index) => (
                  <TimelineEntry
                    key={visit.id ?? visit.visit_id ?? index}
                    visit={visit}
                    index={index}
                  />
                ))}
              </div>
            )}

            <p className="clinical-disclaimer">
              This timeline presents available records for review. Missing
              information does not necessarily mean a measurement or report
              was absent from the patient's real-world care. This tool does
              not replace clinical judgment.
            </p>
          </section>
        </>
      )}

      <footer className="workspace-footer">
        CareTrack AI · Longitudinal Healthcare Platform
      </footer>

      <VisitRegistrationModal
        isOpen={visitModalOpen}
        onClose={() => setVisitModalOpen(false)}
        initialPatientId={patientId}
        onVisitCreated={() => {
          loadTimelineById(patientId);
        }}
      />

      <ClinicalMeasurementModal
        isOpen={measModalOpen}
        onClose={() => setMeasModalOpen(false)}
        initialPatientId={patientId}
        onMeasurementCreated={() => {
          loadTimelineById(patientId);
        }}
      />
    </main>
  );
}