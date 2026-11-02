import { useEffect, useState, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Clock,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  Search,
  RefreshCw,
  ArrowLeft,
  Sliders,
  Check,
  ExternalLink,
  FileDown,
  Activity,
  CalendarDays,
  TrendingUp,
  UserCheck,
  LogOut,
} from "lucide-react";

import "./ClinicalAlertsDashboard.css";
import { API_URL, authFetch, authDownloadBlob } from "../config";
import { usePatient } from "../context/PatientContext";
import { useAuth } from "../context/AuthContext";

const REVIEW_STORAGE_KEY = "caretrack_alert_reviews";

export default function ClinicalAlertsDashboard() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [searchParams] = useSearchParams();
  const { selectedPatientId, selectPatient } = usePatient();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [rulesExpanded, setRulesExpanded] = useState(false);
  const [selectedFilter, setSelectedFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [reviews, setReviews] = useState(() => {
    try {
      const saved = localStorage.getItem(REVIEW_STORAGE_KEY);
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  // Check if a specific patient was passed in the query
  const queryPatientId = searchParams.get("patientId");

  const loadAlertsOverview = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(`${API_URL}/clinical-alerts/overview`);
      if (!res.ok) {
        throw new Error(`Failed to load alerts overview (${res.status})`);
      }
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err.message || "Failed to connect to clinical alerts service.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAlertsOverview();
  }, []);

  const toggleReviewStatus = (patientId) => {
    setReviews((prev) => {
      const current = prev[patientId];
      const nextStatus = current?.status === "reviewed" ? "pending" : "reviewed";
      const updated = {
        ...prev,
        [patientId]: {
          status: nextStatus,
          timestamp: new Date().toISOString(),
          reviewer: "Attending Clinician",
        },
      };
      try {
        localStorage.setItem(REVIEW_STORAGE_KEY, JSON.stringify(updated));
      } catch (err) {
        console.error("Failed to save review status:", err);
      }
      return updated;
    });
  };

  const handleSelectPatient = (patient) => {
    selectPatient(String(patient.patient_id));
  };

  const handleDownloadPdf = (patientId, patientName) => {
    authDownloadBlob(
      `${API_URL}/patients/${patientId}/pdf`,
      `CareTrack_Patient_${patientId}_History.pdf`
    ).catch((err) => alert(err.message || "Failed to download patient history PDF."));
  };

  // Filter & Search Logic
  const filteredPatients = useMemo(() => {
    if (!data?.patients) return [];

    return data.patients.filter((p) => {
      // Priority tier filter
      if (selectedFilter === "high" && p.highest_severity !== "high") return false;
      if (selectedFilter === "moderate" && p.highest_severity !== "moderate") return false;
      if (selectedFilter === "normal" && p.highest_severity !== "normal") return false;
      if (selectedFilter === "no_data" && p.highest_severity !== "no_data") return false;
      if (selectedFilter === "reviewed") {
        if (reviews[p.patient_id]?.status !== "reviewed") return false;
      }
      if (selectedFilter === "pending") {
        if (reviews[p.patient_id]?.status === "reviewed") return false;
      }

      // Text search filter
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        const matchesName = (p.patient_name || "").toLowerCase().includes(query);
        const matchesCode = (p.patient_code || "").toLowerCase().includes(query);
        const matchesLocation = (p.location || "").toLowerCase().includes(query);
        return matchesName || matchesCode || matchesLocation;
      }

      return true;
    });
  }, [data, selectedFilter, searchQuery, reviews]);

  const summary = data?.summary || {
    total_patients_evaluated: 0,
    patients_with_alerts: 0,
    high_priority_count: 0,
    moderate_priority_count: 0,
    normal_count: 0,
    no_data_count: 0,
  };

  return (
    <div className="alerts-dashboard-page">
      {/* HEADER */}
      <header className="alerts-header">
        <div>
          <button
            type="button"
            className="btn-refresh"
            onClick={() => navigate("/")}
            style={{ marginBottom: "10px" }}
          >
            <ArrowLeft size={14} /> Back to Dashboard
          </button>
          <span className="eyebrow">CARETRACK AI · CLINICAL SCREENING & TRIAGE</span>
          <h1>Clinical Alerts & Health Urgency Dashboard</h1>
          <p className="panel-description">
            Longitudinal screening triage, clinical screening alerts, and review tracking across all registered patients.
          </p>
        </div>

        <div className="alerts-header-actions">
          <button
            type="button"
            className="btn-refresh"
            onClick={loadAlertsOverview}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            Refresh Alerts
          </button>

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

      {/* CLINICAL SAFETY & SIMULATED DATA DISCLAIMER BANNER */}
      <section className="alerts-disclaimer-banner demo-mode" role="region" aria-label="Clinical Safety Disclaimer">
        <div className="disclaimer-icon-wrap">
          <ShieldAlert size={22} />
        </div>
        <div className="disclaimer-content">
          <h4>Decision Support Disclaimer & Simulated Data Notice</h4>
          <p>
            {data?.disclaimer ||
              "Clinical screening rules applied to simulated patient data. Alerts are not medical diagnoses and do not constitute real-time monitoring. A qualified healthcare professional must review and confirm all clinical findings."}
          </p>
          <div className="disclaimer-tags">
            <span className="demo-pill">Simulated Test Records</span>
            <span className="safety-pill">Not Clinically Validated Thresholds</span>
            <span className="safety-pill">No Continuous Telemetry Claimed</span>
            <span className="safety-pill">Clinical Judgement Required</span>
          </div>
        </div>
      </section>

      {/* KPI SUMMARY CARDS */}
      <section className="alerts-kpi-grid">
        <div
          className={`alerts-kpi-card high ${selectedFilter === "high" ? "active-filter" : ""}`}
          onClick={() => setSelectedFilter(selectedFilter === "high" ? "all" : "high")}
          style={{ cursor: "pointer" }}
        >
          <div className="kpi-icon-box red">
            <AlertTriangle size={22} />
          </div>
          <div className="kpi-details">
            <span className="kpi-value">{summary.high_priority_count}</span>
            <span className="kpi-label">High Priority Flags</span>
          </div>
        </div>

        <div
          className={`alerts-kpi-card moderate ${selectedFilter === "moderate" ? "active-filter" : ""}`}
          onClick={() => setSelectedFilter(selectedFilter === "moderate" ? "all" : "moderate")}
          style={{ cursor: "pointer" }}
        >
          <div className="kpi-icon-box amber">
            <AlertCircle size={22} />
          </div>
          <div className="kpi-details">
            <span className="kpi-value">{summary.moderate_priority_count}</span>
            <span className="kpi-label">Moderate Flags</span>
          </div>
        </div>

        <div
          className={`alerts-kpi-card normal ${selectedFilter === "normal" ? "active-filter" : ""}`}
          onClick={() => setSelectedFilter(selectedFilter === "normal" ? "all" : "normal")}
          style={{ cursor: "pointer" }}
        >
          <div className="kpi-icon-box green">
            <CheckCircle2 size={22} />
          </div>
          <div className="kpi-details">
            <span className="kpi-value">{summary.normal_count}</span>
            <span className="kpi-label">Within Normal Limits</span>
          </div>
        </div>

        <div
          className={`alerts-kpi-card no-data ${selectedFilter === "no_data" ? "active-filter" : ""}`}
          onClick={() => setSelectedFilter(selectedFilter === "no_data" ? "all" : "no_data")}
          style={{ cursor: "pointer" }}
        >
          <div className="kpi-icon-box slate">
            <Clock size={22} />
          </div>
          <div className="kpi-details">
            <span className="kpi-value">{summary.no_data_count}</span>
            <span className="kpi-label">Missing Vitals</span>
          </div>
        </div>

        <div
          className={`alerts-kpi-card total ${selectedFilter === "all" ? "active-filter" : ""}`}
          onClick={() => setSelectedFilter("all")}
          style={{ cursor: "pointer" }}
        >
          <div className="kpi-icon-box cyan">
            <UserCheck size={22} />
          </div>
          <div className="kpi-details">
            <span className="kpi-value">{summary.total_patients_evaluated}</span>
            <span className="kpi-label">Total Patients Evaluated</span>
          </div>
        </div>
      </section>

      {/* CONFIGURABLE CLINICAL RULES ACCORDION */}
      <section className="alerts-rules-panel">
        <div
          className={`rules-panel-header ${rulesExpanded ? "open" : ""}`}
          onClick={() => setRulesExpanded((prev) => !prev)}
        >
          <div className="rules-panel-title">
            <Sliders size={18} color="var(--primary)" />
            <h3>Configured Clinical Screening Rules</h3>
            <span className="rules-badge">{data?.rules?.length || 6} Screening Parameters</span>
          </div>
          <button type="button" className="text-button" style={{ fontSize: "12px" }}>
            {rulesExpanded ? (
              <>
                Hide Rulebook <ChevronUp size={16} />
              </>
            ) : (
              <>
                View Rulebook Parameters <ChevronDown size={16} />
              </>
            )}
          </button>
        </div>

        {rulesExpanded && (
          <div className="rules-grid">
            {(data?.rules || []).map((rule, idx) => (
              <div key={rule.field || idx} className={`rule-chip-card ${rule.severity}`}>
                <div className="rule-chip-info">
                  <span className="rule-metric-name">{rule.metric}</span>
                  <span className="rule-threshold-range">
                    Normal Clinical Range:{" "}
                    <strong>
                      {rule.low !== null ? `${rule.low}` : "—"} to{" "}
                      {rule.high !== null ? `${rule.high}` : "—"} {rule.unit}
                    </strong>
                  </span>
                </div>
                <span className={`rule-severity-pill ${rule.severity}`}>
                  {rule.severity} Tier
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* FILTER TABS & SEARCH BAR */}
      <div className="alerts-controls-row">
        <div className="alerts-filter-tabs">
          <button
            type="button"
            className={`filter-tab-btn ${selectedFilter === "all" ? "active" : ""}`}
            onClick={() => setSelectedFilter("all")}
          >
            All Patients <span className="tab-count-badge">{summary.total_patients_evaluated}</span>
          </button>

          <button
            type="button"
            className={`filter-tab-btn ${selectedFilter === "high" ? "active" : ""}`}
            onClick={() => setSelectedFilter("high")}
          >
            High Priority <span className="tab-count-badge">{summary.high_priority_count}</span>
          </button>

          <button
            type="button"
            className={`filter-tab-btn ${selectedFilter === "moderate" ? "active" : ""}`}
            onClick={() => setSelectedFilter("moderate")}
          >
            Moderate Flags <span className="tab-count-badge">{summary.moderate_priority_count}</span>
          </button>

          <button
            type="button"
            className={`filter-tab-btn ${selectedFilter === "normal" ? "active" : ""}`}
            onClick={() => setSelectedFilter("normal")}
          >
            Within Limits <span className="tab-count-badge">{summary.normal_count}</span>
          </button>

          <button
            type="button"
            className={`filter-tab-btn ${selectedFilter === "no_data" ? "active" : ""}`}
            onClick={() => setSelectedFilter("no_data")}
          >
            Missing Vitals <span className="tab-count-badge">{summary.no_data_count}</span>
          </button>
        </div>

        <div className="alerts-search-box">
          <Search size={16} color="var(--muted)" />
          <input
            type="text"
            placeholder="Search by name, code, or clinic..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* LOADING & ERROR STATES */}
      {loading && (
        <div className="alerts-loading-state">
          <div className="spinner" />
          <p>Evaluating clinical screening rules against patient records...</p>
        </div>
      )}

      {error && !loading && (
        <div className="alerts-empty-state">
          <AlertTriangle size={32} color="#dc2626" />
          <h3>Unable to load clinical alerts</h3>
          <p>{error}</p>
          <button type="button" className="btn-refresh" onClick={loadAlertsOverview}>
            Retry
          </button>
        </div>
      )}

      {/* PATIENT ALERTS ROSTER */}
      {!loading && !error && (
        <div className="alerts-roster-list">
          {filteredPatients.length === 0 ? (
            <div className="alerts-empty-state">
              <CheckCircle2 size={36} color="var(--primary)" />
              <h3>No matching patient alert records</h3>
              <p>Try clearing filters or search keywords to view other patients.</p>
            </div>
          ) : (
            filteredPatients.map((patient) => {
              const isSelected = String(patient.patient_id) === String(selectedPatientId);
              const isHighlighted = queryPatientId && String(patient.patient_id) === String(queryPatientId);
              const reviewState = reviews[patient.patient_id];
              const isReviewed = reviewState?.status === "reviewed";

              return (
                <article
                  key={patient.patient_id}
                  className={`patient-alert-card ${patient.highest_severity} ${
                    isSelected ? "is-active-patient" : ""
                  }`}
                  style={isHighlighted ? { outline: "2px solid #087f8c" } : undefined}
                >
                  {/* CARD HEADER */}
                  <div className="pac-header">
                    <div className="pac-patient-info">
                      <div className="pac-title-row">
                        <h3 className="pac-name">{patient.patient_name}</h3>
                        <span className="pac-code">{patient.patient_code}</span>
                        {isSelected && (
                          <span className="rules-badge" style={{ background: "#e0f2fe", color: "#0369a1" }}>
                            Active Context
                          </span>
                        )}
                      </div>

                      <div className="pac-meta-row">
                        <span className="pac-meta-item">
                          Age: <strong>{patient.age ?? "—"}</strong>
                        </span>
                        <span className="pac-meta-item">
                          Gender: <strong>{patient.gender ?? "—"}</strong>
                        </span>
                        <span className="pac-meta-item">
                          Location: <strong>{patient.location ?? "General Clinic"}</strong>
                        </span>
                        <span className="pac-meta-item">
                          Latest Visit:{" "}
                          <strong>
                            {patient.latest_visit_date ? patient.latest_visit_date : "No visits recorded"}
                          </strong>
                        </span>
                      </div>
                    </div>

                    <div className="pac-status-badges">
                      {/* PRIORITY BADGE */}
                      {patient.highest_severity === "high" && (
                        <span className="severity-badge high">
                          <AlertTriangle size={14} /> High Urgency Alert
                        </span>
                      )}
                      {patient.highest_severity === "moderate" && (
                        <span className="severity-badge moderate">
                          <AlertCircle size={14} /> Moderate Alert
                        </span>
                      )}
                      {patient.highest_severity === "normal" && (
                        <span className="severity-badge normal">
                          <CheckCircle2 size={14} /> Within Normal Limits
                        </span>
                      )}
                      {patient.highest_severity === "no_data" && (
                        <span className="severity-badge no_data">
                          <Clock size={14} /> Vitals Needed
                        </span>
                      )}

                      {/* REVIEW STATUS TOGGLE */}
                      <button
                        type="button"
                        className={`review-toggle-btn ${isReviewed ? "reviewed" : "pending"}`}
                        onClick={() => toggleReviewStatus(patient.patient_id)}
                        title="Click to toggle clinician review status"
                      >
                        {isReviewed ? (
                          <>
                            <Check size={13} /> Reviewed by Clinician
                          </>
                        ) : (
                          <>
                            <Clock size={13} /> Pending Review
                          </>
                        )}
                      </button>
                    </div>
                  </div>

                  {/* SUMMARY TEXT */}
                  <p className="pac-summary-text">{patient.summary}</p>

                  {/* TRIGGERING MEASUREMENTS SECTION */}
                  {patient.alerts && patient.alerts.length > 0 && (
                    <div
                      className={`pac-alerts-container ${
                        patient.highest_severity === "moderate" ? "moderate-container" : ""
                      }`}
                    >
                      <div className="pac-alerts-label">
                        <AlertTriangle size={14} />
                        Triggering Measurements ({patient.alerts.length} Flagged)
                      </div>

                      <div className="trigger-measurements-grid">
                        {patient.alerts.map((alert, idx) => (
                          <div key={alert.field || idx} className="trigger-item-card">
                            <div className="trigger-item-top">
                              <span className="trigger-item-metric">{alert.metric}</span>
                              <span className={`trigger-item-severity ${alert.severity}`}>
                                {alert.severity}
                              </span>
                            </div>

                            <div className="trigger-item-readings">
                              <div>
                                <span style={{ fontSize: "11px", color: "var(--muted)" }}>Recorded: </span>
                                <span className="reading-val">
                                  {alert.value} {alert.unit}
                                </span>
                              </div>
                              <div>
                                <span style={{ fontSize: "11px", color: "var(--muted)" }}>Screening Rule: </span>
                                <span className="threshold-val">{alert.threshold}</span>
                              </div>
                            </div>

                            <p className="trigger-item-reason">{alert.reason}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* ACTIONS FOOTER */}
                  <div className="pac-footer-actions">
                    <div className="pac-action-links">
                      <button
                        type="button"
                        className={`pac-btn select-patient ${isSelected ? "is-selected" : ""}`}
                        onClick={() => handleSelectPatient(patient)}
                      >
                        {isSelected ? "Active Selected Patient" : "Select Patient"}
                      </button>

                      <button
                        type="button"
                        className="pac-btn"
                        onClick={() => {
                          handleSelectPatient(patient);
                          navigate(`/trends?patientId=${patient.patient_id}`);
                        }}
                      >
                        <Activity size={13} /> Trends & Vitals
                      </button>

                      <button
                        type="button"
                        className="pac-btn"
                        onClick={() => {
                          handleSelectPatient(patient);
                          navigate(`/timeline?patientId=${patient.patient_id}`);
                        }}
                      >
                        <CalendarDays size={13} /> Timeline
                      </button>

                      <button
                        type="button"
                        className="pac-btn"
                        onClick={() => {
                          handleSelectPatient(patient);
                          navigate(`/radar?patientId=${patient.patient_id}`);
                        }}
                      >
                        <TrendingUp size={13} /> Health Radar
                      </button>
                    </div>

                    <button
                      type="button"
                      className="pac-btn"
                      onClick={() => handleDownloadPdf(patient.patient_id, patient.patient_name)}
                      title="Download longitudinal patient history report as PDF"
                    >
                      <FileDown size={13} /> Patient PDF
                    </button>
                  </div>
                </article>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
