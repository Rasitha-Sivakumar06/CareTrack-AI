
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  CalendarDays,
  FileText,
  HeartPulse,
  MessageCircle,
  ShieldCheck,
  Stethoscope,
  Users,
  Upload,
  TrendingUp,
  LogOut,
} from "lucide-react";
import PatientSelector from "../components/PatientSelector";
import HealthChangeRadar from "../components/HealthChangeRadar";
import { usePatient } from "../context/PatientContext";
import { useAuth } from "../context/AuthContext";

const actions = [
  {
    title: "Clinical Alerts",
    description: "Screening flags & health urgency dashboard",
    icon: AlertTriangle,
    path: "/alerts",
    color: "red",
  },
  {
    title: "Health Change Radar",
    description: "Multidimensional longitudinal shifts & alerts",
    icon: TrendingUp,
    path: "/radar",
    color: "cyan",
  },
  {
    title: "HealthTrajectory AI",
    description: "Explainable multi-visit change detection & physiological trends",
    icon: BrainCircuit,
    path: "/trajectory",
    color: "cyan",
  },
  {
    title: "Patient Records",
    description: "Explore individual patient histories",
    icon: Users,
    path: "/patients",
    color: "cyan",
  },
  {
    title: "Medical Reports",
    description: "Upload and review medical documents",
    icon: FileText,
    path: "/reports",
    color: "purple",
  },
  {
    title: "Clinical Trends",
    description: "Explore recorded health measurements",
    icon: Activity,
    path: "/trends",
    color: "green",
  },
  {
    title: "Patient Timeline",
    description: "Review visits and medical history",
    icon: CalendarDays,
    path: "/timeline",
    color: "orange",
  },
  {
    title: "Clinical Copilot",
    description: "Ask AI about a patient's medical history",
    icon: MessageCircle,
    path: "/copilot",
    color: "purple",
  },
];

export default function Dashboard({ navigate }) {
  const { selectedPatientId } = usePatient();
  const { user, logout } = useAuth();

  function handleNavigate(path) {
    if (selectedPatientId) {
      navigate(`${path}?patientId=${selectedPatientId}`);
    } else {
      navigate(path);
    }
  }

  return (
    <div className="page-content">
      <header className="page-header">
        <div>
          <span className="eyebrow">
            YOUR HEALTHCARE WORKSPACE
          </span>

          <h1>Dashboard</h1>

          <p>
            One patient. Every visit. A clearer picture of health.
          </p>
        </div>

        <div className="header-actions-group">
          <div className="api-badge">
            <span className="live-dot" />
            Connected workspace
          </div>

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

      <PatientSelector />

      <section className="hero-panel">
        <div className="hero-copy">
          <span className="hero-label">
            <HeartPulse size={15} />
            LONGITUDINAL HEALTHCARE
          </span>

          <h2>
            Better continuity.
            <br />
            Better-informed care.
          </h2>

          <p>
            Bring patient visits, medical reports and clinical
            measurements together in one connected healthcare
            workspace.
          </p>

          <button
            className="primary-button"
            onClick={() => handleNavigate("/patients")}
          >
            Explore patients
            <ArrowRight size={17} />
          </button>
        </div>

        <div className="hero-art">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />

          <div className="medical-glass glass-top">
            <Activity size={23} />
            <span>Clinical signals</span>
            <div className="pulse-line" />
          </div>

          <div className="doctor-illustration">
            <Stethoscope size={76} strokeWidth={1.1} />

            <div className="doctor-heart">
              <HeartPulse size={43} />
            </div>
          </div>

          <div className="medical-glass glass-bottom">
            <BrainCircuit size={21} />
            <span>Health insights</span>
          </div>

          <div className="floating-plus plus-one">+</div>
          <div className="floating-plus plus-two">+</div>
        </div>
      </section>

      <section className="section-block">
        <div className="section-title">
          <div>
            <span className="eyebrow">QUICK ACCESS</span>
            <h2>Everything in its place</h2>
          </div>

          <span className="section-caption">
            Choose a workspace
          </span>
        </div>

        <div className="action-grid">
          {actions.map((action) => {
            const Icon = action.icon;

            return (
              <button
                className="action-card"
                key={action.title}
                onClick={() => handleNavigate(action.path)}
              >
                <span className={`action-icon ${action.color}`}>
                  <Icon size={23} />
                </span>

                <span className="action-text">
                  <strong>{action.title}</strong>
                  <span>{action.description}</span>
                </span>

                <ArrowRight
                  className="action-arrow"
                  size={19}
                />
              </button>
            );
          })}
        </div>
      </section>

      {/* HEALTH CHANGE RADAR — UNIQUE DECISION SUPPORT FEATURE */}
      <HealthChangeRadar />

      <section className="dashboard-bottom">
        <article className="feature-panel">
          <div className="feature-icon">
            <ShieldCheck size={27} />
          </div>

          <div>
            <span className="eyebrow">
              RESPONSIBLE HEALTHCARE
            </span>

            <h3>Care that sees the bigger picture.</h3>

            <p>
              Review changes across visits. Keep clinical information
              organized. Support decisions with a longitudinal view
              of the patient.
            </p>
          </div>
        </article>

        <article className="upload-panel">
          <div className="upload-icon">
            <Upload size={24} />
          </div>

          <h3>Have a medical report?</h3>

          <p>
            Open the report workspace to manage patient documents.
          </p>

          <button
            className="text-button"
            onClick={() => navigate("/reports")}
          >
            Open reports
            <ArrowRight size={16} />
          </button>
        </article>
      </section>

      <footer className="page-footer">
        <span>
          <HeartPulse size={15} />
          CareTrack AI
        </span>

        <span>
          Clinical decision support · Not a diagnostic system
        </span>
      </footer>
    </div>
  );
}
