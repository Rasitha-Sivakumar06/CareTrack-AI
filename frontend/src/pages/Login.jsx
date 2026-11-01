import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  Stethoscope,
  Lock,
  User,
  ArrowRight,
  Eye,
  EyeOff,
  AlertCircle,
  ShieldCheck,
  HeartPulse,
} from "lucide-react";
import "./Login.css";

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated, sessionExpiredNotice, clearSessionNotice } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const destination = location.state?.from?.pathname || "/";

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate(destination, { replace: true });
    }
  }, [isAuthenticated, navigate, destination]);

  async function handleSubmit(e) {
    e.preventDefault();
    setErrorMessage("");
    clearSessionNotice();

    if (!username.trim() || !password) {
      setErrorMessage("Please enter both your username/email and password.");
      return;
    }

    setSubmitting(true);

    try {
      const result = await login(username, password);

      if (result.success) {
        navigate(destination, { replace: true });
      } else {
        setErrorMessage(result.error || "Authentication failed. Please verify credentials.");
      }
    } catch {
      setErrorMessage("An unexpected error occurred during login. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page-container">
      <div className="login-decorative-circle circle-top" />
      <div className="login-decorative-circle circle-bottom" />

      <section className="login-card" aria-labelledby="login-heading">
        <header className="login-brand-header">
          <div className="login-brand-badge">
            <HeartPulse size={13} />
            <span>CareTrack AI Platform</span>
          </div>

          <div className="login-icon-avatar" aria-hidden="true">
            <Stethoscope size={32} />
          </div>

          <h1 id="login-heading">Clinician Sign In</h1>
          <p>
            Authenticate to access longitudinal patient health records, diagnostic timelines, and AI decision support.
          </p>
        </header>

        {sessionExpiredNotice && (
          <div className="login-alert warning" role="alert">
            <AlertCircle size={18} className="login-alert-icon" />
            <span>Your session has expired. Please sign in again to continue your work.</span>
          </div>
        )}

        {errorMessage && (
          <div className="login-alert error" role="alert">
            <AlertCircle size={18} className="login-alert-icon" />
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="login-form" noValidate>
          <div className="form-field-group">
            <label htmlFor="login-username">Username or Email</label>
            <div className="input-with-icon">
              <User size={18} className="input-leading-icon" aria-hidden="true" />
              <input
                id="login-username"
                name="username"
                type="text"
                autoComplete="username"
                className="login-input"
                placeholder="clinician_user or doctor@clinic.org"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={submitting}
                required
                autoFocus
              />
            </div>
          </div>

          <div className="form-field-group">
            <label htmlFor="login-password">Password</label>
            <div className="input-with-icon">
              <Lock size={18} className="input-leading-icon" aria-hidden="true" />
              <input
                id="login-password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                className="login-input"
                placeholder="Enter account password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={submitting}
                required
              />
              <button
                type="button"
                className="password-toggle-btn"
                onClick={() => setShowPassword((prev) => !prev)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                tabIndex={-1}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="login-submit-button"
            disabled={submitting}
          >
            {submitting ? (
              <>
                <span className="live-dot" />
                <span>Authenticating...</span>
              </>
            ) : (
              <>
                <span>Sign In to Workspace</span>
                <ArrowRight size={17} />
              </>
            )}
          </button>
        </form>

        <footer className="login-security-notice">
          <ShieldCheck size={20} className="security-icon" aria-hidden="true" />
          <span>
            Protected Health Information (PHI) access is restricted to authorized clinicians and administrative staff. All sessions are audited.
          </span>
        </footer>

        <div className="login-storage-note">
          CareTrack AI Client Security · Session tokens stored in protected browser storage
        </div>
      </section>
    </main>
  );
}
