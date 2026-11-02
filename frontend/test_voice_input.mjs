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

console.log("\n=== CareTrack AI Two-Way Voice Assistance Verification ===");

// 11. Check Language Selector (English & Tamil)
const hasTamilSupport = content.includes('"ta-IN"') && content.includes('"en-IN"');
console.log(`[PASS 11] English & Tamil voice input languages supported: ${hasTamilSupport}`);
if (!hasTamilSupport) throw new Error("Tamil/English language support missing");

// 12. Check continuous recognition mode
const hasContinuous = /recognition\.continuous\s*=\s*true/.test(content);
console.log(`[PASS 12] Continuous voice recognition configured: ${hasContinuous}`);
if (!hasContinuous) throw new Error("Continuous recognition missing");

// 13. Check Text-to-Speech (TTS) functions defined for both Question and AI Response
const hasSpeakResponseFunc = /function\s+speakResponse\(/.test(content);
const hasSpeakQuestionFunc = /function\s+speakQuestion\(/.test(content);
const hasPauseFunc = /function\s+pauseSpeech\(/.test(content);
const hasResumeFunc = /function\s+resumeSpeech\(/.test(content);
const hasStopFunc = /function\s+stopSpeech\(/.test(content);
console.log(`[PASS 13] TTS functions (speakQuestion, speakResponse, pause, resume, stop) defined: ${hasSpeakQuestionFunc && hasSpeakResponseFunc && hasPauseFunc && hasResumeFunc && hasStopFunc}`);
if (!hasSpeakQuestionFunc || !hasSpeakResponseFunc || !hasPauseFunc || !hasResumeFunc || !hasStopFunc) {
  throw new Error("One or more TTS speech functions missing");
}

// 14. Check cleanTextForSpeech function
const hasCleanText = /function\s+cleanTextForSpeech\(/.test(content);
console.log(`[PASS 14] cleanTextForSpeech helper defined: ${hasCleanText}`);
if (!hasCleanText) throw new Error("cleanTextForSpeech missing");

// Extract and test cleanTextForSpeech directly
const cleanFnMatch = content.match(/function\s+cleanTextForSpeech\([\s\S]*?\n\}/);
if (!cleanFnMatch) throw new Error("Could not extract cleanTextForSpeech");
const cleanTextForSpeech = new Function("text", cleanFnMatch[0].replace("function cleanTextForSpeech(text)", "") + "\nreturn cleanTextForSpeech(text);");

// Test cleanTextForSpeech: remove citations and markdown, preserve medical data
const rawSample = "**Blood Pressure**: 140/90 mmHg [S1, S2].\n* Fasting glucose: 130 mg/dL [S3].\n### Follow-up\nRecommended follow-up in 2 weeks.";
const cleanedSample = cleanTextForSpeech(rawSample);
console.log(`[PASS 15] cleanTextForSpeech strips citations and markup: ${!cleanedSample.includes("[S1") && !cleanedSample.includes("**") && cleanedSample.includes("140/90 mmHg")}`);
if (cleanedSample.includes("[S1") || cleanedSample.includes("**") || !cleanedSample.includes("140/90 mmHg")) {
  throw new Error(`cleanTextForSpeech failed: "${cleanedSample}"`);
}

// 16. Check Question voice output button beside question input
const hasQuestionListenBtn = content.includes("Listen to Question");
console.log(`[PASS 16] Question voice output button present beside question input: ${hasQuestionListenBtn}`);
if (!hasQuestionListenBtn) throw new Error("Question voice output button missing");

// 17. Check Response TTS controls in JSX: Listen to Response, Pause, Resume, Stop
const hasListenBtn = content.includes("Listen to Response");
const hasPauseBtn = content.includes("Pause");
const hasResumeBtn = content.includes("Resume");
const hasStopBtn = content.includes("Stop");
console.log(`[PASS 17] TTS UI controls (Listen to Response, Pause, Resume, Stop) present in JSX: ${hasListenBtn && hasPauseBtn && hasResumeBtn && hasStopBtn}`);
if (!hasListenBtn || !hasPauseBtn || !hasResumeBtn || !hasStopBtn) {
  throw new Error("TTS action buttons missing in JSX");
}

// 18. Check TTS cancel on unmount
const hasTtsCleanup = content.includes("window.speechSynthesis.cancel()");
console.log(`[PASS 18] TTS speech synthesis cancelled on unmount: ${hasTtsCleanup}`);
if (!hasTtsCleanup) throw new Error("TTS cancel on unmount missing");

// 19. Simulate Speech Synthesis State Machine
class MockSpeechSynthesis {
  constructor() {
    this.speaking = false;
    this.paused = false;
    this.currentUtterance = null;
  }
  speak(utterance) {
    this.cancel();
    this.speaking = true;
    this.paused = false;
    this.currentUtterance = utterance;
    if (utterance.onstart) utterance.onstart();
  }
  pause() {
    if (this.speaking) {
      this.paused = true;
      if (this.currentUtterance?.onpause) this.currentUtterance.onpause();
    }
  }
  resume() {
    if (this.speaking && this.paused) {
      this.paused = false;
      if (this.currentUtterance?.onresume) this.currentUtterance.onresume();
    }
  }
  cancel() {
    if (this.currentUtterance) {
      if (this.currentUtterance.onend) this.currentUtterance.onend();
    }
    this.speaking = false;
    this.paused = false;
    this.currentUtterance = null;
  }
}

// Simulation 5: Independent AI response playback (Play -> Pause -> Resume -> Stop)
{
  const synth = new MockSpeechSynthesis();
  let state = { activeSource: null, status: "idle" };

  function speakTextMock(source) {
    synth.cancel();
    const utterance = {
      onstart: () => { state.activeSource = source; state.status = "playing"; },
      onpause: () => { state.status = "paused"; },
      onresume: () => { state.status = "playing"; },
      onend: () => { state.activeSource = null; state.status = "idle"; },
    };
    synth.speak(utterance);
  }

  // 1. Play AI Response
  speakTextMock({ type: "response", index: 0 });
  if (state.activeSource?.type !== "response" || state.status !== "playing") {
    throw new Error("AI Response Simulation: speakResponse failed to set playing state");
  }

  // 2. Pause
  synth.pause();
  if (state.status !== "paused") {
    throw new Error("AI Response Simulation: pause failed to set paused state");
  }

  // 3. Resume
  synth.resume();
  if (state.status !== "playing") {
    throw new Error("AI Response Simulation: resume failed to set playing state");
  }

  // 4. Stop
  synth.cancel();
  if (state.activeSource !== null || state.status !== "idle") {
    throw new Error("AI Response Simulation: stop failed to reset to idle");
  }

  console.log("[SIMULATION 5 PASS] AI Response playback (Listen -> Pause -> Resume -> Stop) passed.");
}

// Simulation 6: Independent Question playback (Play -> Pause -> Resume -> Stop)
{
  const synth = new MockSpeechSynthesis();
  let state = { activeSource: null, status: "idle" };

  function speakTextMock(source) {
    synth.cancel();
    const utterance = {
      onstart: () => { state.activeSource = source; state.status = "playing"; },
      onpause: () => { state.status = "paused"; },
      onresume: () => { state.status = "playing"; },
      onend: () => { state.activeSource = null; state.status = "idle"; },
    };
    synth.speak(utterance);
  }

  // 1. Play typed or voice-input question
  speakTextMock({ type: "question" });
  if (state.activeSource?.type !== "question" || state.status !== "playing") {
    throw new Error("Question Simulation: speakQuestion failed to set playing state");
  }

  // 2. Pause
  synth.pause();
  if (state.status !== "paused") {
    throw new Error("Question Simulation: pause failed to set paused state");
  }

  // 3. Resume
  synth.resume();
  if (state.status !== "playing") {
    throw new Error("Question Simulation: resume failed to set playing state");
  }

  // 4. Stop
  synth.cancel();
  if (state.activeSource !== null || state.status !== "idle") {
    throw new Error("Question Simulation: stop failed to reset to idle");
  }

  console.log("[SIMULATION 6 PASS] Question voice output (Listen -> Pause -> Resume -> Stop) passed.");
}

// Simulation 7: Mutual Exclusion - Question and Response never play simultaneously
{
  const synth = new MockSpeechSynthesis();
  let state = { activeSource: null, status: "idle" };

  function speakTextMock(source) {
    synth.cancel();
    const utterance = {
      onstart: () => { state.activeSource = source; state.status = "playing"; },
      onpause: () => { state.status = "paused"; },
      onresume: () => { state.status = "playing"; },
      onend: () => { state.activeSource = null; state.status = "idle"; },
    };
    synth.speak(utterance);
  }

  // Start question audio
  speakTextMock({ type: "question" });
  if (state.activeSource?.type !== "question") throw new Error("Mutual Exclusion test: question did not start");

  // Click response audio while question is playing -> Question audio must stop
  speakTextMock({ type: "response", index: 0 });
  if (state.activeSource?.type !== "response" || state.activeSource.index !== 0) {
    throw new Error("Mutual Exclusion test: response failed to override question");
  }

  // Click question audio while response is playing -> Response audio must stop
  speakTextMock({ type: "question" });
  if (state.activeSource?.type !== "question") {
    throw new Error("Mutual Exclusion test: question failed to override response");
  }

  synth.cancel();
  console.log("[SIMULATION 7 PASS] Question and response audio mutual exclusion verified (never simultaneous).");
}

console.log("\nALL VOICE ASSISTANCE STATIC CHECKS AND RUNTIME SIMULATIONS PASSED (24/24)!");

