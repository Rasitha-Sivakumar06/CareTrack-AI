import { useState, useEffect } from "react";
import {
  Languages,
  ArrowRightLeft,
  Copy,
  Check,
  AlertCircle,
  Sparkles,
  RefreshCw,
  FileText,
  ShieldAlert,
} from "lucide-react";
import { API_URL, authFetch } from "../config";
import "./BilingualClinicalSummary.css";

export default function BilingualClinicalSummary({
  suggestedText = "",
  patientName = "",
}) {
  const [sourceLang, setSourceLang] = useState("en");
  const [targetLang, setTargetLang] = useState("ta");
  const [inputText, setInputText] = useState("");
  const [translationResult, setTranslationResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copiedOriginal, setCopiedOriginal] = useState(false);
  const [copiedTranslated, setCopiedTranslated] = useState(false);

  // If a suggestedText was provided, update the input
  useEffect(() => {
    if (suggestedText) {
      setInputText(suggestedText);
    }
  }, [suggestedText]);

  function handleSwapLanguages() {
    const prevSource = sourceLang;
    const prevTarget = targetLang;
    setSourceLang(prevTarget);
    setTargetLang(prevSource);

    // If a translation exists, swap the text as well for seamless round-trip
    if (translationResult?.translated_text) {
      setInputText(translationResult.translated_text);
      setTranslationResult(null);
    }
  }

  function handleSelectDirection(src, tgt) {
    setSourceLang(src);
    setTargetLang(tgt);
  }

  async function handleTranslate(event) {
    if (event) event.preventDefault();

    const text = inputText.trim();
    if (!text) {
      setError("Please enter or paste clinical text to translate.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      const response = await authFetch(
        `${API_URL}/clinical-translation/translate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            text,
            source_language: sourceLang,
            target_language: targetLang,
          }),
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : `Translation request failed (${response.status}).`
        );
      }

      setTranslationResult(data);
    } catch (err) {
      setError(
        err.message ||
          "Could not complete clinical translation. Check backend connectivity."
      );
    } finally {
      setLoading(false);
    }
  }

  function handleCopy(text, type) {
    if (!text) return;
    navigator.clipboard?.writeText(text);
    if (type === "original") {
      setCopiedOriginal(true);
      setTimeout(() => setCopiedOriginal(false), 2000);
    } else {
      setCopiedTranslated(true);
      setTimeout(() => setCopiedTranslated(false), 2000);
    }
  }

  function handleClear() {
    setInputText("");
    setTranslationResult(null);
    setError("");
  }

  return (
    <section className="bilingual-summary-card">
      <div className="bilingual-header">
        <div className="bilingual-title-group">
          <div className="bilingual-icon-orb">
            <Languages size={20} />
          </div>
          <div>
            <div className="bilingual-badge-row">
              <span className="bilingual-eyebrow">
                PHASE 4 · BILINGUAL HEALTHCARE CONTINUITY
              </span>
              <span className="bilingual-ai-tag">
                <Sparkles size={12} />
                AI-Assisted Translation
              </span>
            </div>
            <h2>Bilingual Clinical Summary (English ⇄ தமிழ்)</h2>
            <p>
              Faithfully translate patient-facing notes and clinical summaries
              between English and Tamil while strictly preserving vital signs,
              measurements, drug names, and clinical uncertainty.
            </p>
          </div>
        </div>

        {/* Language selector toggle */}
        <div className="bilingual-direction-selector">
          <button
            type="button"
            className={`direction-tab ${sourceLang === "en" ? "active" : ""}`}
            onClick={() => handleSelectDirection("en", "ta")}
          >
            English → Tamil (தமிழ்)
          </button>

          <button
            type="button"
            className="swap-button"
            onClick={handleSwapLanguages}
            title="Swap translation direction"
          >
            <ArrowRightLeft size={16} />
          </button>

          <button
            type="button"
            className={`direction-tab ${sourceLang === "ta" ? "active" : ""}`}
            onClick={() => handleSelectDirection("ta", "en")}
          >
            Tamil (தமிழ்) → English
          </button>
        </div>
      </div>

      {suggestedText && suggestedText !== inputText && (
        <div className="suggested-source-bar">
          <span className="suggested-icon">
            <FileText size={15} />
          </span>
          <span className="suggested-text">
            Latest Copilot response available for {patientName || "patient"}.
          </span>
          <button
            type="button"
            className="use-suggested-button"
            onClick={() => {
              setInputText(suggestedText);
              setTranslationResult(null);
            }}
          >
            Load into Translator
          </button>
        </div>
      )}

      {/* Editor & Translation Form */}
      <form className="bilingual-form" onSubmit={handleTranslate}>
        <div className="bilingual-input-group">
          <div className="input-header-row">
            <label htmlFor="bilingual-input-textarea">
              Source Text (
              {sourceLang === "en" ? "English" : "Tamil / தமிழ்"})
            </label>
            <div className="input-actions-right">
              {inputText && (
                <button
                  type="button"
                  className="clear-text-btn"
                  onClick={handleClear}
                >
                  Clear
                </button>
              )}
              <span className="char-count">{inputText.length}/5000</span>
            </div>
          </div>

          <textarea
            id="bilingual-input-textarea"
            className="bilingual-textarea"
            rows={4}
            maxLength={5000}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder={
              sourceLang === "en"
                ? "e.g. Patient presented with blood pressure 140/90 mmHg and blood glucose 145 mg/dL. Metformin 500mg prescribed. Follow-up in 4 weeks."
                : "எ.கா. நோயாளிக்கு இரத்த அழுத்தம் 140/90 mmHg மற்றும் இரத்த சர்க்கரை 145 mg/dL. மெட்ஃபோர்மின் (Metformin) 500mg பரிந்துரைக்கப்பட்டது. 4 வாரங்களில் மீண்டும் வரவும்."
            }
            disabled={loading}
          />
        </div>

        <div className="bilingual-action-bar">
          <button
            type="submit"
            className="bilingual-translate-btn"
            disabled={loading || !inputText.trim()}
          >
            {loading ? (
              <>
                <RefreshCw size={16} className="spin" />
                <span>Translating with Clinical Precision...</span>
              </>
            ) : (
              <>
                <Languages size={16} />
                <span>
                  Translate to {targetLang === "ta" ? "Tamil (தமிழ்)" : "English"}
                </span>
              </>
            )}
          </button>
        </div>
      </form>

      {error && (
        <div className="bilingual-error-banner" role="alert">
          <AlertCircle size={18} />
          <div>
            <strong>Translation Error: </strong>
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Side-by-side or stacked Dual Display */}
      {translationResult && (
        <div className="bilingual-comparison-grid">
          {/* Original Card */}
          <div className="bilingual-card original-card">
            <div className="bilingual-card-header">
              <div className="bilingual-card-title">
                <span className="lang-tag">
                  {translationResult.source_language === "en"
                    ? "English Original"
                    : "தமிழ் (Tamil) அசல்"}
                </span>
              </div>
              <button
                type="button"
                className="bilingual-copy-btn"
                onClick={() =>
                  handleCopy(translationResult.original_text, "original")
                }
                title="Copy original text"
              >
                {copiedOriginal ? <Check size={14} /> : <Copy size={14} />}
                <span>{copiedOriginal ? "Copied" : "Copy"}</span>
              </button>
            </div>
            <div className="bilingual-card-content">
              {translationResult.original_text}
            </div>
          </div>

          {/* Translated Card */}
          <div className="bilingual-card translated-card">
            <div className="bilingual-card-header">
              <div className="bilingual-card-title">
                <span className="lang-tag translated-tag">
                  {translationResult.target_language === "ta"
                    ? "தமிழ் மொழிபெயர்ப்பு (Tamil Translation)"
                    : "English Clinical Translation"}
                </span>
              </div>
              <button
                type="button"
                className="bilingual-copy-btn"
                onClick={() =>
                  handleCopy(translationResult.translated_text, "translated")
                }
                title="Copy translated text"
              >
                {copiedTranslated ? <Check size={14} /> : <Copy size={14} />}
                <span>{copiedTranslated ? "Copied" : "Copy"}</span>
              </button>
            </div>
            <div className="bilingual-card-content highlight-content">
              {translationResult.translated_text}
            </div>
          </div>
        </div>
      )}

      {/* Clinical Review & Regulatory Safety Notice */}
      <footer className="bilingual-safety-notice">
        <ShieldAlert size={16} />
        <div>
          <strong>Clinician Verification Mandatory: </strong>
          <span>
            {translationResult?.disclaimer ||
              "AI-assisted clinical translation for healthcare continuity. Must be reviewed and verified by a qualified clinician before patient communication. Vital signs, drug names, dosages, and timeline dates must be verified against source records."}
          </span>
        </div>
      </footer>
    </section>
  );
}
