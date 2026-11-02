import { useState } from "react";
import { User, UserPlus, AlertCircle, RefreshCw, FileDown } from "lucide-react";
import { API_URL, authFetch } from "../config";
import { usePatient } from "../context/PatientContext";
import PatientRegistrationModal from "./PatientRegistrationModal";

export default function PatientSelector({ onPatientChange, compact = false, showPdf = false }) {
  const {
    patients,
    selectedPatientId,
    selectedPatient,
    invalidPatientId,
    loadingPatients,
    patientError,
    selectPatient,
    refreshPatients,
  } = usePatient();

  const [modalOpen, setModalOpen] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  async function handleDownloadPdf() {
    if (!selectedPatientId) return;
    setDownloadingPdf(true);
    try {
      const response = await authFetch(`${API_URL}/patients/${selectedPatientId}/pdf`);
      if (!response.ok) {
        throw new Error(`Failed to generate PDF (${response.status})`);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const code = selectedPatient?.patient_code || selectedPatientId;
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

  function handleSelect(e) {
    const newId = e.target.value;
    selectPatient(newId);
    if (onPatientChange) {
      onPatientChange(newId);
    }
  }

  return (
    <div className={`patient-selector-container ${compact ? "compact" : ""}`}>
      {invalidPatientId && (
        <div className="selector-warning-banner" role="alert">
          <AlertCircle size={15} />
          <span>
            Patient ID <strong>#{invalidPatientId}</strong> does not exist in the database. Please select a valid patient below.
          </span>
        </div>
      )}

      {patientError && (
        <div className="selector-warning-banner error" role="alert">
          <AlertCircle size={15} />
          <span>{patientError}</span>
          <button
            type="button"
            className="retry-btn"
            onClick={() => refreshPatients()}
            title="Retry loading roster"
          >
            <RefreshCw size={12} />
          </button>
        </div>
      )}

      <div className="patient-selector-bar">
        <div className="selector-left">
          <span className="selector-label">
            <User size={15} />
            <span>Active Patient:</span>
          </span>

          <select
            className="patient-dropdown"
            value={selectedPatientId}
            onChange={handleSelect}
            disabled={loadingPatients || patients.length === 0}
            aria-label="Select active patient"
          >
            {patients.length === 0 && !loadingPatients && (
              <option value="">No patients registered yet</option>
            )}
            {loadingPatients && <option value="">Loading patient roster...</option>}
            {!loadingPatients && patients.length > 0 && !selectedPatientId && (
              <option value="">-- Select a patient --</option>
            )}
            {patients.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.patient_code}) — ID #{p.id}
              </option>
            ))}
          </select>

          {selectedPatient && !compact && (
            <span className="patient-quick-badge">
              {selectedPatient.gender ? `${selectedPatient.gender}, ` : ""}
              {selectedPatient.age !== null && selectedPatient.age !== undefined
                ? `${selectedPatient.age} yrs`
                : ""}
              {selectedPatient.location ? ` · ${selectedPatient.location}` : ""}
            </span>
          )}
        </div>

        <div className="selector-right">
          {showPdf && selectedPatientId && (
            <button
              type="button"
              className="download-pdf-btn"
              onClick={handleDownloadPdf}
              disabled={downloadingPdf}
              title="Download patient longitudinal history PDF"
            >
              <FileDown size={15} />
              <span>{downloadingPdf ? "Generating..." : "Download PDF"}</span>
            </button>
          )}

          <button
            type="button"
            className="register-patient-btn"
            onClick={() => setModalOpen(true)}
            title="Register a new patient"
          >
            <UserPlus size={15} />
            <span>Register Patient</span>
          </button>
        </div>
      </div>

      <PatientRegistrationModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </div>
  );
}
