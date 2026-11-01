import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { HeartPulse } from "lucide-react";

export default function ProtectedRoute({ children }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="auth-loading-screen" style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--background, #f4f8fc)",
        color: "var(--text, #17324d)"
      }}>
        <div style={{
          textAlign: "center",
          padding: "32px",
          borderRadius: "16px",
          background: "#ffffff",
          boxShadow: "0 10px 30px rgba(8, 127, 140, 0.08)",
          border: "1px solid #dce7f0",
          maxWidth: "360px"
        }}>
          <div style={{
            width: "56px",
            height: "56px",
            borderRadius: "50%",
            background: "rgba(8, 127, 140, 0.1)",
            color: "#087f8c",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: "16px"
          }}>
            <HeartPulse size={28} className="pulse-icon" />
          </div>
          <h3 style={{ margin: "0 0 8px", fontSize: "17px", fontWeight: "700" }}>
            CareTrack AI
          </h3>
          <p style={{ margin: 0, fontSize: "13px", color: "var(--muted, #71849a)" }}>
            Verifying clinical session credentials...
          </p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
