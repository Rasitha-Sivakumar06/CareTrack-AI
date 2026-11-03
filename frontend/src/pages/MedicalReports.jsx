import { useEffect, useRef, useState } from "react";
import { LogOut } from "lucide-react";
import "./MedicalReports.css";
import { API_URL, authFetch, authDownloadBlob } from "../config";
import { usePatient } from "../context/PatientContext";
import { useAuth } from "../context/AuthContext";
import PatientSelector from "../components/PatientSelector";
import VisitRegistrationModal from "../components/VisitRegistrationModal";
import { decodeHtmlEntities } from "../utils/clinicalFormatters";

const MAX_FILE_SIZE = 10 * 1024 * 1024;

const ALLOWED_EXTENSIONS = [
  ".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff",
];

const MEASUREMENT_LABELS = {
  blood_pressure: "Blood Pressure",
  systolic_bp: "Systolic BP",
  diastolic_bp: "Diastolic BP",
  hemoglobin: "Hemoglobin",
  blood_glucose: "Blood Glucose",
  heart_rate: "Heart Rate",
  temperature: "Temperature",
  oxygen_saturation: "Oxygen Saturation",
  weight: "Weight",
};

const MEASUREMENT_UNITS = {
  blood_pressure: "mmHg",
  systolic_bp: "mmHg",
  diastolic_bp: "mmHg",
  hemoglobin: "g/dL",
  blood_glucose: "mg/dL",
  heart_rate: "bpm",
  temperature: "°C",
  oxygen_saturation: "%",
  weight: "kg",
};

function getErrorMessage(data, fallback) {
  if (typeof data?.detail === "string") return data.detail;

  if (Array.isArray(data?.detail)) {
    return data.detail.map((item) => item.msg || "Invalid input").join(", ");
  }

  return fallback;
}

async function readResponse(response) {
  const type = response.headers.get("content-type") || "";

  if (type.includes("application/json")) return response.json();

  return {
    detail: (await response.text()) || "Unexpected server response.",
  };
}

function getFileExtension(name) {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index).toLowerCase() : "";
}

function formatDate(value) {
  if (!value) return "Date unavailable";

  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleDateString();
}

function patientName(patient) {
  return patient.name || patient.full_name || `Patient ${patient.id}`;
}

function patientIdentifier(patient) {
  return patient.patient_code || patient.patient_id || `ID ${patient.id}`;
}

function visitDate(visit) {
  return formatDate(visit.visit_date || visit.created_at);
}

function getMeasurements(measurements) {
  if (!measurements || typeof measurements !== "object") return [];

  return Object.entries(MEASUREMENT_LABELS)
    .filter(([key]) => {
      const value = measurements[key];
      return value !== null && value !== undefined && value !== "";
    })
    .map(([key, label]) => ({
      key,
      label,
      value: measurements[key],
      unit: MEASUREMENT_UNITS[key] || "",
    }));
}

function MeasurementResults({ measurements }) {
  const items = getMeasurements(measurements);

  return (
    <div className="extracted-measurements">
      <h3>Extracted Clinical Measurements</h3>

      <p className="panel-description">
        Check every value against the original document before confirming.
        Extracted values may be incomplete or incorrect.
      </p>

      {items.length > 0 ? (
        <div className="measurement-grid">
          {items.map((item) => (
            <article className="measurement-card" key={item.key}>
              <span className="measurement-label">{item.label}</span>
              <strong className="measurement-value">
                {String(item.value)}
                {item.unit ? ` ${item.unit}` : ""}
              </strong>
            </article>
          ))}
        </div>
      ) : (
        <div className="report-status report-status-warning">
          <strong>No structured measurements found</strong>
          <p>Review the original report manually.</p>
        </div>
      )}

      <p className="clinical-disclaimer">
        These values support clinical review and are not a diagnosis.
      </p>
    </div>
  );
}

function ReportDetails({ report, patientId }) {
  return (
    <>
      <div className="report-result-row">
        <span>Report ID</span>
        <strong>{report.id ?? "Unavailable"}</strong>
      </div>

      <div className="report-result-row">
        <span>Visit ID</span>
        <strong>{report.visit_id ?? "Unavailable"}</strong>
      </div>

      <div className="report-result-row">
        <span>Filename</span>
        <strong>{report.file_name || "Unavailable"}</strong>
      </div>

      {report.id && patientId && (
        <div className="report-result-row">
          <span>Original Document</span>
          <button
            type="button"
            className="report-download-link"
            style={{ background: "none", border: "none", cursor: "pointer", textDecoration: "underline", color: "inherit", font: "inherit", padding: 0 }}
            onClick={() =>
              authDownloadBlob(
                `${API_URL}/medical-reports/${report.id}/file?patient_id=${encodeURIComponent(patientId)}`,
                report.file_name || `Medical_Report_${report.id}.pdf`
              ).catch((err) => alert(err.message || "Failed to download original document."))
            }
            title="Download verified original medical report"
          >
            📄 View / Download File
          </button>
        </div>
      )}

      <h4>Extracted text</h4>

      {report.extracted_text?.trim() ? (
        <pre className="report-extracted-text">
          {decodeHtmlEntities(report.extracted_text)}
        </pre>
      ) : (
        <p className="panel-description">
          No readable text was extracted. Review the original document.
        </p>
      )}
    </>
  );
}

export default function MedicalReports() {
  const fileInputRef = useRef(null);
  const { user, logout } = useAuth();

  const {
    patients,
    selectedPatientId,
    selectPatient,
    loading: patientsLoading,
  } = usePatient();

  const [patientId, setPatientId] = useState(() => selectedPatientId || "");
  const [visits, setVisits] = useState([]);
  const [visitId, setVisitId] = useState("");

  const [visitsLoading, setVisitsLoading] = useState(false);

  const [file, setFile] = useState(null);
  const [verified, setVerified] = useState(false);

  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [report, setReport] = useState(null);

  const [historyVisitId, setHistoryVisitId] = useState("");
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [historySearched, setHistorySearched] = useState(false);
  const [visitModalOpen, setVisitModalOpen] = useState(false);

  useEffect(() => {
    if (selectedPatientId && selectedPatientId !== patientId) {
      setPatientId(selectedPatientId);
      setVisits([]);
      setVisitId("");
      setFile(null);
      setReport(null);
      setConfirmed(false);
      setVerified(false);
      setNotice("");
      setError("");
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }, [selectedPatientId, patientId]);

  useEffect(() => {
    let active = true;

    async function loadVisits() {
      setVisits([]);
      setVisitId("");
      setVerified(false);

      if (!patientId) return;

      setVisitsLoading(true);

      try {
        const response = await authFetch(
          `${API_URL}/visits/patient/${encodeURIComponent(patientId)}`
        );
        const data = await readResponse(response);

        if (!response.ok) {
          throw new Error(getErrorMessage(data, "Could not load visits."));
        }

        if (active) setVisits(Array.isArray(data) ? data : []);
      } catch (err) {
        if (active) setError(err.message || "Could not load visits.");
      } finally {
        if (active) setVisitsLoading(false);
      }
    }

    loadVisits();

    return () => {
      active = false;
    };
  }, [patientId]);

  function resetReview() {
    setReport(null);
    setConfirmed(false);
    setVerified(false);
    setNotice("");
    setError("");
  }

  function handlePatientChange(value) {
    setPatientId(value);
    if (value) {
      selectPatient(value);
    }
    setVisits([]);
    setVisitId("");
    setFile(null);
    resetReview();

    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleVisitChange(value) {
    setVisitId(value);
    setFile(null);
    resetReview();

    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function loadReportHistory(id) {
    setHistoryError("");
    setHistory([]);
    setHistorySearched(false);

    const cleanId = String(id).trim();

    if (!/^\d+$/.test(cleanId) || Number(cleanId) < 1) {
      setHistoryError("Enter a valid positive numeric visit ID.");
      return;
    }

    setHistoryLoading(true);

    try {
      const response = await authFetch(
        `${API_URL}/medical-reports/visit/${cleanId}`
      );
      const data = await readResponse(response);

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data, "Could not retrieve report history.")
        );
      }

      setHistory(Array.isArray(data) ? data : []);
      setHistorySearched(true);
    } catch (err) {
      setHistoryError(err.message || "Could not connect to the backend.");
    } finally {
      setHistoryLoading(false);
    }
  }

  async function handleUpload(event) {
    event.preventDefault();
    setError("");
    setNotice("");

    if (!patientId || !visitId) {
      setError("Select both a patient and a visit.");
      return;
    }

    const selectedVisit = visits.find(
      (visit) => String(visit.id) === String(visitId)
    );

    if (!selectedVisit || String(selectedVisit.patient_id) !== String(patientId)) {
      setError("The selected visit does not belong to this patient. Select it again.");
      return;
    }

    if (!verified) {
      setError("Confirm that the selected patient and visit match the report.");
      return;
    }

    if (!file) {
      setError("Select a medical report file.");
      return;
    }

    if (!ALLOWED_EXTENSIONS.includes(getFileExtension(file.name))) {
      setError("Choose a PDF, JPEG, PNG, BMP, or TIFF file.");
      return;
    }

    if (file.size === 0 || file.size > MAX_FILE_SIZE) {
      setError("The file must be greater than 0 bytes and no larger than 10 MB.");
      return;
    }

    const data = new FormData();
    data.append("patient_id", patientId);
    data.append("visit_id", visitId);
    data.append("file", file);

    setLoading(true);
    setReport(null);
    setConfirmed(false);

    try {
      const response = await authFetch(`${API_URL}/medical-reports/upload`, {
        method: "POST",
        body: data,
      });
      const result = await readResponse(response);

      if (!response.ok) {
        throw new Error(getErrorMessage(result, "Could not upload the report."));
      }

      setReport(result);
      setFile(null);
      setNotice("Report uploaded. Review the extracted information below.");

      if (fileInputRef.current) fileInputRef.current.value = "";

      await loadReportHistory(visitId);
    } catch (err) {
      setError(err.message || "Could not connect to the backend.");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirmMeasurements() {
    if (!report?.id || !patientId || !visitId) {
      setError("Missing report, patient, or visit information.");
      return;
    }

    if (!verified) {
      setError("Verify the patient and visit before confirming.");
      return;
    }

    if (getMeasurements(report.extracted_measurements).length === 0) {
      setError("There are no extracted measurements to confirm.");
      return;
    }

    const accepted = window.confirm(
      "Have you checked these values against the original document and confirmed the patient and visit? Only proceed if they match."
    );

    if (!accepted) return;

    setConfirming(true);
    setError("");
    setNotice("");

    try {
      const response = await authFetch(
        `${API_URL}/medical-reports/${report.id}/confirm-measurements`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            patient_id: Number(patientId),
            visit_id: Number(visitId),
          }),
        }
      );

      const data = await readResponse(response);

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data, "Could not confirm measurements.")
        );
      }

      setConfirmed(true);
      setNotice(data.message || "Measurements saved for clinical review.");
      await loadReportHistory(visitId);
    } catch (err) {
      setError(err.message || "Could not confirm measurements.");
    } finally {
      setConfirming(false);
    }
  }

  async function handleHistorySearch(event) {
    event.preventDefault();
    await loadReportHistory(historyVisitId);
  }

  const selectedPatient = patients.find(
    (patient) => String(patient.id) === String(patientId)
  );

  const selectedVisit = visits.find(
    (visit) => String(visit.id) === String(visitId)
  );

  return (
    <main className="patient-workspace">
      <header className="workspace-header">
        <a className="back-button" href="/">← Dashboard</a>
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
        <span className="eyebrow">CARETRACK AI · MEDICAL DOCUMENTS</span>
        <h1>Medical Reports</h1>
        <p>
          Link reports to the correct patient and visit, review extracted
          measurements, and explicitly confirm values before saving them.
        </p>
      </section>
      <PatientSelector onPatientChange={handlePatientChange} />

      <section className="workspace-panel">
        <h2>1. Select patient and visit</h2>
        <p className="panel-description">
          A report must be linked to a visit belonging to the selected patient.
        </p>

        <div className="report-form-group">
          <label htmlFor="patient-select">Patient</label>
          <select
            id="patient-select"
            value={patientId}
            onChange={(event) => handlePatientChange(event.target.value)}
            disabled={patientsLoading || loading || confirming}
          >
            <option value="">
              {patientsLoading ? "Loading patients..." : "Select a patient"}
            </option>
            {patients.map((patient) => (
              <option key={patient.id} value={patient.id}>
                {patientName(patient)} — {patientIdentifier(patient)}
              </option>
            ))}
          </select>
        </div>

        <div className="report-form-group">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <label htmlFor="visit-select" style={{ margin: 0 }}>Patient visit</label>
            <button
              type="button"
              className="add-visit-inline-btn"
              onClick={() => setVisitModalOpen(true)}
              disabled={!patientId || loading || confirming}
              title="Record a new visit for this patient"
            >
              + Record New Visit
            </button>
          </div>
          <select
            id="visit-select"
            value={visitId}
            onChange={(event) => handleVisitChange(event.target.value)}
            disabled={!patientId || visitsLoading || loading || confirming}
          >
            <option value="">
              {!patientId
                ? "Select a patient first"
                : visitsLoading
                  ? "Loading visits..."
                  : visits.length
                    ? "Select a visit"
                    : "No visits found for this patient"}
            </option>
            {visits.map((visit) => (
              <option key={visit.id} value={visit.id}>
                Visit {visit.id} — {visitDate(visit)}
              </option>
            ))}
          </select>
        </div>

        {selectedPatient && selectedVisit && (
          <div className="report-status report-status-success">
            <strong>Selected record</strong>
            <p>
              Patient: {patientName(selectedPatient)} (
              {patientIdentifier(selectedPatient)})
            </p>
            <p>
              Visit: {selectedVisit.id} — {visitDate(selectedVisit)}
            </p>
          </div>
        )}
      </section>

      <section className="workspace-panel">
        <h2>2. Upload report</h2>
        <p className="panel-description">
          Supported formats: PDF, JPEG, PNG, BMP, TIFF. Maximum size: 10 MB.
        </p>

        <form onSubmit={handleUpload}>
          <div className="report-form-group">
            <label htmlFor="medical-file">Medical report file</label>
            <input
              ref={fileInputRef}
              id="medical-file"
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,.bmp,.tif,.tiff"
              disabled={!patientId || !visitId || loading || confirming}
              onChange={(event) => {
                setFile(event.target.files?.[0] || null);
                resetReview();
              }}
            />
          </div>

          {file && (
            <div className="report-selected-file">
              <strong>{file.name}</strong>
              <span>{(file.size / 1024).toFixed(1)} KB</span>
            </div>
          )}

          <div className="report-form-group">
            <label>
              <input
                type="checkbox"
                checked={verified}
                onChange={(event) => setVerified(event.target.checked)}
                disabled={!patientId || !visitId || loading || confirming}
              />{" "}
              I verified that this report belongs to the selected patient and visit.
            </label>
          </div>

          {error && <p className="workspace-error" role="alert">{error}</p>}
          {notice && <p className="report-notice" role="status">{notice}</p>}

          <button
            className="workspace-primary-button"
            type="submit"
            disabled={loading || confirming || !patientId || !visitId}
          >
            {loading ? "Uploading and extracting..." : "Upload and Extract"}
          </button>
        </form>
      </section>

      {report && (
        <section className="workspace-panel">
          <h2>3. Review extracted information</h2>
          <ReportDetails report={report} patientId={patientId} />
          <MeasurementResults measurements={report.extracted_measurements} />

          {getMeasurements(report.extracted_measurements).length > 0 && (
            <div className="report-confirmation">
              <p className="panel-description">
                Confirm only after comparing every extracted value with the
                original document. The current endpoint re-extracts values
                from stored report text; it does not save edits made in the UI.
              </p>

              <button
                className="workspace-primary-button"
                type="button"
                onClick={handleConfirmMeasurements}
                disabled={confirming || confirmed}
              >
                {confirming
                  ? "Saving measurements..."
                  : confirmed
                    ? "Measurements Confirmed"
                    : "Confirm and Save Measurements"}
              </button>
            </div>
          )}
        </section>
      )}

      <section className="workspace-panel">
        <h2>Report history</h2>
        <p className="panel-description">
          Retrieve the reports associated with a visit.
        </p>

        <form onSubmit={handleHistorySearch}>
          <div className="report-form-group">
            <label htmlFor="history-visit-id">Visit ID</label>
            <input
              id="history-visit-id"
              type="number"
              min="1"
              step="1"
              required
              value={historyVisitId}
              onChange={(event) => setHistoryVisitId(event.target.value)}
              placeholder="Enter visit ID"
            />
          </div>

          {historyError && (
            <p className="workspace-error" role="alert">{historyError}</p>
          )}

          <button
            className="workspace-primary-button"
            type="submit"
            disabled={historyLoading}
          >
            {historyLoading ? "Searching..." : "View Report History"}
          </button>
        </form>

        {historySearched && history.length === 0 && (
          <p className="panel-description">No reports found for this visit.</p>
        )}

        {historySearched && history.length > 0 && (
          <div className="report-history-list">
            <h3>Reports found: {history.length}</h3>
            {history.map((item) => (
              <article className="report-history-item" key={item.id}>
                <ReportDetails
                  report={item}
                  patientId={patientId || (selectedPatient ? selectedPatient.id : null)}
                />
                <MeasurementResults
                  measurements={item.extracted_measurements}
                />
              </article>
            ))}
          </div>
        )}
      </section>

      <footer className="workspace-footer">
        CareTrack AI · Longitudinal Healthcare Platform
      </footer>

      <VisitRegistrationModal
        isOpen={visitModalOpen}
        onClose={() => setVisitModalOpen(false)}
        initialPatientId={patientId}
        onVisitCreated={(newVisit) => {
          setVisits((prev) => [newVisit, ...prev]);
          setVisitId(String(newVisit.id));
          setNotice(`Visit #${newVisit.id} recorded and selected.`);
        }}
      />
    </main>
  );
}
