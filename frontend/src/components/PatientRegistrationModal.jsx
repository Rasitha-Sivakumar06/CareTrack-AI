import { useState } from "react";
import { UserPlus, X, AlertCircle, CheckCircle2 } from "lucide-react";
import { API_URL, authFetch } from "../config";
import { usePatient } from "../context/PatientContext";

export default function PatientRegistrationModal({ isOpen, onClose }) {
  const { refreshPatients } = usePatient();

  const [formData, setFormData] = useState({
    patient_code: "",
    name: "",
    age: "",
    gender: "",
    phone: "",
    location: "",
  });

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  if (!isOpen) return null;

  function handleChange(field, value) {
    setError("");
    setFormData((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSuccessMessage("");

    const code = formData.patient_code.trim();
    const name = formData.name.trim();

    // Client-side validations aligned with PostgreSQL column limits
    if (!code) {
      setError("Patient Code is required.");
      return;
    }
    if (code.length > 20) {
      setError("Patient Code must be 20 characters or fewer.");
      return;
    }
    if (!name) {
      setError("Patient Name is required.");
      return;
    }
    if (name.length > 100) {
      setError("Patient Name must be 100 characters or fewer.");
      return;
    }

    let parsedAge = null;
    if (formData.age !== "" && formData.age !== null && formData.age !== undefined) {
      parsedAge = Number(formData.age);
      if (!Number.isInteger(parsedAge) || parsedAge < 0 || parsedAge > 130) {
        setError("Age must be an integer between 0 and 130.");
        return;
      }
    }

    const gender = formData.gender.trim();
    if (gender.length > 20) {
      setError("Gender must be 20 characters or fewer.");
      return;
    }

    const phone = formData.phone.trim();
    if (phone.length > 20) {
      setError("Phone number must be 20 characters or fewer.");
      return;
    }

    const location = formData.location.trim();
    if (location.length > 100) {
      setError("Location must be 100 characters or fewer.");
      return;
    }

    setSubmitting(true);

    try {
      const payload = {
        patient_code: code,
        name: name,
        age: parsedAge,
        gender: gender || null,
        phone: phone || null,
        location: location || null,
      };

      const response = await authFetch(`${API_URL}/patients/`, {
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
          throw new Error(data.detail || `Patient code '${code}' is already registered.`);
        }
        if (response.status === 422) {
          const detail = Array.isArray(data.detail)
            ? data.detail.map((d) => d.msg || "Invalid field").join(", ")
            : data.detail || "Validation failed.";
          throw new Error(detail);
        }
        throw new Error(data.detail || `Failed to register patient (${response.status}).`);
      }

      setSuccessMessage(`Patient '${data.name}' (#${data.id}) registered successfully!`);
      // Auto refresh roster and select newly created patient
      await refreshPatients(data.id);

      // Reset form
      setFormData({
        patient_code: "",
        name: "",
        age: "",
        gender: "",
        phone: "",
        location: "",
      });

      setTimeout(() => {
        onClose();
        setSuccessMessage("");
      }, 1200);
    } catch (err) {
      setError(err.message || "Failed to register patient. Please check your connection.");
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
              <UserPlus size={20} />
            </span>
            <div>
              <h3>Register New Patient</h3>
              <p>Add a new patient to the CareTrack AI longitudinal system.</p>
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
              <label htmlFor="patient_code">
                Patient Code <span className="req">*</span>
              </label>
              <input
                id="patient_code"
                type="text"
                maxLength={20}
                required
                placeholder="e.g. CT-2026-001"
                value={formData.patient_code}
                onChange={(e) => handleChange("patient_code", e.target.value)}
              />
              <span className="field-hint">Max 20 characters (unique)</span>
            </div>

            <div className="form-group">
              <label htmlFor="name">
                Full Name <span className="req">*</span>
              </label>
              <input
                id="name"
                type="text"
                maxLength={100}
                required
                placeholder="e.g. Maya Devi"
                value={formData.name}
                onChange={(e) => handleChange("name", e.target.value)}
              />
              <span className="field-hint">Max 100 characters</span>
            </div>

            <div className="form-group">
              <label htmlFor="age">Age</label>
              <input
                id="age"
                type="number"
                min={0}
                max={130}
                placeholder="e.g. 48"
                value={formData.age}
                onChange={(e) => handleChange("age", e.target.value)}
              />
              <span className="field-hint">0 to 130 years</span>
            </div>

            <div className="form-group">
              <label htmlFor="gender">Gender</label>
              <select
                id="gender"
                value={formData.gender}
                onChange={(e) => handleChange("gender", e.target.value)}
              >
                <option value="">Select gender...</option>
                <option value="Female">Female</option>
                <option value="Male">Male</option>
                <option value="Other">Other</option>
                <option value="Not Disclosed">Not Disclosed</option>
              </select>
              <span className="field-hint">Max 20 characters</span>
            </div>

            <div className="form-group">
              <label htmlFor="phone">Phone Number</label>
              <input
                id="phone"
                type="tel"
                maxLength={20}
                placeholder="e.g. +91 98765 43210"
                value={formData.phone}
                onChange={(e) => handleChange("phone", e.target.value)}
              />
              <span className="field-hint">Max 20 characters</span>
            </div>

            <div className="form-group">
              <label htmlFor="location">Location / Clinic</label>
              <input
                id="location"
                type="text"
                maxLength={100}
                placeholder="e.g. Community Health Center, Ward 4"
                value={formData.location}
                onChange={(e) => handleChange("location", e.target.value)}
              />
              <span className="field-hint">Max 100 characters</span>
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
              {submitting ? "Registering..." : "Save Patient"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
