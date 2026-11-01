import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  LogOut,
  Languages,
  BookOpen,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  CalendarPlus,
  ArrowRight,
  Sparkles,
  Copy,
  Check,
  Activity,
  Clock,
  ShieldAlert,
} from "lucide-react";
import "./ClinicalCopilot.css";
import { API_URL, authFetch } from "../config";
import { usePatient } from "../context/PatientContext";
import { useAuth } from "../context/AuthContext";
import PatientSelector from "../components/PatientSelector";
import BilingualClinicalSummary from "../components/BilingualClinicalSummary";
import VisitRegistrationModal from "../components/VisitRegistrationModal";

const QUICK_QUESTIONS = [
  "Summarize this patient's medical history.",
  "How have the patient's blood glucose levels changed?",
  "Compare blood pressure across visits.",
  "What were the most recent clinical measurements?",
  "What symptoms and clinical notes were recorded previously?",
  "What medical reports are available?",
];

export default function ClinicalCopilot() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    patients,
    selectedPatientId,
    selectedPatient,
    selectPatient,
    loadingPatients,
  } = usePatient();

  const queryPatientId = searchParams.get("patientId");
  const initialPatientId = queryPatientId || selectedPatientId || "";

  const [patientId, setPatientId] = useState(initialPatientId);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [summaryForTranslation, setSummaryForTranslation] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [voiceSupported] = useState(
    () =>
      typeof window !== "undefined" &&
      Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)
  );
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef(null);

  // Cleanup speech recognition on component unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore cleanup abort errors
        }
        recognitionRef.current = null;
      }
    };
  }, []);

  // Patient longitudinal record status fetched from timeline
  const [historySummary, setHistorySummary] = useState(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [visitModalOpen, setVisitModalOpen] = useState(false);

  // Expanded state for source panels (keyed by message index)
  const [expandedSources, setExpandedSources] = useState({});
  const [copiedIndex, setCopiedIndex] = useState(null);

  // Sync patientId when context or URL changes
  useEffect(() => {
    const targetId = queryPatientId || selectedPatientId;
    if (targetId && targetId !== patientId) {
      setPatientId(targetId);
    }
  }, [queryPatientId, selectedPatientId, patientId]);

  // Load patient longitudinal status whenever patientId changes
  const loadPatientStatus = useCallback(async (idToLoad) => {
    if (!idToLoad || !/^\d+$/.test(idToLoad) || Number(idToLoad) < 1) {
      setHistorySummary(null);
      return;
    }
    setLoadingHistory(true);
    try {
      const response = await authFetch(`${API_URL}/patients/${idToLoad}/timeline`);
      if (response.ok) {
        const timeline = await response.json();
        const visits = Array.isArray(timeline.visits) ? timeline.visits : [];
        let measCount = 0;
        let repCount = 0;
        visits.forEach((v) => {
          if (Array.isArray(v.measurements)) measCount += v.measurements.length;
          if (Array.isArray(v.reports)) repCount += v.reports.length;
        });

        setHistorySummary({
          totalVisits: visits.length,
          totalMeasurements: measCount,
          totalReports: repCount,
          earliestDate: visits.length > 0 ? visits[0].visit_date : null,
          latestDate: visits.length > 0 ? visits[visits.length - 1].visit_date : null,
          hasHistory: visits.length > 0,
        });
      } else {
        setHistorySummary(null);
      }
    } catch {
      setHistorySummary(null);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    if (patientId) {
      loadPatientStatus(patientId);
    } else {
      setHistorySummary(null);
    }
  }, [patientId, loadPatientStatus]);

  function handlePatientSelect(id) {
    setPatientId(id);
    selectPatient(id);
    setSearchParams({ patientId: id });
    setError("");
    setMessages([]); // Clear chat history when switching patients for strict isolation
  }

  function handleQuickQuestion(qText) {
    setQuestion(qText);
    const textarea = document.getElementById("copilot-question");
    if (textarea) textarea.focus();
  }

  function toggleSources(index) {
    setExpandedSources((prev) => ({
      ...prev,
      [index]: !prev[index],
    }));
  }

  async function handleCopyAnswer(text, index) {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2500);
    } catch {
      // Fallback
    }
  }

  async function sendQuestion(event) {
    if (event) event.preventDefault();

    const text = question.trim();
    const id = Number(patientId);

    if (!Number.isInteger(id) || id < 1) {
      setError("Please select a valid patient first.");
      return;
    }

    if (text.length < 3) {
      setError("Please enter a question of at least 3 characters.");
      return;
    }

    // Edge case check: zero visits
    if (historySummary && historySummary.totalVisits === 0) {
      setError("Cannot query: this patient has no recorded clinical visits in CareTrack AI.");
      return;
    }

    // If voice recognition is actively listening, stop it before sending
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // ignore
      }
      recognitionRef.current = null;
      setListening(false);
    }

    setError("");
    setSending(true);
    setQuestion("");

    // Append user question
    const userMsgIndex = messages.length;
    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        text,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);

    try {
      const response = await authFetch(`${API_URL}/rag/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          patient_id: id,
          question: text,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        let errorMsg = "The RAG Assistant could not generate a response. Please try again.";
        if (response.status === 404) {
          errorMsg = "Patient not found. Please re-verify the active patient.";
        } else if (response.status === 422) {
          errorMsg = "Invalid query parameters submitted.";
        } else if (response.status === 502) {
          errorMsg = "The AI service is temporarily unavailable. Please try again shortly.";
        } else if (typeof data.detail === "string") {
          errorMsg = data.detail;
        }
        throw new Error(errorMsg);
      }

      // Automatically expand sources on first answer
      const newMsgIndex = userMsgIndex + 1;
      setExpandedSources((prev) => ({
        ...prev,
        [newMsgIndex]: true,
      }));

      // Update history status from actual API response data_summary
      if (data.data_summary) {
        setHistorySummary((prev) => ({
          ...prev,
          totalVisits: data.data_summary.total_visits_retrieved,
          totalMeasurements: data.data_summary.total_measurements_retrieved,
          totalReports: data.data_summary.total_reports_retrieved,
          earliestDate: data.data_summary.earliest_visit_date,
          latestDate: data.data_summary.latest_visit_date,
          hasHistory: data.data_summary.total_visits_retrieved > 0,
        }));
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.answer || "No answer was returned.",
          patientName: data.patient_name,
          sources: Array.isArray(data.sources) ? data.sources : [],
          dataSummary: data.data_summary,
          retrievalMethod: data.retrieval_method,
          disclaimer: data.disclaimer,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } catch (err) {
      setError(
        err.message ||
          "Unable to connect to the backend. Check that the API server is running."
      );
    } finally {
      setSending(false);
    }
  }

  function stopVoiceInput() {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (err) {
        console.warn("Speech recognition stop error:", err);
      }
    }
  }

  function startVoiceInput() {
    const SpeechRecognitionAPI =
      typeof window !== "undefined"
        ? window.SpeechRecognition || window.webkitSpeechRecognition
        : null;

    if (!SpeechRecognitionAPI) {
      setError(
        "Voice input is not supported in this browser. Please use Google Chrome or Microsoft Edge."
      );
      return;
    }

    // Clean up any existing active recognition instance before starting anew
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // ignore
      }
      recognitionRef.current = null;
    }

    try {
      const recognition = new SpeechRecognitionAPI();
      recognitionRef.current = recognition;

      // Configuration
      // Fallback: use user's browser language if English-based, otherwise default to en-IN / en-US
      const browserLang =
        typeof navigator !== "undefined" && navigator.language
          ? navigator.language
          : "en-US";
      recognition.lang = browserLang.startsWith("en") ? browserLang : "en-IN";
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setListening(true);
        setError("");
      };

      recognition.onresult = (event) => {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal || !recognition.continuous) {
            transcript += event.results[i][0].transcript;
          }
        }
        const cleanTranscript = transcript.trim();
        if (cleanTranscript) {
          setQuestion((prev) => {
            const trimmedPrev = prev ? prev.trim() : "";
            return trimmedPrev ? `${trimmedPrev} ${cleanTranscript}` : cleanTranscript;
          });
          setError("");
        }
      };

      recognition.onerror = (event) => {
        const errorCode = event.error || "unknown";
        console.error("CareTrack AI Speech Recognition Error:", errorCode, event);

        // Map browser error codes to clear, helpful user guidance
        switch (errorCode) {
          case "no-speech":
            setError(
              "No speech was detected. Please click the microphone and speak clearly."
            );
            break;
          case "not-allowed":
            setError(
              "Microphone permission was denied. Please allow microphone access in Chrome's address bar settings."
            );
            break;
          case "service-not-allowed":
            setError(
              "Speech recognition service is disabled or blocked by browser/system policy."
            );
            break;
          case "audio-capture":
            setError(
              "Microphone audio capture failed. Please check your microphone connection and Windows audio input settings."
            );
            break;
          case "network":
            setError(
              "Speech recognition service network error. Chrome could not reach Google speech services. Please check your internet connection or type your question."
            );
            break;
          case "language-not-supported":
            setError(
              "Speech recognition language is not supported by your browser. Please type your question."
            );
            break;
          case "aborted":
            // Normal user or programmatic cancellation; do not display error banner
            break;
          default:
            setError(`Voice input error (${errorCode}). Please type your question.`);
            break;
        }
      };

      recognition.onend = () => {
        setListening(false);
        recognitionRef.current = null;
      };

      recognition.start();
    } catch (err) {
      console.error("CareTrack AI Speech Recognition Start Exception:", err);
      setError(
        `Unable to activate microphone (${err.name || "Error"}: ${err.message || "Failed to start"}). Please type your question.`
      );
      setListening(false);
      recognitionRef.current = null;
    }
  }

  function toggleVoiceInput() {
    if (listening) {
      stopVoiceInput();
    } else {
      startVoiceInput();
    }
  }

  function formatAnswerWithCitations(text) {
    if (!text) return null;
    return text.split("\n").map((line, lineIndex) => {
      // Highlight bold text (**bold**) and citations ([S1], [S2])
      const parts = line.split(/(\*\*.*?\*\*|\[S\d+(?:,\s*S\d+)*\])/g);
      return (
        <span key={lineIndex} className="copilot-line">
          {parts.map((part, partIndex) => {
            if (part.startsWith("**") && part.endsWith("**")) {
              return (
                <strong key={partIndex} className="copilot-strong">
                  {part.slice(2, -2)}
                </strong>
              );
            }
            if (/^\[S\d+(?:,\s*S\d+)*\]$/.test(part)) {
              return (
                <span key={partIndex} className="citation-badge" title="Grounded Clinical Source Citation">
                  {part}
                </span>
              );
            }
            return part.replace(/^#{1,6}\s/, "");
          })}
          {"\n"}
        </span>
      );
    });
  }

  const activePatientName =
    selectedPatient?.name ||
    patients.find((p) => String(p.id) === String(patientId))?.name ||
    (patientId ? `Patient #${patientId}` : "");

  return (
    <main className="copilot-page">
      {/* Header */}
      <header className="copilot-header">
        <button
          type="button"
          className="copilot-back"
          onClick={() => navigate("/")}
        >
          ← Dashboard
        </button>

        <div className="header-actions-group">
          <span className="copilot-status">
            <span className="copilot-status-dot" />
            CareTrack AI · Patient History RAG Assistant
          </span>

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

      {/* Hero Section */}
      <section className="copilot-hero">
        <span className="copilot-eyebrow">
          CARETRACK AI · CLINICAL DECISION SUPPORT & RAG
        </span>

        <h1>Patient History RAG Assistant</h1>

        <p>
          Evidence-based longitudinal retrieval grounded exclusively in
          documented clinical encounters, physiological measurements, and
          medical reports.
        </p>

        {/* Prominent Clinical Safety Notice */}
        <div className="safety-warning-banner" role="note">
          <ShieldAlert size={16} />
          <span>
            <strong>Clinical Safety Notice:</strong> CareTrack AI is a clinical
            decision-support tool, not an autonomous diagnostic system.
            AI-generated information must be reviewed and verified by a
            qualified healthcare professional.
          </span>
        </div>
      </section>

      {/* Patient Selector */}
      <PatientSelector onPatientChange={handlePatientSelect} />

      {/* Patient Longitudinal Record Status Bar */}
      {patientId && (
        <section className="rag-status-card" aria-label="Patient Clinical History Status">
          <div className="rag-status-header">
            <div className="rag-status-patient">
              <Activity size={18} className="rag-status-icon" />
              <div>
                <h3>{activePatientName}</h3>
                <span className="rag-status-meta">
                  Patient ID: #{patientId} · Location: {selectedPatient?.location || "Documented Clinic"}
                </span>
              </div>
            </div>

            <span className="rag-engine-badge">
              <Sparkles size={13} />
              <span>SLCR-RAG · Structured Longitudinal Retrieval</span>
            </span>
          </div>

          <div className="rag-metrics-grid">
            <div className="rag-metric-item">
              <span className="rag-metric-label">Visits Retrieved</span>
              <strong className="rag-metric-val">
                {loadingHistory ? "..." : (historySummary?.totalVisits ?? 0)}
              </strong>
            </div>

            <div className="rag-metric-item">
              <span className="rag-metric-label">Clinical Measurements</span>
              <strong className="rag-metric-val">
                {loadingHistory ? "..." : (historySummary?.totalMeasurements ?? 0)}
              </strong>
            </div>

            <div className="rag-metric-item">
              <span className="rag-metric-label">Medical Reports</span>
              <strong className="rag-metric-val">
                {loadingHistory ? "..." : (historySummary?.totalReports ?? 0)}
              </strong>
            </div>

            <div className="rag-metric-item">
              <span className="rag-metric-label">Timeline Span</span>
              <strong className="rag-metric-val small">
                {loadingHistory ? (
                  "Loading..."
                ) : historySummary?.earliestDate ? (
                  `${historySummary.earliestDate} → ${historySummary.latestDate || "Present"}`
                ) : (
                  "No visits on record"
                )}
              </strong>
            </div>
          </div>
        </section>
      )}

      {/* Empty State when Patient Has Zero Visits */}
      {patientId && historySummary && historySummary.totalVisits === 0 && !loadingHistory && (
        <section className="empty-history-banner" role="alert">
          <div className="empty-history-icon">
            <AlertCircle size={28} />
          </div>
          <div className="empty-history-content">
            <h4>No Documented Clinical History Found</h4>
            <p>
              Patient <strong>{activePatientName}</strong> has no documented
              clinical visits, measurements, or medical reports in CareTrack AI.
              The RAG Assistant requires historical records to formulate
              grounded answers.
            </p>
            <div className="empty-history-actions">
              <button
                type="button"
                className="empty-action-primary"
                onClick={() => setVisitModalOpen(true)}
              >
                <CalendarPlus size={15} />
                <span>Register First Visit</span>
              </button>
              <button
                type="button"
                className="empty-action-secondary"
                onClick={() => navigate(`/timeline?patientId=${patientId}`)}
              >
                <span>Open Patient Timeline</span>
                <ArrowRight size={14} />
              </button>
            </div>
          </div>
        </section>
      )}

      {/* Main Workspace */}
      <section className="copilot-workspace">
        {/* Quick Clinical Questions */}
        <div className="quick-questions-panel">
          <span className="quick-questions-title">
            <Sparkles size={14} />
            <span>Suggested Clinical Questions for {activePatientName || "Active Patient"}:</span>
          </span>
          <div className="quick-questions-grid">
            {QUICK_QUESTIONS.map((qText, qIdx) => (
              <button
                key={qIdx}
                type="button"
                className="quick-question-btn"
                onClick={() => handleQuickQuestion(qText)}
                disabled={sending || (historySummary && historySummary.totalVisits === 0)}
              >
                {qText}
              </button>
            ))}
          </div>
        </div>

        {/* Chat Thread */}
        <div className="copilot-chat" aria-live="polite">
          {messages.length === 0 ? (
            <div className="copilot-empty">
              <div className="copilot-orb">✦</div>
              <h2>How can I assist with this patient's medical history?</h2>
              <p>
                Ask questions regarding documented symptoms, clinical notes,
                longitudinal vitals, blood glucose changes, and attached lab
                reports. Every answer cites verified source records.
              </p>
            </div>
          ) : (
            messages.map((message, index) => (
              <article
                key={`${index}-${message.role}`}
                className={`copilot-message ${message.role}`}
              >
                <div className="copilot-message-header">
                  <span className="copilot-message-label">
                    {message.role === "user"
                      ? "Treating Clinician"
                      : `CareTrack AI · Grounded Synthesis (${message.patientName || activePatientName})`}
                  </span>
                  {message.timestamp && (
                    <span className="copilot-message-time">
                      <Clock size={11} />
                      <span>{message.timestamp}</span>
                    </span>
                  )}
                </div>

                <div className="copilot-message-body">
                  {message.role === "assistant"
                    ? formatAnswerWithCitations(message.text)
                    : message.text}
                </div>

                {/* Assistant Source Records Panel & Actions */}
                {message.role === "assistant" && (
                  <div className="copilot-message-footer">
                    {/* Expandable Source Records Drawer */}
                    {Array.isArray(message.sources) && message.sources.length > 0 && (
                      <div className="rag-sources-container">
                        <button
                          type="button"
                          className="rag-sources-toggle-btn"
                          onClick={() => toggleSources(index)}
                          aria-expanded={Boolean(expandedSources[index])}
                        >
                          <BookOpen size={14} />
                          <span>
                            Clinical Sources Used ({message.sources.length} record{message.sources.length > 1 ? "s" : ""})
                          </span>
                          {expandedSources[index] ? (
                            <ChevronUp size={15} />
                          ) : (
                            <ChevronDown size={15} />
                          )}
                        </button>

                        {expandedSources[index] && (
                          <div className="rag-sources-list">
                            {message.sources.map((src, srcIdx) => (
                              <div key={srcIdx} className="rag-source-card">
                                <div className="rag-source-card-header">
                                  <span className="rag-source-id-tag">
                                    {src.source_id}
                                  </span>
                                  <span className={`rag-source-type-tag ${src.record_type?.replace(/\s+/g, "-").toLowerCase()}`}>
                                    {src.record_type}
                                  </span>
                                  <span className="rag-source-visit-tag">
                                    {src.visit_id ? `Visit #${src.visit_id}` : "Unattached"}
                                  </span>
                                  <span className="rag-source-date-tag">
                                    {src.visit_date || "Date unrecorded"}
                                  </span>
                                </div>

                                <p className="rag-source-summary">{src.summary}</p>

                                {/* Structured Clinical Parameters */}
                                {src.parameters && Object.keys(src.parameters).length > 0 && (
                                  <div className="rag-source-params">
                                    {Object.entries(src.parameters)
                                      .filter(([, v]) => v !== null && v !== undefined && v !== "")
                                      .map(([paramKey, paramVal]) => (
                                        <span key={paramKey} className="rag-param-chip">
                                          <strong className="param-k">{paramKey.replace(/_/g, " ")}:</strong>{" "}
                                          <span className="param-v">{String(paramVal)}</span>
                                        </span>
                                      ))}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Actions: Copy & Translate */}
                    <div className="copilot-message-actions">
                      <button
                        type="button"
                        className="copilot-copy-btn"
                        onClick={() => handleCopyAnswer(message.text, index)}
                        title="Copy answer to clipboard"
                      >
                        {copiedIndex === index ? (
                          <>
                            <Check size={13} />
                            <span>Copied</span>
                          </>
                        ) : (
                          <>
                            <Copy size={13} />
                            <span>Copy</span>
                          </>
                        )}
                      </button>

                      <button
                        type="button"
                        className="copilot-translate-action-btn"
                        onClick={() => {
                          setSummaryForTranslation(message.text);
                          const el = document.getElementById("bilingual-translator-anchor");
                          if (el) el.scrollIntoView({ behavior: "smooth" });
                        }}
                        title="Send this clinical answer to the Bilingual Clinical Translator"
                      >
                        <Languages size={14} />
                        <span>Translate to Tamil (தமிழ்)</span>
                      </button>
                    </div>
                  </div>
                )}
              </article>
            ))
          )}

          {sending && (
            <div className="copilot-loading-card" role="status">
              <span className="copilot-spinner" />
              <span>
                Retrieving longitudinal records for {activePatientName} and generating
                grounded synthesis...
              </span>
            </div>
          )}
        </div>

        {error && (
          <div className="copilot-error" role="alert">
            <AlertCircle size={15} />
            <span>{error}</span>
          </div>
        )}

        {/* Question Composer */}
        <form className="copilot-composer" onSubmit={sendQuestion}>
          <label htmlFor="copilot-question">
            Ask about {activePatientName ? `${activePatientName}'s` : "the patient's"} medical history
          </label>

          <textarea
            id="copilot-question"
            rows={3}
            maxLength={2000}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={
              historySummary && historySummary.totalVisits === 0
                ? "This patient has no recorded visits yet. Register a visit above to enable questions."
                : "e.g. Compare the patient's blood pressure and glucose across documented visits."
            }
            disabled={
              sending ||
              loadingPatients ||
              !patientId ||
              (historySummary && historySummary.totalVisits === 0)
            }
          />

          <div className="copilot-composer-footer">
            <div className="copilot-tools">
              {voiceSupported && (
                <button
                  type="button"
                  className={`copilot-voice-button ${listening ? "listening" : ""}`}
                  onClick={toggleVoiceInput}
                  disabled={
                    sending ||
                    !patientId ||
                    (historySummary && historySummary.totalVisits === 0)
                  }
                  title={
                    listening
                      ? "Click to stop microphone recording"
                      : "Speak your question using microphone"
                  }
                  aria-pressed={listening}
                >
                  {listening ? "⏹ Stop Listening" : "🎙 Voice input"}
                </button>
              )}

              <span className="char-count">{question.length}/2000</span>
            </div>

            <button
              type="submit"
              className="copilot-send"
              disabled={
                sending ||
                loadingPatients ||
                !patientId ||
                question.trim().length < 3 ||
                (historySummary && historySummary.totalVisits === 0)
              }
            >
              {sending ? "Synthesizing..." : "Ask RAG Assistant ↑"}
            </button>
          </div>
        </form>
      </section>

      {/* Bilingual Clinical Summary (English ⇄ Tamil) */}
      <div id="bilingual-translator-anchor">
        <BilingualClinicalSummary
          suggestedText={summaryForTranslation}
          patientName={activePatientName}
        />
      </div>

      {/* Visit Registration Modal for zero-visit patients */}
      <VisitRegistrationModal
        isOpen={visitModalOpen}
        onClose={() => setVisitModalOpen(false)}
        initialPatientId={patientId}
        onVisitCreated={() => {
          setVisitModalOpen(false);
          loadPatientStatus(patientId);
        }}
      />

      {/* Footer Disclaimer */}
      <footer className="copilot-disclaimer">
        <strong>CareTrack AI · Clinical Decision Support Prototype</strong>
        <p>
          This assistant retrieves longitudinal records to support clinical review.
          It does not diagnose conditions, prescribe medications, or replace qualified
          medical judgment. Verify all critical findings against original records.
        </p>
      </footer>
    </main>
  );
}
