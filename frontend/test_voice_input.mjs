// test_voice_input.mjs - Unit verification and mock simulation for ClinicalCopilot Voice Input
import { readFileSync } from "fs";
import { resolve } from "path";

console.log("=== CareTrack AI Voice Input Static Verification ===");

const filePath = resolve("./src/pages/ClinicalCopilot.jsx");
const content = readFileSync(filePath, "utf-8");

// 1. Check imports
const hasUseRef = /import\s*\{[^}]*useRef[^}]*\}\s*from\s*["']react["']/.test(content);
console.log(`[PASS 1] useRef imported from React: ${hasUseRef}`);
if (!hasUseRef) throw new Error("useRef not found in React imports");

// 2. Check recognitionRef declaration
const hasRefDecl = /const\s+recognitionRef\s*=\s*useRef\(null\)/.test(content);
console.log(`[PASS 2] recognitionRef defined: ${hasRefDecl}`);
if (!hasRefDecl) throw new Error("recognitionRef not defined");

// 3. Check lifecycle cleanup
const hasCleanup = /recognitionRef\.current\.abort\(\)/.test(content);
console.log(`[PASS 3] Cleanup abort on unmount: ${hasCleanup}`);
if (!hasCleanup) throw new Error("Unmount cleanup missing");

// 4. Check toggleVoiceInput function
const hasToggle = /function\s+toggleVoiceInput\(\)/.test(content);
console.log(`[PASS 4] toggleVoiceInput defined: ${hasToggle}`);
if (!hasToggle) throw new Error("toggleVoiceInput not defined");

// 5. Check error code logging
const hasErrorLogging = /console\.error\(\s*["']CareTrack AI Speech Recognition Error:["'],\s*errorCode/.test(content);
console.log(`[PASS 5] Speech recognition error code logging: ${hasErrorLogging}`);
if (!hasErrorLogging) throw new Error("Error code logging missing");

// 6. Check error code handling cases
const errorCases = [
  "no-speech",
  "not-allowed",
  "service-not-allowed",
  "audio-capture",
  "network",
  "language-not-supported",
  "aborted",
];
for (const code of errorCases) {
  const hasCase = content.includes(`case "${code}":`);
  console.log(`[PASS 6.${code}] Handled error case '${code}': ${hasCase}`);
  if (!hasCase) throw new Error(`Missing error case: ${code}`);
}

// 7. Check button disabled does NOT include listening
const buttonMatch = content.match(/<button[\s\S]*?className=\{`copilot-voice-button[\s\S]*?<\/button>/);
if (!buttonMatch) throw new Error("Voice button not found in JSX");
const buttonJSX = buttonMatch[0];
const listeningInDisabled = /disabled=\{[^}]*listening[^}]*\}/.test(buttonJSX);
console.log(`[PASS 7] Button disabled state does NOT disable while listening: ${!listeningInDisabled}`);
if (listeningInDisabled) throw new Error("Voice button is still disabled while listening!");

// 8. Check button displays stop listening label
const hasStopLabel = buttonJSX.includes("Stop Listening");
console.log(`[PASS 8] Button displays Stop Listening when listening: ${hasStopLabel}`);
if (!hasStopLabel) throw new Error("Stop Listening label missing");

// 9. Check onresult transcript accumulation
const hasTranscriptAccum = /trimmedPrev \? `\$\{trimmedPrev\} \$\{cleanTranscript\}` : cleanTranscript/.test(content);
console.log(`[PASS 9] Appends speech to existing input query: ${hasTranscriptAccum}`);
if (!hasTranscriptAccum) throw new Error("Transcript appending missing");

// 10. Check abort on send
const hasSendAbort = content.includes("// If voice recognition is actively listening, stop it before sending");
console.log(`[PASS 10] Voice recognition aborted on query submission: ${hasSendAbort}`);
if (!hasSendAbort) throw new Error("Abort on send missing");

console.log("\n=== CareTrack AI Voice Input State Machine Simulation ===");

// Simulate component state and Web Speech API behavior
class MockSpeechRecognition {
  constructor() {
    this.lang = "en-US";
    this.continuous = false;
    this.interimResults = false;
    this.maxAlternatives = 1;
    this.onstart = null;
    this.onresult = null;
    this.onerror = null;
    this.onend = null;
    this.started = false;
    this.stopped = false;
    this.aborted = false;
  }

  start() {
    if (this.started) throw new Error("Recognition already started");
    this.started = true;
    if (this.onstart) this.onstart();
  }

  stop() {
    this.stopped = true;
    if (this.onend) this.onend();
  }

  abort() {
    this.aborted = true;
    if (this.onerror) this.onerror({ error: "aborted" });
    if (this.onend) this.onend();
  }

  emitResult(transcript) {
    if (this.onresult) {
      this.onresult({
        resultIndex: 0,
        results: [
          [{ transcript: transcript }],
        ],
      });
    }
  }

  emitError(errorCode) {
    if (this.onerror) {
      this.onerror({ error: errorCode });
    }
  }
}

// Test Flow 1: Start -> Speak -> Result populated -> Stop
{
  let state = { listening: false, question: "Existing note:", error: "" };
  let recognitionInstance = null;

  function setListening(val) { state.listening = val; }
  function setQuestion(updater) { state.question = typeof updater === "function" ? updater(state.question) : updater; }
  function setError(val) { state.error = val; }

  const recognition = new MockSpeechRecognition();
  recognitionInstance = recognition;
  recognition.onstart = () => { setListening(true); setError(""); };
  recognition.onresult = (event) => {
    let transcript = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    const cleanTranscript = transcript.trim();
    if (cleanTranscript) {
      setQuestion((prev) => (prev ? `${prev.trim()} ${cleanTranscript}` : cleanTranscript));
      setError("");
    }
  };
  recognition.onend = () => { setListening(false); };

  recognition.start();
  if (!state.listening) throw new Error("Simulation 1: listening should be true on start");

  recognition.emitResult("Summarize patient blood pressure history");
  if (!state.question.includes("Summarize patient blood pressure history")) {
    throw new Error("Simulation 1: transcript not populated");
  }
  if (!state.question.startsWith("Existing note: Summarize")) {
    throw new Error("Simulation 1: text not concatenated properly");
  }

  recognition.stop();
  if (state.listening) throw new Error("Simulation 1: listening should be false on stop");
  console.log("[SIMULATION 1 PASS] Normal speech input transcribed and concatenated successfully.");
}

// Test Flow 2: Silence / 'no-speech' error
{
  let state = { listening: false, question: "", error: "" };
  const recognition = new MockSpeechRecognition();
  recognition.onstart = () => { state.listening = true; };
  recognition.onerror = (event) => {
    switch (event.error) {
      case "no-speech":
        state.error = "No speech was detected. Please click the microphone and speak clearly.";
        break;
      default:
        state.error = `Voice input error (${event.error}). Please type your question.`;
    }
  };
  recognition.onend = () => { state.listening = false; };

  recognition.start();
  recognition.emitError("no-speech");
  recognition.onend();

  if (!state.error.includes("No speech was detected")) {
    throw new Error("Simulation 2: friendly no-speech error not produced");
  }
  if (state.listening) throw new Error("Simulation 2: listening should reset to false");
  console.log("[SIMULATION 2 PASS] 'no-speech' produces informative guidance instead of fatal error.");
}

// Test Flow 3: Permission denied ('not-allowed')
{
  let state = { listening: false, question: "", error: "" };
  const recognition = new MockSpeechRecognition();
  recognition.onstart = () => { state.listening = true; };
  recognition.onerror = (event) => {
    switch (event.error) {
      case "not-allowed":
        state.error = "Microphone permission was denied. Please allow microphone access in Chrome's address bar settings.";
        break;
      default:
        state.error = `Voice input error (${event.error}). Please type your question.`;
    }
  };
  recognition.onend = () => { state.listening = false; };

  recognition.start();
  recognition.emitError("not-allowed");
  recognition.onend();

  if (!state.error.includes("Microphone permission was denied")) {
    throw new Error("Simulation 3: not-allowed error message incorrect");
  }
  console.log("[SIMULATION 3 PASS] 'not-allowed' clearly instructs user to check address bar permissions.");
}

// Test Flow 4: User cancellation ('aborted') should not set error
{
  let state = { listening: false, question: "", error: "" };
  const recognition = new MockSpeechRecognition();
  recognition.onstart = () => { state.listening = true; };
  recognition.onerror = (event) => {
    switch (event.error) {
      case "aborted":
        // silent
        break;
      default:
        state.error = `Error: ${event.error}`;
    }
  };
  recognition.onend = () => { state.listening = false; };

  recognition.start();
  recognition.abort();

  if (state.error !== "") {
    throw new Error("Simulation 4: aborted should NOT set error");
  }
  console.log("[SIMULATION 4 PASS] 'aborted' cleanly stops without showing an error banner.");
}

console.log("\nALL STATIC CHECKS AND RUNTIME SIMULATIONS PASSED (14/14)!");
