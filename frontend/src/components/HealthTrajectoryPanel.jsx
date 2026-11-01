import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  Calendar,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileQuestion,
  HelpCircle,
  Info,
  Minus,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  UserX,
} from "lucide-react";

import "./HealthTrajectoryPanel.css";
import { API_URL, authFetch } from "../config";
import { usePatient } from "../context/PatientContext";

function formatNodeTimestamp(reading) {
  if (!reading || !reading.visit_date) return null;
  if (!reading.measured_at) {
    return (
      <span className="reading-meta">
        <Calendar size={11} />
        <span>{reading.visit_date}</span>
      </span>
    );
  }
  try {
    const d = new Date(reading.measured_at);
    const timeStr = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return (
      <span className="reading-meta" title={`Measured at: ${reading.measured_at}`}>
        <Calendar size={11} />
        <span>{reading.visit_date}</span>
        <span className="node-time">· {timeStr}</span>
      </span>
    );
  } catch {
    return (
      <span className="reading-meta">
        <Calendar size={11} />
        <span>{reading.visit_date}</span>
      </span>
    );
  }
}

export default function HealthTrajectoryPanel({ patientId: propPatientId = null }) {
  const navigate = useNavigate();
  const { selectedPatientId } = usePatient();
  const effectivePatientId = propPatientId || selectedPatientId;

  const [trajectoryData, setTrajectoryData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeFilter, setActiveFilter] = useState("ALL"); // ALL, CONCERNING, IMPROVING, STABLE, GAPS

  useEffect(() => {
    let active = true;

    async function loadTrajectory() {
      if (!effectivePatientId) {
        setTrajectoryData(null);
        return;
      }

      setLoading(true);
      setError("");

      try {
        const response = await authFetch(
          `${API_URL}/patients/${effectivePatientId}/health-trajectory`
        );
        if (!response.ok) {
          throw new Error(
            `Failed to load HealthTrajectory data (HTTP ${response.status})`
          );
        }
        const data = await response.json();
        if (active) {
          setTrajectoryData(data);
        }
      } catch (err) {
        if (active) {
          setError(
            err.message ||
              "Could not connect to HealthTrajectory decision support service."
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadTrajectory();

    return () => {
      active = false;
    };
  }, [effectivePatientId]);

  const summary = trajectoryData?.summary;
  const allMetrics = useMemo(
    () => trajectoryData?.metrics || [],
    [trajectoryData]
  );

  // Filter metrics
  const filteredMetrics = useMemo(() => {
    if (activeFilter === "CONCERNING") {
      return allMetrics.filter((m) => m.classification === "CONCERNING_CHANGE");
    }
    if (activeFilter === "IMPROVING") {
      return allMetrics.filter((m) => m.classification === "IMPROVING_TREND");
    }
    if (activeFilter === "STABLE") {
      return allMetrics.filter(
        (m) =>
          m.classification === "STABLE_TREND" ||
          m.classification === "MODERATE_SHIFT"
      );
    }
    if (activeFilter === "GAPS") {
      return allMetrics.filter(
        (m) =>
          m.classification === "DATA_GAP" ||
          m.classification === "DATA_INCONSISTENCY"
      );
    }
    return allMetrics;
  }, [allMetrics, activeFilter]);

  function getStatusBadge(status) {
    switch (status) {
      case "ATTENTION_REQUIRED":
        return {
          label: "Attention Required",
          className: "status-badge attention",
          icon: AlertOctagon,
        };
      case "STABILIZING_TRAJECTORY":
        return {
          label: "Stabilizing Trajectory",
          className: "status-badge improving",
          icon: TrendingUp,
        };
      case "STABLE_MAINTENANCE":
        return {
          label: "Stable Maintenance",
          className: "status-badge stable",
          icon: CheckCircle2,
        };
      case "INSUFFICIENT_HISTORY":
      default:
        return {
          label: "Insufficient History",
          className: "status-badge insufficient",
          icon: HelpCircle,
        };
    }
  }

  function getMetricClassificationBadge(classification, label) {
    switch (classification) {
      case "CONCERNING_CHANGE":
        return {
          className: "metric-badge concerning",
          icon: AlertTriangle,
          label: label || "Concerning Shift",
        };
      case "IMPROVING_TREND":
        return {
          className: "metric-badge improving",
          icon: CheckCircle2,
          label: label || "Improving Trend",
        };
      case "MODERATE_SHIFT":
        return {
          className: "metric-badge moderate",
          icon: Activity,
          label: label || "Moderate Shift",
        };
      case "DATA_GAP":
      case "DATA_INCONSISTENCY":
        return {
          className: "metric-badge gap",
          icon: FileQuestion,
          label: label || "Data Gap",
        };
      case "STABLE_TREND":
      default:
        return {
          className: "metric-badge stable",
          icon: Minus,
          label: label || "Stable",
        };
    }
  }

  if (!effectivePatientId) {
    return (
      <div className="trajectory-empty-state">
        <UserX size={44} className="empty-icon" />
        <h3>No Patient Selected</h3>
        <p>
          Select a patient from the roster above to analyze longitudinal clinical
          trajectories and multi-visit physiological changes.
        </p>
      </div>
    );
  }

  return (
    <div className="health-trajectory-container">
      {/* 1. Header Card */}
      <section className="trajectory-header-card">
        <div className="trajectory-header-main">
          <div className="trajectory-header-titles">
            <span className="trajectory-eyebrow">
              <Sparkles size={14} />
              CareTrack AI · Clinical Change Engine
            </span>
            <h2 className="trajectory-title">HealthTrajectory AI</h2>
            <p className="trajectory-subtitle">
              Explainable multi-visit longitudinal change detection comparing
              baseline, previous, and latest readings with transparent delta arithmetic.
            </p>
          </div>

          <div className="trajectory-header-actions">
            {summary && (
              <span
                className={
                  getStatusBadge(summary.overall_trajectory_status).className
                }
              >
                {(() => {
                  const BadgeIcon = getStatusBadge(
                    summary.overall_trajectory_status
                  ).icon;
                  return <BadgeIcon size={16} />;
                })()}
                {getStatusBadge(summary.overall_trajectory_status).label}
              </span>
            )}
            <button
              type="button"
              className="trajectory-refresh-btn"
              onClick={() => {
                setLoading(true);
                authFetch(
                  `${API_URL}/patients/${effectivePatientId}/health-trajectory`
                )
                  .then((res) => res.json())
                  .then((d) => setTrajectoryData(d))
                  .catch((e) => setError(e.message))
                  .finally(() => setLoading(false));
              }}
              disabled={loading}
              title="Refresh longitudinal trajectory analysis"
            >
              <RefreshCw size={14} className={loading ? "spin" : ""} />
              <span>{loading ? "Analyzing..." : "Refresh"}</span>
            </button>
          </div>
        </div>

        {/* 2. Stat Counter Summary Ribbon */}
        {summary && (
          <div className="trajectory-stats-ribbon">
            <div
              className={`stat-card ${
                activeFilter === "ALL" ? "active" : ""
              }`}
              onClick={() => setActiveFilter("ALL")}
              role="button"
              tabIndex={0}
            >
              <span className="stat-label">Total Visits Analyzed</span>
              <div className="stat-value-group">
                <span className="stat-number">
                  {summary.total_visits_recorded}
                </span>
                <span className="stat-subtext">
                  {summary.chronological_span || "Visits recorded"}
                </span>
              </div>
            </div>

            <div
              className={`stat-card stat-concerning ${
                activeFilter === "CONCERNING" ? "active" : ""
              }`}
              onClick={() => setActiveFilter("CONCERNING")}
              role="button"
              tabIndex={0}
            >
              <span className="stat-label">Concerning Shifts</span>
              <div className="stat-value-group">
                <span className="stat-number concerning">
                  {summary.concerning_count}
                </span>
                <span className="stat-subtext">Require clinician review</span>
              </div>
            </div>

            <div
              className={`stat-card stat-improving ${
                activeFilter === "IMPROVING" ? "active" : ""
              }`}
              onClick={() => setActiveFilter("IMPROVING")}
              role="button"
              tabIndex={0}
            >
              <span className="stat-label">Improving / Normalizing</span>
              <div className="stat-value-group">
                <span className="stat-number improving">
                  {summary.improving_count}
                </span>
                <span className="stat-subtext">Progressing toward target</span>
              </div>
            </div>

            <div
              className={`stat-card stat-stable ${
                activeFilter === "STABLE" ? "active" : ""
              }`}
              onClick={() => setActiveFilter("STABLE")}
              role="button"
              tabIndex={0}
            >
              <span className="stat-label">Stable Parameters</span>
              <div className="stat-value-group">
                <span className="stat-number stable">
                  {summary.stable_count}
                </span>
                <span className="stat-subtext">Within baseline bounds</span>
              </div>
            </div>

            <div
              className={`stat-card stat-gap ${
                activeFilter === "GAPS" ? "active" : ""
              }`}
              onClick={() => setActiveFilter("GAPS")}
              role="button"
              tabIndex={0}
            >
              <span className="stat-label">Data Gaps / Unrecorded</span>
              <div className="stat-value-group">
                <span className="stat-number gap">
                  {summary.data_gaps_count}
                </span>
                <span className="stat-subtext">Omitted measurements</span>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Loading Skeleton */}
      {loading && !trajectoryData && (
        <div className="trajectory-loading-card">
          <RefreshCw size={24} className="spin text-teal" />
          <p>
            Computing explainable longitudinal change trajectories across clinical
            visits...
          </p>
        </div>
      )}

      {/* Error Callout */}
      {error && (
        <div className="trajectory-error-card" role="alert">
          <AlertOctagon size={20} />
          <div>
            <strong>Unable to Load Trajectory Analysis</strong>
            <p>{error}</p>
          </div>
        </div>
      )}

      {/* 2.5 Grouped Visit Timing / Data Quality Notice */}
      {summary?.visit_quality_warnings &&
        summary.visit_quality_warnings.length > 0 && (
          <div className="trajectory-grouped-warning-card">
            <Clock size={18} className="grouped-warning-icon" />
            <div className="grouped-warning-body">
              <span className="grouped-warning-title">
                Source Visit Timing & Record Reconciliation Notice:
              </span>
              <ul className="grouped-warning-list">
                {summary.visit_quality_warnings.map((warnText, idx) => (
                  <li key={idx}>{warnText}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

      {/* 3. Factual Grounded Narrative & Clinical Notes */}
      {summary && (
        <section className="trajectory-narrative-card">
          <div className="narrative-section-header">
            <Info size={18} className="text-teal" />
            <h3>Clinician Decision Support Summary</h3>
            <span className="narrative-meta">
              Patient: <strong>{summary.patient_name}</strong> (
              <code>{summary.patient_code}</code>) · Visits:{" "}
              <strong>{summary.total_visits_recorded}</strong>
            </span>
          </div>

          <p className="narrative-body">
            {summary.factual_trajectory_narrative}
          </p>

          {summary.clinical_decision_support_notes &&
            summary.clinical_decision_support_notes.length > 0 && (
              <div className="trajectory-notes-list">
                <span className="notes-heading">
                  Recommended Clinician Follow-up Actions:
                </span>
                <ul>
                  {summary.clinical_decision_support_notes.map((note, idx) => (
                    <li key={idx}>
                      <ArrowRight size={13} className="bullet-arrow" />
                      <span>{note}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
        </section>
      )}

      {/* 4. Filter Tabs */}
      {trajectoryData && (
        <div className="trajectory-filter-tabs">
          <button
            type="button"
            className={`filter-tab ${activeFilter === "ALL" ? "active" : ""}`}
            onClick={() => setActiveFilter("ALL")}
          >
            All Parameters ({allMetrics.length})
          </button>
          <button
            type="button"
            className={`filter-tab concerning ${
              activeFilter === "CONCERNING" ? "active" : ""
            }`}
            onClick={() => setActiveFilter("CONCERNING")}
          >
            Concerning Shifts ({summary?.concerning_count ?? 0})
          </button>
          <button
            type="button"
            className={`filter-tab improving ${
              activeFilter === "IMPROVING" ? "active" : ""
            }`}
            onClick={() => setActiveFilter("IMPROVING")}
          >
            Improving Trends ({summary?.improving_count ?? 0})
          </button>
          <button
            type="button"
            className={`filter-tab stable ${
              activeFilter === "STABLE" ? "active" : ""
            }`}
            onClick={() => setActiveFilter("STABLE")}
          >
            Stable / Shifts ({summary?.stable_count ?? 0})
          </button>
          <button
            type="button"
            className={`filter-tab gaps ${
              activeFilter === "GAPS" ? "active" : ""
            }`}
            onClick={() => setActiveFilter("GAPS")}
          >
            Data Gaps ({summary?.data_gaps_count ?? 0})
          </button>
        </div>
      )}

      {/* 5. Metrics Cards Grid */}
      {filteredMetrics.length === 0 && trajectoryData && (
        <div className="trajectory-no-results">
          <CheckCircle2 size={32} />
          <p>No metrics match the selected "{activeFilter}" filter category.</p>
        </div>
      )}

      <div className="trajectory-metrics-grid">
        {filteredMetrics.map((metric) => {
          const badge = getMetricClassificationBadge(
            metric.classification,
            metric.classification_label
          );
          const BadgeIcon = badge.icon;
          const deltaSign =
            metric.delta_from_baseline !== null && metric.delta_from_baseline > 0
              ? "+"
              : "";

          return (
            <article
              key={metric.key}
              className={`trajectory-metric-card severity-${metric.severity_level}`}
            >
              {/* Card Header */}
              <div className="metric-card-top">
                <div className="metric-card-title-group">
                  <span className="metric-unit-tag">{metric.unit}</span>
                  <h4 className="metric-title">{metric.label}</h4>
                </div>

                <span className={badge.className}>
                  <BadgeIcon size={14} />
                  <span>{badge.label}</span>
                </span>
              </div>

              {/* Longitudinal 3-Node Reading Sequence */}
              <div className="metric-sequence-track">
                {/* Baseline Reading */}
                <div className="reading-node">
                  <span className="reading-node-label">Baseline</span>
                  {metric.baseline_reading &&
                  metric.baseline_reading.value !== null ? (
                    <>
                      <strong className="reading-val">
                        {metric.baseline_reading.value}
                        <span className="val-unit"> {metric.unit}</span>
                      </strong>
                      {formatNodeTimestamp(metric.baseline_reading)}
                      <span className="reading-source">
                        Visit #{metric.baseline_reading.visit_id}
                      </span>
                    </>
                  ) : (
                    <span className="reading-unrecorded">Not recorded</span>
                  )}
                </div>

                <div className="sequence-connector">
                  <ArrowRight size={14} />
                </div>

                {/* Previous Reading */}
                <div className="reading-node">
                  <span className="reading-node-label">Previous</span>
                  {metric.previous_reading &&
                  metric.previous_reading.value !== null ? (
                    <>
                      <strong className="reading-val">
                        {metric.previous_reading.value}
                        <span className="val-unit"> {metric.unit}</span>
                      </strong>
                      {formatNodeTimestamp(metric.previous_reading)}
                      <span className="reading-source">
                        Visit #{metric.previous_reading.visit_id}
                      </span>
                    </>
                  ) : (
                    <span className="reading-unrecorded">
                      {summary?.total_visits_recorded <= 2
                        ? "N/A (2 visits)"
                        : "Not recorded"}
                    </span>
                  )}
                </div>

                <div className="sequence-connector">
                  <ArrowRight size={14} />
                </div>

                {/* Latest Reading */}
                <div className="reading-node latest">
                  <span className="reading-node-label latest">Latest</span>
                  {metric.latest_reading &&
                  metric.latest_reading.value !== null ? (
                    <>
                      <strong className="reading-val">
                        {metric.latest_reading.value}
                        <span className="val-unit"> {metric.unit}</span>
                      </strong>
                      {formatNodeTimestamp(metric.latest_reading)}
                      <span className="reading-source">
                        Visit #{metric.latest_reading.visit_id}
                      </span>
                    </>
                  ) : (
                    <span className="reading-unrecorded">Missing on visit</span>
                  )}
                </div>
              </div>

              {/* Delta Calculations & Formula Breakdown */}
              <div className="metric-delta-box">
                <div className="delta-stats-row">
                  <div className="delta-item">
                    <span className="delta-item-label">
                      Change from Baseline:
                    </span>
                    {metric.delta_from_baseline !== null ? (
                      <span
                        className={`delta-item-val ${
                          metric.classification === "CONCERNING_CHANGE"
                            ? "concerning"
                            : metric.classification === "IMPROVING_TREND"
                            ? "improving"
                            : ""
                        }`}
                      >
                        {deltaSign}
                        {metric.delta_from_baseline} {metric.unit} (
                        {metric.percent_change_from_baseline !== null
                          ? `${deltaSign}${metric.percent_change_from_baseline}%`
                          : "0%"}
                        )
                      </span>
                    ) : (
                      <span className="delta-item-val unrecorded">N/A</span>
                    )}
                  </div>

                  {metric.delta_from_previous !== null && (
                    <div className="delta-item">
                      <span className="delta-item-label">
                        Shift from Previous:
                      </span>
                      <span className="delta-item-val secondary">
                        {metric.delta_from_previous > 0 ? "+" : ""}
                        {metric.delta_from_previous} {metric.unit}
                      </span>
                    </div>
                  )}
                </div>

                {/* Transparent Arithmetic Formula Tag */}
                <div className="metric-formula-tag" title="Exact delta arithmetic">
                  <code>{metric.formula_breakdown}</code>
                </div>
              </div>

              {/* Clinical Explanation */}
              <div className="metric-clinical-box">
                <p className="clinical-text">{metric.clinical_explanation}</p>
              </div>

              {/* Data Inconsistency / Multiple Readings / Quality Flags */}
              {(() => {
                const uniqueWarnings = [];
                if (metric.data_quality_note) {
                  uniqueWarnings.push(metric.data_quality_note);
                }
                if (
                  metric.latest_reading?.timestamp_warning &&
                  !uniqueWarnings.some((w) =>
                    w.includes(metric.latest_reading.timestamp_warning)
                  )
                ) {
                  uniqueWarnings.push(metric.latest_reading.timestamp_warning);
                }
                if (
                  metric.baseline_reading?.timestamp_warning &&
                  !uniqueWarnings.some((w) =>
                    w.includes(metric.baseline_reading.timestamp_warning)
                  )
                ) {
                  uniqueWarnings.push(metric.baseline_reading.timestamp_warning);
                }
                if (
                  metric.latest_reading?.has_multiple_readings &&
                  !uniqueWarnings.some((w) =>
                    w.toLowerCase().includes("multiple")
                  )
                ) {
                  uniqueWarnings.push(
                    "Multiple readings recorded on visit date; latest reading evaluated."
                  );
                }

                if (uniqueWarnings.length === 0) return null;

                return (
                  <div className="metric-quality-warning">
                    <AlertTriangle size={13} className="warning-icon" />
                    <div className="warning-text-container">
                      {uniqueWarnings.map((w, idx) => (
                        <div key={idx} className="warning-line">
                          {w}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}
            </article>
          );
        })}
      </div>

      {/* 6. Quick Cross-Feature Navigation */}
      <section className="trajectory-quick-links">
        <span className="quick-links-title">
          Explore Related Clinical Modules for Patient #{effectivePatientId}:
        </span>
        <div className="quick-links-group">
          <button
            type="button"
            className="quick-nav-btn"
            onClick={() => navigate(`/timeline?patientId=${effectivePatientId}`)}
          >
            <Calendar size={14} />
            <span>Patient Timeline</span>
            <ExternalLink size={12} />
          </button>
          <button
            type="button"
            className="quick-nav-btn"
            onClick={() => navigate(`/radar?patientId=${effectivePatientId}`)}
          >
            <Activity size={14} />
            <span>Health Change Radar</span>
            <ExternalLink size={12} />
          </button>
          <button
            type="button"
            className="quick-nav-btn"
            onClick={() => navigate(`/alerts?patientId=${effectivePatientId}`)}
          >
            <AlertTriangle size={14} />
            <span>Clinical Alerts Queue</span>
            <ExternalLink size={12} />
          </button>
          <button
            type="button"
            className="quick-nav-btn"
            onClick={() => navigate(`/copilot?patientId=${effectivePatientId}`)}
          >
            <Sparkles size={14} />
            <span>Ask Clinical Copilot</span>
            <ExternalLink size={12} />
          </button>
        </div>
      </section>

      {/* 7. Clinician Supervision & Regulatory Notice */}
      <footer className="trajectory-regulatory-card">
        <ShieldAlert size={18} className="shield-icon" />
        <div className="regulatory-text">
          <strong>Clinician Supervision & Non-Diagnostic Notice:</strong>
          <p>
            {trajectoryData?.disclaimer ||
              "Clinical decision support only. Not an autonomous diagnosis or clinically validated prediction system. All trajectory classifications are based strictly on documented historical readings and configured demonstration rules. A qualified healthcare professional must review and verify all findings against primary source records."}
          </p>
        </div>
      </footer>
    </div>
  );
}
