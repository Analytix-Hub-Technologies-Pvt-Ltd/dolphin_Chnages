import React, { useEffect, useState, useRef, useCallback } from "react";
import { Sparkles } from "lucide-react";
import { VoiceSession } from "../../utils/audioStreamer";

/**
 * Compact Above-Input Voice Mode Orb Dock
 *
 * Sits directly above the bottom chat bar so the entire chat session
 * and streaming responses remain fully visible in real-time.
 */
const VoiceModePanel = ({
  isActive,
  onClose,
  sessionId,
  userId = "test-user",
  userData = {},
  onTranscript,
  onStatusChunk,
  onTokenChunk,
  onTurnComplete,
  onInterrupt,
  isMuted = false,
  onMuteChange,
  voiceSessionRef,
}) => {
  const [voiceState, setVoiceState] = useState("CONNECTING"); // CONNECTING, LISTENING, USER_SPEAKING, PROCESSING, ASSISTANT_SPEAKING, ERROR
  const [micVolume, setMicVolume] = useState(0);
  const [assistantVolume, setAssistantVolume] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");
  const [liveTranscript, setLiveTranscript] = useState("");

  const sessionRef = useRef(null);
  const latestTranscriptRef = useRef("");

  // Store latest callbacks and props in refs to prevent unnecessary session teardowns
  const callbacksRef = useRef({});
  callbacksRef.current = {
    onClose,
    onTranscript,
    onStatusChunk,
    onTokenChunk,
    onTurnComplete,
    onInterrupt,
  };

  const sessionIdRef = useRef(sessionId);
  sessionIdRef.current = sessionId;
  const userIdRef = useRef(userId);
  userIdRef.current = userId;
  const userDataRef = useRef(userData);
  userDataRef.current = userData;

  // Clean exit handler
  const handleExit = useCallback(() => {
    if (sessionRef.current) {
      sessionRef.current.stop();
      sessionRef.current = null;
      if (voiceSessionRef) {
        voiceSessionRef.current = null;
      }
    }
    callbacksRef.current.onClose?.();
  }, [voiceSessionRef]);

  // Sync external mute state to session
  useEffect(() => {
    if (sessionRef.current && sessionRef.current.isMuted !== isMuted) {
      sessionRef.current.setMuted(isMuted);
    }
  }, [isMuted]);

  // Sync session ID changes without tearing down the WebSocket
  useEffect(() => {
    if (sessionRef.current && sessionId && sessionRef.current.sessionId !== sessionId) {
      sessionRef.current.sessionId = sessionId;
    }
  }, [sessionId]);

  // Initialize voice session ONCE on activation; never tear down on re-renders
  useEffect(() => {
    if (!isActive) return;

    setErrorMessage("");
    setMicVolume(0);
    setAssistantVolume(0);
    setLiveTranscript("");
    latestTranscriptRef.current = "";

    const session = new VoiceSession({
      sessionId: sessionIdRef.current || "new-session",
      userId: userIdRef.current || "guest",
      userData: userDataRef.current || {},
      onStateChange: (state) => {
        setVoiceState(state);
        if (state === "ASSISTANT_SPEAKING" || state === "IDLE") {
          setLiveTranscript("");
        }
      },
      onInterimTranscript: (interim) => {
        setLiveTranscript(interim);
      },
      onTranscript: (transcript) => {
        setLiveTranscript(transcript);
        latestTranscriptRef.current = transcript;
        callbacksRef.current.onTranscript?.(transcript);
      },
      onStatusChunk: (status, message) => {
        callbacksRef.current.onStatusChunk?.(status, message);
      },
      onTokenChunk: (token, query) => {
        callbacksRef.current.onTokenChunk?.(token, query || latestTranscriptRef.current);
      },
      onAssistantMessage: (payload) => {
        const query = payload.user_query || latestTranscriptRef.current || "";
        callbacksRef.current.onTurnComplete?.(query, payload);
      },
      onMicVolume: (rms) => {
        setMicVolume(rms);
      },
      onAssistantVolume: (rms) => {
        setAssistantVolume(rms);
      },
      onInterrupt: () => {
        setLiveTranscript("");
        callbacksRef.current.onInterrupt?.();
      },
      onError: (err) => {
        setErrorMessage(typeof err === "string" ? err : "Voice connection issue");
      },
    });

    sessionRef.current = session;
    if (voiceSessionRef) {
      voiceSessionRef.current = session;
    }
    session.start();

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
        if (voiceSessionRef) {
          voiceSessionRef.current = null;
        }
      }
    };
  }, [isActive, handleExit, voiceSessionRef]);

  if (!isActive) return null;

  // Active volume calculation for audio reactivity
  const activeVolume = voiceState === "ASSISTANT_SPEAKING" ? assistantVolume : micVolume;
  const dynamicScale = 1 + Math.min(0.2, Math.max(0, activeVolume * 1.4));

  return (
    <div
      role="region"
      aria-label="Active Voice Mode"
      className="w-full max-w-4xl mx-auto px-4 pb-1 pt-0 flex flex-col items-center justify-center relative select-none animate-in fade-in slide-in-from-bottom-2 duration-300 pointer-events-none shrink-0"
    >
      {/* Soft Ambient Background Glow */}
      <div
        className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-20 h-20 sm:w-24 sm:h-24 rounded-full blur-xl opacity-30 dark:opacity-20 transition-all duration-500 pointer-events-none ${
          voiceState === "ASSISTANT_SPEAKING"
            ? "bg-primary"
            : voiceState === "PROCESSING"
            ? "bg-amber-400"
            : voiceState === "USER_SPEAKING"
            ? "bg-emerald-400"
            : "bg-sky-400"
        }`}
      />

      {/* Compact Animated Voice Orb & State Label */}
      <div className="relative z-10 flex flex-col items-center justify-center pointer-events-auto">
        
        {/* Live Spoken Speech Preview Badge */}
        {liveTranscript && (voiceState === "USER_SPEAKING" || voiceState === "PROCESSING") && (
          <div className="mb-1.5 px-3 py-1 rounded-full bg-bg-paper/95 dark:bg-slate-900/95 backdrop-blur-md border border-primary/30 shadow-md flex items-center gap-2 max-w-sm sm:max-w-md animate-in fade-in slide-in-from-bottom-1 duration-200">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shrink-0" />
            <p className="text-[11px] font-medium text-text-primary truncate italic">
              "{liveTranscript}"
            </p>
          </div>
        )}

        <div
          role="button"
          tabIndex={0}
          onClick={() => {
            if (voiceState === "ASSISTANT_SPEAKING") {
              sessionRef.current?.interrupt();
            }
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              if (voiceState === "ASSISTANT_SPEAKING") {
                sessionRef.current?.interrupt();
              }
            }
          }}
          title={voiceState === "ASSISTANT_SPEAKING" ? "Click to interrupt speech" : undefined}
          className={`relative flex items-center justify-center w-11 h-11 sm:w-12 sm:h-12 ${
            voiceState === "ASSISTANT_SPEAKING" ? "cursor-pointer hover:scale-105 transition-transform" : ""
          }`}
        >
          
          {/* Concentric Soft Wave Rings for Listening / Speaking */}
          {(voiceState === "LISTENING" || voiceState === "USER_SPEAKING" || voiceState === "ASSISTANT_SPEAKING") && (
            <>
              <div
                className="absolute inset-0 rounded-full border border-primary/25 dark:border-primary/35 animate-voice-ripple pointer-events-none"
                style={{ animationDuration: voiceState === "ASSISTANT_SPEAKING" ? "2.2s" : "3.2s" }}
              />
              <div
                className="absolute inset-1 rounded-full border border-sky-400/20 animate-voice-ripple pointer-events-none"
                style={{ animationDuration: voiceState === "ASSISTANT_SPEAKING" ? "2.8s" : "3.8s", animationDelay: "0.7s" }}
              />
            </>
          )}

          {/* Thinking Orbital Spinner Ring */}
          {voiceState === "PROCESSING" && (
            <div className="absolute inset-0.5 rounded-full border-2 border-dashed border-amber-400/40 animate-voice-spin pointer-events-none" />
          )}

          {/* Outer Breathing Radial Glow */}
          <div
            className={`absolute inset-1 rounded-full blur-xs transition-all duration-300 opacity-60 ${
              voiceState === "USER_SPEAKING"
                ? "bg-emerald-400"
                : voiceState === "PROCESSING"
                ? "bg-amber-400 animate-pulse"
                : voiceState === "ASSISTANT_SPEAKING"
                ? "bg-primary"
                : "bg-gradient-to-tr from-sky-400 to-indigo-500 animate-voice-pulse-slow"
            }`}
            style={{ transform: `scale(${dynamicScale})` }}
          />

          {/* Central 3D Fluid Voice Sphere (Compact ~34-38px) */}
          <div
            className={`w-8.5 h-8.5 sm:w-9.5 sm:h-9.5 rounded-full shadow-md flex items-center justify-center transition-transform duration-75 ease-out relative overflow-hidden ${
              voiceState === "USER_SPEAKING"
                ? "bg-gradient-to-tr from-emerald-600 via-teal-400 to-cyan-300 shadow-[0_0_16px_rgba(16,185,129,0.45)]"
                : voiceState === "PROCESSING"
                ? "bg-gradient-to-tr from-amber-600 via-yellow-400 to-orange-400 shadow-[0_0_16px_rgba(245,158,11,0.45)] animate-voice-spin"
                : voiceState === "ASSISTANT_SPEAKING"
                ? "bg-gradient-to-tr from-[#0284c7] via-[#6366f1] to-[#a855f7] shadow-[0_0_18px_rgba(99,102,241,0.5)] animate-voice-breathe"
                : "bg-gradient-to-tr from-[#0369a1] via-[#0284c7] to-[#818cf8] shadow-[0_0_15px_rgba(14,165,233,0.38)] animate-voice-breathe"
            }`}
            style={{
              transform: `scale(${dynamicScale})`,
            }}
          >
            {/* Inner Glass Highlights */}
            <div className="absolute top-0.5 left-1 w-4 h-4 rounded-full bg-white/30 blur-xs pointer-events-none" />
            <div className="absolute bottom-0.5 right-1 w-5 h-2.5 rounded-full bg-black/15 blur-xs pointer-events-none" />

            {/* Core Thinking Indicator */}
            {voiceState === "PROCESSING" && (
              <Sparkles className="w-3 h-3 text-amber-100 animate-pulse" />
            )}
          </div>
        </div>

        {/* Subtle Status Text Indicator */}
        <p className="text-[11px] font-medium text-text-secondary dark:text-slate-400 tracking-tight mt-0.5 mb-0 max-w-sm sm:max-w-md truncate text-center">
          {voiceState === "CONNECTING" && "Connecting..."}
          {voiceState === "LISTENING" && (isMuted ? "Microphone Muted" : "Listening for your question...")}
          {voiceState === "USER_SPEAKING" && (liveTranscript ? `Listening...` : "Listening...")}
          {voiceState === "PROCESSING" && (liveTranscript ? `Processing question...` : "Thinking...")}
          {voiceState === "ASSISTANT_SPEAKING" && "Dolphin is speaking..."}
          {voiceState === "ERROR" && (errorMessage || "Voice connection issue")}
        </p>
      </div>
    </div>
  );
};

export default VoiceModePanel;
