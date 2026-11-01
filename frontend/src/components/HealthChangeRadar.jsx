import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Info,
  Calendar,
  ArrowRight,
  BrainCircuit,
  RefreshCw,
  TrendingUp,
} from "lucide-react";

import "./HealthChangeRadar.css";
import { API_URL, authFetch } from "../config";
import { usePatient } from "../context/PatientContext";

function CustomRadarTooltip({ active, payload }) {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="radar-tooltip">
        <span className="radar-tooltip-title">{data.label}</span>
        <div className="radar-tooltip-row">
          <span>Baseline ({data.baseline_date || "Prior"}):</span>
          <strong>
            {data.baseline_value !== null ? `${data.baseline_value} ${data.unit}` : "Not recorded"}
          </strong>
        </div>
        <div className="radar-tooltip-row">
          <span>Current ({data.current_date || "Latest"}):</span>
          <strong>
            {data.current_value !== null ? `${data.current_value} ${data.unit}` : "Not recorded"}
          </strong>
        </div>
        {data.delta !== null && (
          <div className="radar-tooltip-row">
            <span>Change:</span>
            <strong style={{ color: data.delta > 0 ? "#f87171" : "#4ade80" }}>
              {data.delta > 0 ? `+${data.delta}` : data.delta} {data.unit} ({data.percent_change > 0 ? `+${data.percent_change}` : data.percent_change}%)
            </strong>
          </div>
        )}
      </div>
    );
  }
  return null;
}

export default function HealthChangeRadar({ patientId: propPatientId = null }) {
  const navigate = useNavigate();
  const { selectedPatientId, selectedPatient } = usePatient();
  const effectivePatientId = propPatientId || selectedPatientId;

  const [radarData, setRadarData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedMetricKey, setSelectedMetricKey] = useState(null);

  useEffect(() => {
    let active = true;

    async function loadRadar() {
      if (!effectivePatientId) {
        setRadarData(null);
        return;
      }

      setLoading(true);
      setError("");

      try {
        const response = await authFetch(`${API_URL}/patients/${effectivePatientId}/health-radar`);
        if (!response.ok) {
          throw new Error(`Failed to load Health Change Radar (${response.status})`);
        }
        const data = await response.json();
        if (active) {
          setRadarData(data);
          if (data.radar_metrics && data.radar_metrics.length > 0) {
            setSelectedMetricKey(data.radar_metrics[0].key);
          }
        }
      } catch (err) {
        if (active) {
          setError(err.message || "Could not connect to health radar decision support service.");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadRadar();

    return () => {
      active = false;
    };
  }, [effectivePatientId]);

  const summary = radarData?.summary;
  const metrics = radarData?.radar_metrics || [];

  // Transform metrics for Recharts Radar
  const chartData = useMemo(() => {
    return metrics.map((m) => ({
      key: m.key,
      label: m.label,
      unit: m.unit,
      baseline_score: m.baseline_score ?? 0,
      current_score: m.current_score ?? 0,
      baseline_value: m.baseline_value,
      baseline_date: m.baseline_date,
      current_value: m.current_value,
      current_date: m.current_date,
      delta: m.delta,
      percent_change: m.percent_change,
    }));
  }, [metrics]);

  const activeMetric = useMemo(() => {
    if (!selectedMetricKey) return metrics[0] || null;
    return metrics.find((m) => m.key === selectedMetricKey) || metrics[0] || null;
  }, [metrics, selectedMetricKey]);

  function getStatusClass(status) {
    if (status === "ATTENTION_REQUIRED") return "attention";
    if (status === "MONITORING_RECOMMENDED") return "monitoring";
    if (status === "STABLE_TRAJECTORY") return "stable";
    return "insufficient";
  }

  function getAlertBadgeClass(alertLevel) {
    if (alertLevel === "HIGH_ATTENTION") return "high";
    if (alertLevel === "MODERATE_ATTENTION") return "moderate";
    if (alertLevel === "STABLE") return "stable";
    return "gap";
  }

  function handleAskCopilot() {
    if (!effectivePatientId) return;
    const shiftText = activeMetric
      ? `Can you analyze the longitudinal change in ${activeMetric.label} from ${activeMetric.baseline_value} to ${activeMetric.current_value} ${activeMetric.unit}?`
      : "Can you summarize the major longitudinal vital sign shifts for this patient?";
    navigate(`/copilot?patientId=${effectivePatientId}&question=${encodeURIComponent(shiftText)}`);
  }

  if (!effectivePatientId) {
    return (
      <div className="health-radar-container">
        <div className="radar-header-card">
          <div className="radar-header-left">
            <span className="radar-eyebrow">
              <Activity size={14} /> DECISION SUPPORT
            </span>
            <h2 className="radar-title">Health Change Radar</h2>
            <p className="radar-subtitle">Select an active patient to visualize longitudinal multidimensional shifts.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="health-radar-container" id="health-change-radar">
      {/* Header & Overall Status */}
      <div className="radar-header-card">
        <div className="radar-header-left">
          <span className="radar-eyebrow">
            <TrendingUp size={15} /> UNIQUE FEATURE · HEALTH CHANGE RADAR
          </span>
          <h2 className="radar-title">
            Longitudinal Trajectory · {summary?.patient_name || selectedPatient?.name || `Patient #${effectivePatientId}`}
          </h2>
          <p className="radar-subtitle">
            Multidimensional comparison of baseline vs. current physiological parameters with explainable change calculations.
          </p>
        </div>

        {summary && (
          <span className={`radar-status-badge ${getStatusClass(summary.overall_status)}`}>
            {summary.overall_status === "ATTENTION_REQUIRED" && <AlertTriangle size={15} />}
            {summary.overall_status === "MONITORING_RECOMMENDED" && <Info size={15} />}
            {summary.overall_status === "STABLE_TRAJECTORY" && <CheckCircle2 size={15} />}
            {summary.overall_status.replace(/_/g, " ")}
          </span>
        )}
      </div>

      {loading && (
        <div className="radar-evidence-card">
          <p className="radar-narrative-text">Analyzing longitudinal measurements and computing radar trajectories...</p>
        </div>
      )}

      {error && (
        <div className="radar-evidence-card" style={{ borderLeftColor: "#ef4444" }}>
          <p className="radar-narrative-text" style={{ color: "#b91c1c" }}>
            {error}
          </p>
        </div>
      )}

      {radarData && summary && (
        <>
          {/* Evidence-Backed Patient Summary */}
          <div className="radar-evidence-card">
            <div className="radar-metrics-pill-row">
              <span className="radar-stat-pill">
                <Calendar size={14} /> Visits: <strong>{summary.total_visits_recorded}</strong>
              </span>
              <span className="radar-stat-pill">
                Dimensions Compared: <strong>{summary.metrics_compared_count} / {metrics.length}</strong>
              </span>
              {summary.attention_flags_count > 0 && (
                <span className="radar-stat-pill alert-flag">
                  <AlertTriangle size={14} /> Attention Flags: <strong>{summary.attention_flags_count}</strong>
                </span>
              )}
              {summary.data_gaps_count > 0 && (
                <span className="radar-stat-pill gap-flag">
                  <Info size={14} /> Data Gaps: <strong>{summary.data_gaps_count}</strong>
                </span>
              )}
            </div>

            <p className="radar-narrative-text">{summary.evidence_narrative}</p>

            {summary.clinical_action_suggestions && summary.clinical_action_suggestions.length > 0 && (
              <ul className="radar-suggestions-list">
                {summary.clinical_action_suggestions.map((sugg, idx) => (
                  <li key={idx}>{sugg}</li>
                ))}
              </ul>
            )}
          </div>

          {/* Radar Visualization & Metric Cards Split */}
          <div className="radar-visual-grid">
            {/* Left: Recharts Radar */}
            <div className="radar-chart-card">
              <h3>Physiological Dimension Radar</h3>
              <span className="radar-chart-caption">
                Standardized 0–100 scale. Blue: Baseline Visit | Purple: Latest Visit
              </span>

              <ResponsiveContainer width="100%" height={340}>
                <RadarChart cx="50%" cy="50%" outerRadius="75%" data={chartData}>
                  <PolarGrid stroke="#cbd5e1" strokeDasharray="3 3" />
                  <PolarAngleAxis dataKey="label" tick={{ fill: "#334155", fontSize: 11, fontWeight: 600 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="#94a3b8" />
                  <Radar
                    name={`Baseline (${summary.baseline_visit_date || "Initial"})`}
                    dataKey="baseline_score"
                    stroke="#087f8c"
                    fill="#087f8c"
                    fillOpacity={0.25}
                  />
                  <Radar
                    name={`Current (${summary.current_visit_date || "Latest"})`}
                    dataKey="current_score"
                    stroke="#8b5cf6"
                    fill="#8b5cf6"
                    fillOpacity={0.35}
                  />
                  <Tooltip content={<CustomRadarTooltip />} />
                  <Legend wrapperStyle={{ paddingTop: 8, fontSize: "0.82rem" }} />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            {/* Right: Explainable Change Alert Cards */}
            <div className="radar-cards-column">
              {metrics.map((m) => {
                const isSelected = selectedMetricKey === m.key;
                return (
                  <div
                    key={m.key}
                    className={`radar-metric-card ${isSelected ? "active-selected" : ""}`}
                    onClick={() => setSelectedMetricKey(m.key)}
                  >
                    <div className="metric-card-header">
                      <span className="metric-card-label">{m.label}</span>
                      <span className={`metric-card-badge ${getAlertBadgeClass(m.alert_level)}`}>
                        {m.alert_level.replace(/_/g, " ")}
                      </span>
                    </div>

                    <div className="metric-card-formula">
                      {m.calculation_formula}
                    </div>

                    <p className="metric-card-reason">{m.clinical_reason}</p>

                    <div className="metric-card-values-row">
                      <span>Baseline: <strong>{m.baseline_value !== null ? `${m.baseline_value} ${m.unit}` : "None"}</strong></span>
                      <span>Latest: <strong>{m.current_value !== null ? `${m.current_value} ${m.unit}` : "Missing"}</strong></span>
                      <span>Delta: <strong>{m.delta !== null ? `${m.delta > 0 ? "+" : ""}${m.delta} ${m.unit}` : "N/A"}</strong></span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Copilot Clinical Consultation Banner */}
          <div className="radar-copilot-banner">
            <div className="radar-copilot-text">
              <BrainCircuit size={20} />
              <span>
                Need AI decision-support on these physiological changes? Query Clinical Copilot with these evidence points.
              </span>
            </div>

            <button type="button" className="radar-copilot-button" onClick={handleAskCopilot}>
              Analyze with Copilot <ArrowRight size={15} />
            </button>
          </div>

          <p className="radar-disclaimer">{summary.disclaimer}</p>
        </>
      )}
    </div>
  );
}
