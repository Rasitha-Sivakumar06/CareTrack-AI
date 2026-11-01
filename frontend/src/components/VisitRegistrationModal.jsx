import { useState } from "react";
import { CalendarPlus, X, AlertCircle, CheckCircle2 } from "lucide-react";
import { API_URL, authFetch } from "../config";
import { usePatient } from "../context/PatientContext";

function getTodayString() {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export default function VisitRegistrationModal({
  isOpen,
  onClose,
  initialPatientId = null,
  onVisitCreated,
}) {
  const { patients, selectedPatientId } = usePatient();

  const effectivePatientId = String(initialPatientId || selectedPatientId || "");

  const [patientId, setPatientId] = useState(effectivePatientId);
  const [visitDate, setVisitDate] = useState(getTodayString);
  const [symptoms, setSymptoms] = useState("");
  const [clinicalNotes, setClinicalNotes] = useState("");
  const [followUpNotes, setFollowUpNotes] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  if (!isOpen) return null;

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSuccessMessage("");

    const parsedPatientId = Number(patientId || effectivePatientId);
    if (!Number.isInteger(parsedPatientId) || parsedPatientId < 1) {
      setError("Please select a valid patient for this visit.");
      return;
    }

    if (!visitDate) {
      setError("Visit date is required.");
      return;
    }

    setSubmitting(true);

    try {
      const payload = {
        patient_id: parsedPatientId,
        visit_date: visitDate,
        symptoms: symptoms.trim() || null,
        clinical_notes: clinicalNotes.trim() || null,
        follow_up_notes: followUpNotes.trim() || null,
      };

      const response = await authFetch(`${API_URL}/visits/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error(data.detail || "Patient not found. Select a registered patient.");
        }
        if (response.status === 422) {
          const detail = Array.isArray(data.detail)
            ? data.detail.map((d) => d.msg || "Invalid input").join(", ")
            : data.detail || "Validation error.";
          throw new Error(detail);
        }
        throw new Error(data.detail || `Failed to create visit (${response.status}).`);
      }

      setSuccessMessage(`Visit #${data.id} recorded successfully!`);

      if (onVisitCreated) {
        onVisitCreated(data);
      }

      // Reset optional fields
      setSymptoms("");
      setClinicalNotes("");
      setFollowUpNotes("");

      setTimeout(() => {
        onClose();
        setSuccessMessage("");
      }, 1000);
    } catch (err) {
      setError(err.message || "Failed to record visit. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <span className="modal-icon">
              <CalendarPlus size={20} />
            </span>
            <div>
              <h3>Record New Patient Visit</h3>
              <p>Log a clinical encounter, symptoms, and consultation notes.</p>
            </div>
          </div>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {error && (
          <div className="modal-alert modal-alert-error" role="alert">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {successMessage && (
          <div className="modal-alert modal-alert-success" role="status">
            <CheckCircle2 size={16} />
            <span>{successMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="visit_patient_id">
                Patient <span className="req">*</span>
              </label>
              <select
                id="visit_patient_id"
                value={patientId || effectivePatientId}
                onChange={(e) => setPatientId(e.target.value)}
                required
              >
                <option value="">-- Select Patient --</option>
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.patient_code}) — ID #{p.id}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="visit_date">
                Visit Date <span className="req">*</span>
              </label>
              <input
                id="visit_date"
                type="date"
                required
                value={visitDate}
                onChange={(e) => setVisitDate(e.target.value)}
              />
            </div>

            <div className="form-group full-width">
              <label htmlFor="symptoms">Reported Symptoms</label>
              <textarea
                id="symptoms"
                rows={2}
                placeholder="e.g. Mild headache, dizziness, persistent cough..."
                value={symptoms}
                onChange={(e) => setSymptoms(e.target.value)}
              />
            </div>

            <div className="form-group full-width">
              <label htmlFor="clinical_notes">Clinical Notes</label>
              <textarea
                id="clinical_notes"
                rows={3}
                placeholder="e.g. Patient presents with elevated BP; prescribed lifestyle modifications..."
                value={clinicalNotes}
                onChange={(e) => setClinicalNotes(e.target.value)}
              />
            </div>

            <div className="form-group full-width">
              <label htmlFor="follow_up_notes">Follow-up Instructions</label>
              <textarea
                id="follow_up_notes"
                rows={2}
                placeholder="e.g. Schedule follow-up visit in 2 weeks for BP check..."
                value={followUpNotes}
                onChange={(e) => setFollowUpNotes(e.target.value)}
              />
            </div>
          </div>

          <div className="modal-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={submitting}
            >
              {submitting ? "Saving Visit..." : "Record Visit"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
