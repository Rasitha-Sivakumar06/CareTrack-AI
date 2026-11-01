import { useState, useEffect } from "react";
import { Activity, X, AlertCircle, CheckCircle2 } from "lucide-react";
import { API_URL, authFetch } from "../config";
import { usePatient } from "../context/PatientContext";

export default function ClinicalMeasurementModal({
  isOpen,
  onClose,
  initialPatientId = null,
  initialVisitId = null,
  onMeasurementCreated,
}) {
  const { patients, selectedPatientId } = usePatient();

  const effectivePatientId = String(initialPatientId || selectedPatientId || "");

  const [patientId, setPatientId] = useState(effectivePatientId);
  const [visits, setVisits] = useState([]);
  const [visitId, setVisitId] = useState(initialVisitId ? String(initialVisitId) : "");
  const [loadingVisits, setLoadingVisits] = useState(false);

  // Clinical measurements state
  const [formData, setFormData] = useState({
    systolic_bp: "",
    diastolic_bp: "",
    blood_glucose: "",
    heart_rate: "",
    temperature: "",
    oxygen_saturation: "",
    hemoglobin: "",
    weight: "",
    measured_at: "",
  });

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  // Load visits whenever selected patient changes
  useEffect(() => {
    let active = true;
    const currentId = patientId || effectivePatientId;

    if (!currentId || !isOpen) {
      setVisits([]);
      return;
    }

    async function loadVisits() {
      setLoadingVisits(true);
      try {
        const response = await authFetch(`${API_URL}/visits/patient/${encodeURIComponent(currentId)}`);
        if (response.ok) {
          const list = await response.json();
          if (active) {
            setVisits(Array.isArray(list) ? list : []);
            if (list.length > 0 && !visitId) {
              setVisitId(String(list[0].id));
            }
          }
        }
      } catch {
        if (active) setVisits([]);
      } finally {
        if (active) setLoadingVisits(false);
      }
    }

    loadVisits();

    return () => {
      active = false;
    };
  }, [patientId, effectivePatientId, isOpen]);

  if (!isOpen) return null;

  function handleFieldChange(field, value) {
    setError("");
    setFormData((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSuccessMessage("");

    const parsedPatientId = Number(patientId || effectivePatientId);
    if (!Number.isInteger(parsedPatientId) || parsedPatientId < 1) {
      setError("Please select a valid patient.");
      return;
    }

    const parsedVisitId = Number(visitId);
    if (!Number.isInteger(parsedVisitId) || parsedVisitId < 1) {
      setError("Please select a valid visit for this measurement.");
      return;
    }

    // Build measurements payload
    const payload = {
      patient_id: parsedPatientId,
      visit_id: parsedVisitId,
    };

    if (formData.measured_at) {
      payload.measured_at = new Date(formData.measured_at).toISOString();
    }

    let enteredCount = 0;

    // Validate and parse systolic BP (0-300)
    if (formData.systolic_bp !== "") {
      const val = Number(formData.systolic_bp);
      if (!Number.isInteger(val) || val < 0 || val > 300) {
        setError("Systolic BP must be an integer between 0 and 300 mmHg.");
        return;
      }
      payload.systolic_bp = val;
      enteredCount++;
    }

    // Validate and parse diastolic BP (0-200)
    if (formData.diastolic_bp !== "") {
      const val = Number(formData.diastolic_bp);
      if (!Number.isInteger(val) || val < 0 || val > 200) {
        setError("Diastolic BP must be an integer between 0 and 200 mmHg.");
        return;
      }
      payload.diastolic_bp = val;
      enteredCount++;
    }

    // If both systolic and diastolic provided, construct standard blood_pressure string
    if (payload.systolic_bp !== undefined && payload.diastolic_bp !== undefined) {
      payload.blood_pressure = `${payload.systolic_bp}/${payload.diastolic_bp}`;
    }

    // Validate and parse blood glucose (0-2000)
    if (formData.blood_glucose !== "") {
      const val = Number(formData.blood_glucose);
      if (Number.isNaN(val) || val < 0 || val > 2000) {
        setError("Blood glucose must be a number between 0 and 2000 mg/dL.");
        return;
      }
      payload.blood_glucose = val;
      enteredCount++;
    }

    // Validate and parse heart rate (0-400)
    if (formData.heart_rate !== "") {
      const val = Number(formData.heart_rate);
      if (Number.isNaN(val) || val < 0 || val > 400) {
        setError("Heart rate must be a number between 0 and 400 bpm.");
        return;
      }
      payload.heart_rate = val;
      enteredCount++;
    }

    // Validate and parse temperature (0-100)
    if (formData.temperature !== "") {
      const val = Number(formData.temperature);
      if (Number.isNaN(val) || val < 0 || val > 100) {
        setError("Body temperature must be a number between 0 and 100 °C.");
        return;
      }
      payload.temperature = val;
      enteredCount++;
    }

    // Validate and parse oxygen saturation (0-100)
    if (formData.oxygen_saturation !== "") {
      const val = Number(formData.oxygen_saturation);
      if (Number.isNaN(val) || val < 0 || val > 100) {
        setError("Oxygen saturation must be a percentage between 0 and 100%.");
        return;
      }
      payload.oxygen_saturation = val;
      enteredCount++;
    }

    // Validate and parse hemoglobin (0-30)
    if (formData.hemoglobin !== "") {
      const val = Number(formData.hemoglobin);
      if (Number.isNaN(val) || val < 0 || val > 30) {
        setError("Hemoglobin must be a number between 0 and 30 g/dL.");
        return;
      }
      payload.hemoglobin = val;
      enteredCount++;
    }

    // Validate and parse weight (0-500)
    if (formData.weight !== "") {
      const val = Number(formData.weight);
      if (Number.isNaN(val) || val <= 0 || val > 500) {
        setError("Weight must be a number between 0 and 500 kg.");
        return;
      }
      payload.weight = val;
      enteredCount++;
    }

    if (enteredCount === 0) {
      setError("Please enter at least one clinical measurement value.");
      return;
    }

    setSubmitting(true);

    try {
      const response = await authFetch(`${API_URL}/clinical-measurements/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        if (response.status === 409) {
          throw new Error(data.detail || "Identical clinical measurements already exist for this visit.");
        }
        if (response.status === 404) {
          throw new Error(data.detail || "Patient or visit not found.");
        }
        if (response.status === 422) {
          const detail = Array.isArray(data.detail)
            ? data.detail.map((d) => d.msg || "Invalid value").join(", ")
            : data.detail || "Validation error.";
          throw new Error(detail);
        }
        throw new Error(data.detail || `Failed to save measurement (${response.status}).`);
      }

      setSuccessMessage("Clinical measurements recorded successfully!");

      if (onMeasurementCreated) {
        onMeasurementCreated(data);
      }

      // Reset form
      setFormData({
        systolic_bp: "",
        diastolic_bp: "",
        blood_glucose: "",
        heart_rate: "",
        temperature: "",
        oxygen_saturation: "",
        hemoglobin: "",
        weight: "",
        measured_at: "",
      });

      setTimeout(() => {
        onClose();
        setSuccessMessage("");
      }, 1000);
    } catch (err) {
      setError(err.message || "Failed to record measurements.");
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
              <Activity size={20} />
            </span>
            <div>
              <h3>Record Clinical Measurements</h3>
              <p>Enter verified vitals and lab measurements for this patient's visit.</p>
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
              <label htmlFor="meas_patient_id">
                Patient <span className="req">*</span>
              </label>
              <select
                id="meas_patient_id"
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
              <label htmlFor="meas_visit_id">
                Encounter Visit <span className="req">*</span>
              </label>
              <select
                id="meas_visit_id"
                value={visitId}
                onChange={(e) => setVisitId(e.target.value)}
                disabled={loadingVisits || visits.length === 0}
                required
              >
                {loadingVisits && <option value="">Loading visits...</option>}
                {!loadingVisits && visits.length === 0 && (
                  <option value="">No visits found (Record a visit first)</option>
                )}
                {visits.map((v) => (
                  <option key={v.id} value={v.id}>
                    Visit #{v.id} — {v.visit_date}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="meas_measured_at">Actual Measurement Time (Optional)</label>
              <input
                id="meas_measured_at"
                type="datetime-local"
                value={formData.measured_at}
                onChange={(e) => handleFieldChange("measured_at", e.target.value)}
              />
              <span className="field-hint">Leave blank if taken during visit</span>
            </div>

            <div className="form-group">
              <label htmlFor="systolic_bp">Systolic BP (mmHg)</label>
              <input
                id="systolic_bp"
                type="number"
                min="0"
                max="300"
                step="1"
                placeholder="e.g. 120"
                value={formData.systolic_bp}
                onChange={(e) => handleFieldChange("systolic_bp", e.target.value)}
              />
              <span className="field-hint">Range: 0 - 300 mmHg</span>
            </div>

            <div className="form-group">
              <label htmlFor="diastolic_bp">Diastolic BP (mmHg)</label>
              <input
                id="diastolic_bp"
                type="number"
                min="0"
                max="200"
                step="1"
                placeholder="e.g. 80"
                value={formData.diastolic_bp}
                onChange={(e) => handleFieldChange("diastolic_bp", e.target.value)}
              />
              <span className="field-hint">Range: 0 - 200 mmHg</span>
            </div>

            <div className="form-group">
              <label htmlFor="blood_glucose">Blood Glucose (mg/dL)</label>
              <input
                id="blood_glucose"
                type="number"
                min="0"
                max="2000"
                step="0.1"
                placeholder="e.g. 95"
                value={formData.blood_glucose}
                onChange={(e) => handleFieldChange("blood_glucose", e.target.value)}
              />
              <span className="field-hint">Fasting or random glucose</span>
            </div>

            <div className="form-group">
              <label htmlFor="heart_rate">Heart Rate (bpm)</label>
              <input
                id="heart_rate"
                type="number"
                min="0"
                max="400"
                step="1"
                placeholder="e.g. 72"
                value={formData.heart_rate}
                onChange={(e) => handleFieldChange("heart_rate", e.target.value)}
              />
              <span className="field-hint">Pulses per minute</span>
            </div>

            <div className="form-group">
              <label htmlFor="temperature">Body Temperature (°C)</label>
              <input
                id="temperature"
                type="number"
                min="0"
                max="100"
                step="0.1"
                placeholder="e.g. 36.8"
                value={formData.temperature}
                onChange={(e) => handleFieldChange("temperature", e.target.value)}
              />
              <span className="field-hint">Range: 0 - 100 °C</span>
            </div>

            <div className="form-group">
              <label htmlFor="oxygen_saturation">Oxygen Saturation (SpO₂ %)</label>
              <input
                id="oxygen_saturation"
                type="number"
                min="0"
                max="100"
                step="0.1"
                placeholder="e.g. 98"
                value={formData.oxygen_saturation}
                onChange={(e) => handleFieldChange("oxygen_saturation", e.target.value)}
              />
              <span className="field-hint">Range: 0 - 100%</span>
            </div>

            <div className="form-group">
              <label htmlFor="hemoglobin">Hemoglobin (g/dL)</label>
              <input
                id="hemoglobin"
                type="number"
                min="0"
                max="30"
                step="0.1"
                placeholder="e.g. 14.2"
                value={formData.hemoglobin}
                onChange={(e) => handleFieldChange("hemoglobin", e.target.value)}
              />
              <span className="field-hint">Range: 0 - 30 g/dL</span>
            </div>

            <div className="form-group">
              <label htmlFor="weight">Weight (kg)</label>
              <input
                id="weight"
                type="number"
                min="0"
                max="500"
                step="0.1"
                placeholder="e.g. 70.5"
                value={formData.weight}
                onChange={(e) => handleFieldChange("weight", e.target.value)}
              />
              <span className="field-hint">Body weight in kg</span>
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
              disabled={submitting || visits.length === 0}
            >
              {submitting ? "Saving Measurements..." : "Save Measurements"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
