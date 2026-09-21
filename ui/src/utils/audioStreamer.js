import { getWsUrl } from "../config/apiConfig";

/**
 * Real-Time Continuous Voice Session Manager
 *
 * Responsibilities:
 * - Microphone capture with hardware echo cancellation and noise suppression
 * - Real-time PCM audio streaming over WebSocket
 * - Client-side energy Voice Activity Detection (VAD) with silence offset detection
 * - Seamless sentence-by-sentence Web Audio queue playback
 * - Real-time audio amplitude analysis for both microphone and assistant playback
 * - Mute / unmute control
 * - Zero-latency barge-in interruption
 */
export class VoiceSession {
  constructor({
    sessionId,
    userId = "test-user",
    onStateChange,
    onTranscript,
    onAssistantMessage,
    onMicVolume,
    onAssistantVolume,
    onError,
  }) {
    this.sessionId = sessionId;
    this.userId = userId;
    this.onStateChange = onStateChange || (() => {});
    this.onTranscript = onTranscript || (() => {});
    this.onAssistantMessage = onAssistantMessage || (() => {});
    this.onMicVolume = onMicVolume || (() => {});
    this.onAssistantVolume = onAssistantVolume || (() => {});
    this.onError = onError || (() => {});

    this.state = "IDLE"; // IDLE, LISTENING, USER_SPEAKING, PROCESSING, ASSISTANT_SPEAKING, ERROR
    this.ws = null;
    this.audioContext = null;
    this.mediaStream = null;
    this.sourceNode = null;
    this.processorNode = null;

    // Analyser nodes for audio reactivity
    this.micAnalyser = null;
    this.playbackAnalyser = null;
    this.animFrameId = null;

    // Mute state
    this.isMuted = false;

    // VAD & Energy parameters
    this.isSpeaking = false;
    this.silenceStartTime = null;
    this.SILENCE_DURATION_MS = 750; // 750ms silence to consider turn finished
    this.SPEECH_THRESHOLD = 0.018; // RMS energy threshold for speech onset
    this.BARGE_IN_THRESHOLD = 0.038; // Elevated threshold during assistant speech

    // Audio Playback Queue
    this.playbackQueue = [];
    this.isPlaying = false;
    this.currentSourceNode = null;
    this.allChunksReceived = false;

    this.isActive = false;
  }

  setState(newState) {
    if (this.state !== newState) {
      this.state = newState;
      this.onStateChange(this.state);
    }
  }

  setMuted(muted) {
    this.isMuted = muted;
    if (this.isMuted) {
      this.isSpeaking = false;
      this.silenceStartTime = null;
      if (this.state === "USER_SPEAKING") {
        this.setState("LISTENING");
      }
    }
  }

  toggleMute() {
    this.setMuted(!this.isMuted);
    return this.isMuted;
  }

  async start() {
    this.isActive = true;
    try {
      this.setState("CONNECTING");

      // 1. Initialize Web Audio Context
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      this.audioContext = new AudioCtx({ sampleRate: 16000 });
      if (this.audioContext.state === "suspended") {
        await this.audioContext.resume();
      }

      // Create AnalyserNode for Assistant playback audio reactivity
      this.playbackAnalyser = this.audioContext.createAnalyser();
      this.playbackAnalyser.fftSize = 64;
      this.playbackAnalyser.smoothingTimeConstant = 0.8;
      this.playbackAnalyser.connect(this.audioContext.destination);

      // 2. Request Microphone Stream with Echo Cancellation
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // 3. Connect WebSocket
      const wsBase = getWsUrl();
      const wsUrl = `${wsBase}/ws/voice/${this.sessionId}`;
      console.log("🎙️ Connecting Voice WebSocket to:", wsUrl);

      this.ws = new WebSocket(wsUrl);
      this.ws.binaryType = "arraybuffer";

      this.ws.onopen = () => {
        console.log("✅ Voice WebSocket Connected");
        this.ws.send(
          JSON.stringify({
            type: "voice_start",
            session_id: this.sessionId,
            user_id: this.userId,
          })
        );
        this.setState("LISTENING");
        this._setupAudioProcessing();
        this._startPlaybackAnimationLoop();
      };

      this.ws.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);
          this._handleServerMessage(data);
        } catch (e) {
          console.error("Error parsing WebSocket message:", e);
        }
      };

      this.ws.onerror = (err) => {
        console.error("Voice WebSocket error:", err);
        this.onError("WebSocket connection error");
      };

      this.ws.onclose = () => {
        console.log("Voice WebSocket closed");
        if (this.isActive) {
          this.setState("IDLE");
        }
      };
    } catch (err) {
      console.error("Failed to start voice session:", err);
      this.onError(err.message || "Could not access microphone");
      this.stop();
    }
  }

  _setupAudioProcessing() {
    if (!this.audioContext || !this.mediaStream) return;

    this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);

    // Buffer size 2048 at 16kHz = ~128ms per slice
    this.processorNode = this.audioContext.createScriptProcessor(2048, 1, 1);

    this.processorNode.onaudioprocess = (e) => {
      if (!this.isActive || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;

      const inputData = e.inputBuffer.getChannelData(0);

      // Compute RMS volume
      let sum = 0;
      for (let i = 0; i < inputData.length; i++) {
        sum += inputData[i] * inputData[i];
      }
      const rms = Math.sqrt(sum / inputData.length);
      this.onMicVolume(this.isMuted ? 0 : rms);

      // If muted, do not send audio chunks or trigger speech
      if (this.isMuted) return;

      // Barge-in check: If assistant is speaking and user speaks
      if (this.state === "ASSISTANT_SPEAKING") {
        if (rms > this.BARGE_IN_THRESHOLD) {
          console.log("⚡ Barge-in detected (RMS:", rms.toFixed(4), ") -> Interrupting");
          this.interrupt();
        }
        return; // Do not stream microphone audio during assistant playback to prevent echo
      }

      // Convert Float32Array to 16-bit PCM
      const pcm16 = new Int16Array(inputData.length);
      for (let i = 0; i < inputData.length; i++) {
        const s = Math.max(-1, Math.min(1, inputData[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }

      // Voice Activity Detection (VAD) Logic
      const isVoice = rms > this.SPEECH_THRESHOLD;
      const now = Date.now();

      if (isVoice) {
        this.silenceStartTime = null;
        if (!this.isSpeaking) {
          this.isSpeaking = true;
          this.setState("USER_SPEAKING");
        }
        // Stream audio chunk to backend
        this.ws.send(pcm16.buffer);
      } else if (this.isSpeaking) {
        // Speech was active, now silent: keep streaming brief trailing silence
        this.ws.send(pcm16.buffer);

        if (!this.silenceStartTime) {
          this.silenceStartTime = now;
        } else if (now - this.silenceStartTime > this.SILENCE_DURATION_MS) {
          // Continuous silence reached -> End of speech turn
          console.log("🛑 Speech ended (silence detected). Processing...");
          this.isSpeaking = false;
          this.silenceStartTime = null;
          this.setState("PROCESSING");
          this.ws.send(JSON.stringify({ type: "speech_end" }));
        }
      }
    };

    this.sourceNode.connect(this.processorNode);
    this.processorNode.connect(this.audioContext.destination);
  }

  _startPlaybackAnimationLoop() {
    const dataArray = new Uint8Array(32);

    const updateLoop = () => {
      if (!this.isActive) return;

      if (this.playbackAnalyser && this.isPlaying && this.state === "ASSISTANT_SPEAKING") {
        this.playbackAnalyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        const avg = sum / dataArray.length / 255;
        this.onAssistantVolume(avg);
      } else if (this.state !== "ASSISTANT_SPEAKING") {
        this.onAssistantVolume(0);
      }

      this.animFrameId = requestAnimationFrame(updateLoop);
    };

    this.animFrameId = requestAnimationFrame(updateLoop);
  }

  async _handleServerMessage(data) {
    switch (data.type) {
      case "listening":
        this.setState("LISTENING");
        break;

      case "speech_started":
        if (this.state !== "USER_SPEAKING") {
          this.setState("USER_SPEAKING");
        }
        break;

      case "processing_started":
        this.setState("PROCESSING");
        break;

      case "transcript_final":
        if (data.transcript) {
          this.onTranscript(data.transcript);
        }
        break;

      case "transcript_empty":
        this.setState("LISTENING");
        break;

      case "assistant_text":
        this.onAssistantMessage(data);
        break;

      case "tts_started":
        this.setState("ASSISTANT_SPEAKING");
        this.allChunksReceived = false;
        this.playbackQueue = [];
        break;

      case "tts_audio_chunk":
        if (data.audio) {
          await this._queueAudioChunk(data.audio);
        }
        break;

      case "tts_completed":
        this.allChunksReceived = true;
        if (!this.isPlaying && this.playbackQueue.length === 0) {
          this.setState("LISTENING");
        }
        break;

      case "interrupted":
        this._stopAudioPlayback();
        this.setState("USER_SPEAKING");
        break;

      case "error":
        console.error("Server voice error:", data.message);
        this.onError(data.message || "An error occurred");
        this.setState("LISTENING");
        break;

      default:
        break;
    }
  }

  async _queueAudioChunk(base64Wav) {
    if (!this.audioContext || this.state === "IDLE") return;

    try {
      // Decode Base64 to ArrayBuffer
      const binaryString = atob(base64Wav);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      // Decode WAV into AudioBuffer using Web Audio API
      const audioBuffer = await this.audioContext.decodeAudioData(bytes.buffer);
      this.playbackQueue.push(audioBuffer);

      if (!this.isPlaying) {
        this._playNextInQueue();
      }
    } catch (e) {
      console.error("Failed to decode audio chunk:", e);
    }
  }

  _playNextInQueue() {
    if (this.playbackQueue.length === 0) {
      this.isPlaying = false;
      if (this.allChunksReceived && this.state === "ASSISTANT_SPEAKING") {
        console.log("🏁 Playback finished -> Automatically listening again.");
        this.setState("LISTENING");
      }
      return;
    }

    this.isPlaying = true;
    const buffer = this.playbackQueue.shift();

    if (!this.audioContext || !this.playbackAnalyser) return;

    const source = this.audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(this.playbackAnalyser);

    this.currentSourceNode = source;

    source.onended = () => {
      this.currentSourceNode = null;
      // Slight 30ms natural pause between sentences
      setTimeout(() => {
        if (this.isActive && this.state === "ASSISTANT_SPEAKING") {
          this._playNextInQueue();
        }
      }, 30);
    };

    source.start(0);
  }

  _stopAudioPlayback() {
    this.playbackQueue = [];
    this.isPlaying = false;
    if (this.currentSourceNode) {
      try {
        this.currentSourceNode.stop();
        this.currentSourceNode.disconnect();
      } catch (e) {
        // already stopped
      }
      this.currentSourceNode = null;
    }
  }

  interrupt() {
    console.log("⚡ Interrupting Assistant Speech...");
    this._stopAudioPlayback();
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "interrupt" }));
    }
    this.setState("USER_SPEAKING");
  }

  stop() {
    this.isActive = false;
    this._stopAudioPlayback();

    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    if (this.processorNode) {
      this.processorNode.disconnect();
      this.processorNode = null;
    }
    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
    if (this.playbackAnalyser) {
      this.playbackAnalyser.disconnect();
      this.playbackAnalyser = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
    if (this.audioContext) {
      this.audioContext.close().catch(() => {});
      this.audioContext = null;
    }
    if (this.ws) {
      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: "session_end" }));
      }
      this.ws.close();
      this.ws = null;
    }

    this.setState("IDLE");
  }
}
