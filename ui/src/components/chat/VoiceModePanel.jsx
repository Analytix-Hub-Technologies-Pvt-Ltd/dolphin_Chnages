import React, { useEffect, useState, useRef, useCallback } from "react";
import { Mic, MicOff, X, Sparkles } from "lucide-react";
import { VoiceSession } from "../../utils/audioStreamer";
import DolphinIconB from "../../assets/images/dolphin_b.png";
import DolphinIconW from "../../assets/images/dolphin_w.png";
import { useThemeMode } from "../../context/ThemeModeContext";

/**
 * Embedded In-Chat Voice Mode Interaction Component
 *
 * Sits directly inside the existing Dolphin chat session.
 * Keeps all previous messages, sidebar, header, and chat history visible.
 */
const VoiceModePanel = ({
  isActive,
  onClose,
  sessionId,
  userId = "test-user",
  onTurnComplete,
}) => {
  const { mode } = useThemeMode();
  const [voiceState, setVoiceState] = useState("CONNECTING"); // CONNECTING, LISTENING, USER_SPEAKING, PROCESSING, ASSISTANT_SPEAKING, ERROR
  const [userTranscript, setUserTranscript] = useState("");
  const [assistantText, setAssistantText] = useState("");
  const [micVolume, setMicVolume] = useState(0);
  const [assistantVolume, setAssistantVolume] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const sessionRef = useRef(null);
  const panelRef = useRef(null);
  const latestTranscriptRef = useRef("");

  // Clean exit handler
  const handleExit = useCallback(() => {
    if (sessionRef.current) {
      sessionRef.current.stop();
      sessionRef.current = null;
    }
    onClose();
  }, [onClose]);

  // Toggle Mute
  const handleToggleMute = useCallback(() => {
    if (sessionRef.current) {
      const nextMuted = sessionRef.current.toggleMute();
      setIsMuted(nextMuted);
    }
  }, []);

  // Initialize voice session on activation
  useEffect(() => {
    if (!isActive || !sessionId) return;

    setUserTranscript("");
    setAssistantText("");
    setErrorMessage("");
    setIsMuted(false);
    setMicVolume(0);
    setAssistantVolume(0);
    latestTranscriptRef.current = "";

    const session = new VoiceSession({
      sessionId,
      userId,
      onStateChange: (state) => {
        setVoiceState(state);
        if (state === "USER_SPEAKING") {
          setAssistantText("");
        }
      },
      onTranscript: (transcript) => {
        latestTranscriptRef.current = transcript;
        setUserTranscript(transcript);
      },
      onAssistantMessage: (payload) => {
        const content = payload.content || "";
        setAssistantText(content);
        const query = payload.user_query || latestTranscriptRef.current || "";
        if (onTurnComplete) {
          onTurnComplete(query, payload);
        }
      },
      onMicVolume: (rms) => {
        setMicVolume(rms);
      },
      onAssistantVolume: (rms) => {
        setAssistantVolume(rms);
      },
      onError: (err) => {
        setErrorMessage(typeof err === "string" ? err : "Voice connection issue");
      },
    });

    sessionRef.current = session;
    session.start();

    // Auto-scroll panel into view
    setTimeout(() => {
      panelRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }, 100);

    // Escape key listener for keyboard accessibility
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        handleExit();
      }
    };
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      if (sessionRef.current) {
        sessionRef.current.stop();
        sessionRef.current = null;
      }
    };
  }, [isActive, sessionId, userId, handleExit]);

  if (!isActive) return null;

  // Active volume calculation for audio reactivity
  const activeVolume = voiceState === "ASSISTANT_SPEAKING" ? assistantVolume : micVolume;
  const dynamicScale = 1 + Math.min(0.28, Math.max(0, activeVolume * 1.8));

  return (
    <div
      ref={panelRef}
      role="region"
      aria-label="Active Voice Conversation Area"
      className="w-full max-w-xl mx-auto my-3 rounded-3xl bg-bg-paper dark:bg-[#07192c] border border-primary/25 dark:border-primary/35 shadow-lg p-5 sm:p-6 flex flex-col items-center justify-between transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 select-none relative overflow-hidden"
    >
      {/* Background Soft Glow */}
      <div
        className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 rounded-full blur-3xl opacity-30 transition-all duration-500 pointer-events-none ${
          voiceState === "ASSISTANT_SPEAKING"
            ? "bg-primary"
            : voiceState === "PROCESSING"
            ? "bg-amber-500"
            : voiceState === "USER_SPEAKING"
            ? "bg-emerald-500"
            : "bg-sky-400"
        }`}
      />

      {/* Top Header Row of In-Chat Voice Panel */}
      <div className="relative z-10 w-full flex items-center justify-between pb-2 border-b border-border/40 dark:border-border/30">
        <div className="flex items-center gap-2">
          <img
            src={mode === "dark" ? DolphinIconW : DolphinIconB}
            alt="Dolphin"
            className="w-5 h-5 object-contain"
          />
          <span className="text-xs font-bold tracking-tight text-text-primary">
            Dolphin <span className="text-primary">Voice</span>
          </span>
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
        </div>

        <button
          type="button"
          onClick={handleExit}
          className="inline-flex items-center gap-1 text-[11px] font-semibold text-text-secondary hover:text-rose-500 transition-colors p-1 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 cursor-pointer"
          aria-label="End voice conversation"
          title="End Voice (Esc)"
        >
          <span>End Voice</span>
          <X size={14} />
        </button>
      </div>

      {/* Central Animated Voice Orb */}
      <div className="relative z-10 flex flex-col items-center justify-center my-4 sm:my-5">
        <div className="relative flex items-center justify-center w-36 h-36 sm:w-44 sm:h-44">
          
          {/* Concentric Wave Rings for Speaking / Listening */}
          {(voiceState === "LISTENING" || voiceState === "USER_SPEAKING" || voiceState === "ASSISTANT_SPEAKING") && (
            <>
              <div
                className="absolute inset-0 rounded-full border border-primary/30 animate-voice-ripple pointer-events-none"
                style={{ animationDuration: voiceState === "ASSISTANT_SPEAKING" ? "2s" : "3s" }}
              />
              <div
                className="absolute inset-3 rounded-full border border-sky-400/25 animate-voice-ripple pointer-events-none"
                style={{ animationDuration: voiceState === "ASSISTANT_SPEAKING" ? "2.5s" : "3.5s", animationDelay: "0.6s" }}
              />
            </>
          )}

          {/* Thinking Orbital Ring */}
          {voiceState === "PROCESSING" && (
            <div className="absolute inset-0 rounded-full border-2 border-dashed border-amber-400/50 animate-voice-spin pointer-events-none" />
          )}

          {/* Outer Breathing Glow */}
          <div
            className={`absolute inset-2 rounded-full blur-lg transition-all duration-300 opacity-60 ${
              voiceState === "USER_SPEAKING"
                ? "bg-emerald-400"
                : voiceState === "PROCESSING"
                ? "bg-amber-400 animate-pulse"
                : voiceState === "ASSISTANT_SPEAKING"
                ? "bg-primary"
                : "bg-primary animate-voice-pulse-slow"
            }`}
            style={{ transform: `scale(${dynamicScale})` }}
          />

          {/* Central 3D Fluid Voice Sphere */}
          <div
            className={`w-24 h-24 sm:w-28 sm:h-28 rounded-full shadow-lg flex items-center justify-center transition-transform duration-75 ease-out relative overflow-hidden ${
              voiceState === "USER_SPEAKING"
                ? "bg-gradient-to-tr from-emerald-600 via-teal-400 to-cyan-300 shadow-[0_0_35px_rgba(16,185,129,0.45)]"
                : voiceState === "PROCESSING"
                ? "bg-gradient-to-tr from-amber-600 via-yellow-400 to-orange-400 shadow-[0_0_35px_rgba(245,158,11,0.45)] animate-voice-spin"
                : voiceState === "ASSISTANT_SPEAKING"
                ? "bg-gradient-to-tr from-[#0284c7] via-[#38bdf8] to-[#67e8f9] shadow-[0_0_40px_rgba(56,189,248,0.5)] animate-voice-breathe"
                : "bg-gradient-to-tr from-[#0369a1] via-[#0284c7] to-[#38bdf8] shadow-[0_0_30px_rgba(14,165,233,0.35)] animate-voice-breathe"
            }`}
            style={{
              transform: `scale(${dynamicScale})`,
            }}
          >
            {/* Inner Glass Highlights */}
            <div className="absolute top-1.5 left-2 w-10 h-10 rounded-full bg-white/35 blur-xs pointer-events-none" />
            <div className="absolute bottom-1 right-2 w-12 h-6 rounded-full bg-black/20 blur-xs pointer-events-none" />

            {/* Core Indicator for Thinking */}
            {voiceState === "PROCESSING" && (
              <Sparkles className="w-6 h-6 text-amber-100 animate-pulse" />
            )}
          </div>
        </div>

        {/* Status Text Indicator */}
        <div className="mt-3 text-center">
          <p className="text-sm sm:text-base font-semibold text-text-primary tracking-tight m-0">
            {voiceState === "CONNECTING" && "Connecting..."}
            {voiceState === "LISTENING" && (isMuted ? "Microphone Muted" : "Listening...")}
            {voiceState === "USER_SPEAKING" && "Listening..."}
            {voiceState === "PROCESSING" && "Thinking..."}
            {voiceState === "ASSISTANT_SPEAKING" && "Dolphin is speaking..."}
            {voiceState === "ERROR" && (errorMessage || "Voice connection issue")}
          </p>

          <p className="text-[11px] text-text-secondary mt-0.5 font-normal">
            {voiceState === "LISTENING" && !isMuted && "Speak naturally at any time"}
            {voiceState === "LISTENING" && isMuted && "Unmute microphone to speak"}
            {voiceState === "ASSISTANT_SPEAKING" && "Speak to interrupt at any time"}
            {voiceState === "PROCESSING" && "Reviewing maritime guidance"}
            {voiceState === "ERROR" && "Click End Voice to retry"}
          </p>
        </div>

        {/* Live Subtitle Preview */}
        {(userTranscript || (voiceState === "ASSISTANT_SPEAKING" && assistantText)) && (
          <div className="mt-3 w-full max-w-sm px-3.5 py-2 rounded-xl bg-bg-light2 dark:bg-bg-default border border-border/60 text-center max-h-20 overflow-hidden">
            {userTranscript && (
              <p className="text-xs font-semibold text-primary truncate">
                "{userTranscript}"
              </p>
            )}
            {voiceState === "ASSISTANT_SPEAKING" && assistantText && (
              <p className="text-[11px] text-text-secondary line-clamp-2 mt-0.5 leading-relaxed">
                {assistantText.replace(/[#*`_]/g, "")}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Bottom Compact Action Bar */}
      <div className="relative z-10 w-full flex items-center justify-center gap-4 pt-1">
        {/* Mute Button */}
        <button
          type="button"
          onClick={handleToggleMute}
          aria-label={isMuted ? "Unmute microphone" : "Mute microphone"}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all border cursor-pointer ${
            isMuted
              ? "bg-rose-500/15 border-rose-500/30 text-rose-500 hover:bg-rose-500/25"
              : "bg-black/5 dark:bg-white/5 border-border text-text-secondary hover:text-text-primary hover:bg-black/10 dark:hover:bg-white/10"
          }`}
        >
          {isMuted ? <MicOff size={14} /> : <Mic size={14} />}
          <span>{isMuted ? "Unmute" : "Mute"}</span>
        </button>

        {/* Interrupt Button (Visible during speech) */}
        {voiceState === "ASSISTANT_SPEAKING" && (
          <button
            type="button"
            onClick={() => sessionRef.current && sessionRef.current.interrupt()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-amber-500/15 border border-amber-500/30 text-amber-600 dark:text-amber-400 hover:bg-amber-500/25 transition-all cursor-pointer"
          >
            <span>Interrupt</span>
          </button>
        )}

        {/* End Voice Button */}
        <button
          type="button"
          onClick={handleExit}
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-semibold bg-rose-600/90 hover:bg-rose-600 text-white transition-all shadow-xs cursor-pointer"
        >
          <X size={14} />
          <span>End</span>
        </button>
      </div>
    </div>
  );
};

export default VoiceModePanel;
