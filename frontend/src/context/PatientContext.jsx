import { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react";
import { API_URL, authFetch } from "../config";

const PatientContext = createContext(null);

export function PatientProvider({ children }) {
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [invalidPatientId, setInvalidPatientId] = useState("");
  const [loadingPatients, setLoadingPatients] = useState(true);
  const [patientError, setPatientError] = useState("");

  const fetchPatientsList = useCallback(async () => {
    setLoadingPatients(true);
    setPatientError("");

    try {
      const response = await authFetch(`${API_URL}/patients/?skip=0&limit=100`);
      if (!response.ok) {
        throw new Error(`Failed to load patient roster (${response.status})`);
      }
      const data = await response.json();
      const list = Array.isArray(data) ? data : [];
      setPatients(list);
      return list;
    } catch (err) {
      setPatientError(err.message || "Could not connect to backend to load patients.");
      return [];
    } finally {
      setLoadingPatients(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    let active = true;

    async function initialize() {
      const list = await fetchPatientsList();
      if (!active) return;

      const params = new URLSearchParams(window.location.search);
      const urlPatientId = params.get("patientId")?.trim();
      const savedPatientId = sessionStorage.getItem("caretrack_active_patient_id")?.trim();

      if (urlPatientId) {
        const found = list.find((p) => String(p.id) === urlPatientId);
        if (found) {
          setSelectedPatientId(String(found.id));
          sessionStorage.setItem("caretrack_active_patient_id", String(found.id));
        } else {
          // Explicitly flag invalid URL patient ID rather than silently picking another
          setInvalidPatientId(urlPatientId);
          setSelectedPatientId("");
        }
      } else if (savedPatientId) {
        const found = list.find((p) => String(p.id) === savedPatientId);
        if (found) {
          setSelectedPatientId(String(found.id));
        } else {
          // Explicitly flag invalid saved patient ID rather than silently picking another
          setInvalidPatientId(savedPatientId);
          setSelectedPatientId("");
        }
      } else if (list.length > 0) {
        // Default to first active patient only when no specific ID was requested
        setSelectedPatientId(String(list[0].id));
        sessionStorage.setItem("caretrack_active_patient_id", String(list[0].id));
      }
    }

    initialize();

    return () => {
      active = false;
    };
  }, [fetchPatientsList]);

  const selectPatient = useCallback((id) => {
    const cleanId = String(id).trim();
    setInvalidPatientId("");
    setSelectedPatientId(cleanId);
    if (cleanId) {
      sessionStorage.setItem("caretrack_active_patient_id", cleanId);
    } else {
      sessionStorage.removeItem("caretrack_active_patient_id");
    }
  }, []);

  const refreshPatients = useCallback(async (autoSelectId = null) => {
    const list = await fetchPatientsList();
    if (autoSelectId) {
      const targetId = String(autoSelectId).trim();
      setInvalidPatientId("");
      setSelectedPatientId(targetId);
      sessionStorage.setItem("caretrack_active_patient_id", targetId);
    }
    return list;
  }, [fetchPatientsList]);

  const selectedPatient = useMemo(() => {
    if (!selectedPatientId) return null;
    return patients.find((p) => String(p.id) === String(selectedPatientId)) || null;
  }, [patients, selectedPatientId]);

  const value = useMemo(
    () => ({
      patients,
      selectedPatientId,
      selectedPatient,
      invalidPatientId,
      loadingPatients,
      patientError,
      selectPatient,
      refreshPatients,
    }),
    [
      patients,
      selectedPatientId,
      selectedPatient,
      invalidPatientId,
      loadingPatients,
      patientError,
      selectPatient,
      refreshPatients,
    ]
  );

  return <PatientContext.Provider value={value}>{children}</PatientContext.Provider>;
}

export function usePatient() {
  const context = useContext(PatientContext);
  if (!context) {
    throw new Error("usePatient must be used within a PatientProvider");
  }
  return context;
}
