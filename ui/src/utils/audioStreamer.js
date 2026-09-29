import { getWsUrl } from "../config/apiConfig";

/**
 * Real-Time Continuous Voice Session Manager
 *
 * Responsibilities:
 * - High-fidelity microphone capture with hardware echo cancellation and noise suppression
 * - Precision linear-interpolated 16kHz PCM downsampling
 * - Continuous circular pre-roll ring buffering (350ms) to eliminate initial syllable clipping
 * - Real-time PCM streaming over WebSocket to Deepgram Nova-3 STT
 * - Adaptive Voice Activity Detection (VAD) with calibrated silence turn-taking detection
 * - Seamless sentence-by-sentence Web Audio queue playback for ElevenLabs TTS
 * - Dual microphone and assistant audio amplitude analysis for orb reactivity
 * - Robust half-duplex acoustic feedback suppression and settling cooldowns
 * - Zero-latency barge-in interruption
 */
export class VoiceSession {
  constructor({
    sessionId,
    userId = "test-user",
    userData = {},
    onStateChange,
    onTranscript,
    onInterimTranscript,
    onStatusChunk,
    onTokenChunk,
    onAssistantMessage,
    onMicVolume,
    onAssistantVolume,
    onInterrupt,
    onError,
  }) {
    this.sessionId = sessionId;
    this.userId = userId;
    this.userData = userData || {};
    this.onStateChange = onStateChange || (() => {});
    this.onTranscript = onTranscript || (() => {});
    this.onInterimTranscript = onInterimTranscript || (() => {});
    this.onStatusChunk = onStatusChunk || (() => {});
    this.onTokenChunk = onTokenChunk || (() => {});
    this.onAssistantMessage = onAssistantMessage || (() => {});
    this.onMicVolume = onMicVolume || (() => {});
    this.onAssistantVolume = onAssistantVolume || (() => {});
    this.onInterrupt = onInterrupt || (() => {});
    this.onError = onError || (() => {});

    this.latestInterimText = "";
    this.state = "IDLE"; // IDLE, CONNECTING, LISTENING, USER_SPEAKING, PROCESSING, ASSISTANT_SPEAKING, ERROR
    this.ws = null;
    this.audioContext = null;
    this.mediaStream = null;
    this.sourceNode = null;
    this.processorNode = null;

    // Analyser nodes for audio reactivity
    this.playbackAnalyser = null;
    this.animFrameId = null;

    // Mute state
    this.isMuted = false;

    // Robust Adaptive VAD parameters
    this.isSpeaking = false;
    this.speechStartTime = null;
    this.silenceStartTime = null;
    this.SILENCE_DURATION_MS = 750; // 750ms silence for natural conversational turn-taking
    this.MAX_SPEECH_DURATION_MS = 25000; // 25s max utterance safeguard
    this.noiseFloor = 0.006; // Smooth background noise floor tracking
    this.consecutiveSpeechFrames = 0;
    this.SPEECH_START_FRAMES = 1; // Instant speech onset confirmation

    // Circular pre-roll buffer (keeps ~350ms of audio constantly to avoid clipping the start of speech)
    this.PRE_ROLL_FRAMES = 14;
    this.preRollBuffer = [];

    // Cooldown timestamp after playback ends to suppress speaker echo / room reverb
    this.playbackSettlingUntil = 0;

    // Audio Playback Queue & Decode Synchronization
    this.playbackQueue = [];
    this.isPlaying = false;
    this.currentSourceNode = null;
    this.serverTtsCompleted = false;
    this.pendingDecodes = 0;
    this._sentenceChunkIndex = 0;
    this._decodePromiseChain = Promise.resolve();

    this.isActive = false;
  }

  setState(newState) {
    if (this.state !== newState) {
      this.state = newState;
      this.onStateChange(this.state);
    }
  }

  setMuted(muted) {
    this.isMuted = Boolean(muted);

    // 1. Hardware audio track mute at browser driver level
    if (this.mediaStream) {
      this.mediaStream.getAudioTracks().forEach((track) => {
        track.enabled = !this.isMuted;
      });
    }

    // 2. Notify backend WebSocket so server drops partial audio buffer immediately
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "mute", is_muted: this.isMuted }));
    }

    // 3. Reset all client-side speech tracking state
    this.isSpeaking = false;
    this.consecutiveSpeechFrames = 0;
    this.speechStartTime = null;
    this.silenceStartTime = null;
    this.preRollBuffer = [];
    this.latestInterimText = "";
    this.onInterimTranscript("");

    if (this.isMuted && this.state === "USER_SPEAKING") {
      this.setState("LISTENING");
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

      // 1. Initialize Web Audio Context with system default sample rate for maximum sound card compatibility
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      this.audioContext = new AudioCtx();
      if (this.audioContext.state === "suspended") {
        await this.audioContext.resume();
      }

      // Create AnalyserNode for Assistant playback audio reactivity
      this.playbackAnalyser = this.audioContext.createAnalyser();
      this.playbackAnalyser.fftSize = 64;
      this.playbackAnalyser.smoothingTimeConstant = 0.8;
      this.playbackAnalyser.connect(this.audioContext.destination);

      // 2. Request Microphone Stream with Echo Cancellation and Noise Suppression
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Apply initial mute state to mediaStream hardware track
      if (this.isMuted && this.mediaStream) {
        this.mediaStream.getAudioTracks().forEach((track) => {
          track.enabled = false;
        });
      }

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
            user_details: this.userData || {},
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
        this.onError("Voice WebSocket connection error");
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

  /**
   * High-precision sample rate conversion from AudioContext input rate to 16kHz 16-bit linear PCM.
   */
  _downsampleTo16kPCM(inputFloat32, inRate, outRate = 16000) {
    if (inRate === outRate) {
      const pcm16 = new Int16Array(inputFloat32.length);
      for (let i = 0; i < inputFloat32.length; i++) {
        const s = Math.max(-1, Math.min(1, inputFloat32[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      return pcm16;
    }

    const sampleRateRatio = inRate / outRate;
    const newLength = Math.round(inputFloat32.length / sampleRateRatio);
    const pcm16 = new Int16Array(newLength);
    let offsetResult = 0;
    let offsetInput = 0;

    while (offsetResult < newLength) {
      const nextOffsetInput = Math.round((offsetResult + 1) * sampleRateRatio);
      let accum = 0;
      let count = 0;
      for (let i = offsetInput; i < nextOffsetInput && i < inputFloat32.length; i++) {
        accum += inputFloat32[i];
        count++;
      }
      const s = count > 0 ? Math.max(-1, Math.min(1, accum / count)) : 0;
      pcm16[offsetResult] = s < 0 ? s * 0x8000 : s * 0x7fff;
      offsetResult++;
      offsetInput = nextOffsetInput;
    }
    return pcm16;
  }

  _setupAudioProcessing() {
    if (!this.audioContext || !this.mediaStream) return;

    this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);
    const inputSampleRate = this.audioContext.sampleRate || 48000;
    const targetSampleRate = 16000;

    // Buffer size 2048 (~42ms per frame at 48kHz, ~128 samples at 16kHz)
    this.processorNode = this.audioContext.createScriptProcessor(2048, 1, 1);

    this.processorNode.onaudioprocess = (e) => {
      // 0. Ensure no microphone audio leaks to speakers
      const outputBuffer = e.outputBuffer;
      for (let c = 0; c < outputBuffer.numberOfChannels; c++) {
        outputBuffer.getChannelData(c).fill(0);
      }

      if (!this.isActive || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;

      const inputData = e.inputBuffer.getChannelData(0);

      // Compute RMS volume
      let sum = 0;
      for (let i = 0; i < inputData.length; i++) {
        sum += inputData[i] * inputData[i];
      }
      const rms = Math.sqrt(sum / inputData.length);
      this.onMicVolume(this.isMuted ? 0 : rms);

      // 1. If muted or IDLE, do not stream
      if (this.isMuted || this.state === "IDLE") return;

      // 2. HALF-DUPLEX ACOUSTIC SUPPRESSION:
      // When the assistant is speaking, playing audio, processing a response, or during the settling cooldown,
      // suppress microphone audio transmission to eliminate feedback loops
      const isAssistantActive =
        this.state === "ASSISTANT_SPEAKING" ||
        this.isPlaying ||
        this.state === "PROCESSING" ||
        Date.now() < this.playbackSettlingUntil;

      if (isAssistantActive) {
        this.isSpeaking = false;
        this.consecutiveSpeechFrames = 0;
        this.speechStartTime = null;
        this.silenceStartTime = null;
        this.preRollBuffer = [];
        return;
      }

      // 3. Convert input to 16kHz 16-bit PCM for Deepgram Streaming STT
      const pcm16 = this._downsampleTo16kPCM(inputData, inputSampleRate, targetSampleRate);
      const rawChunk = pcm16.buffer;

      // Maintain continuous background noise floor estimation
      if (!this.isSpeaking) {
        this.noiseFloor = 0.98 * this.noiseFloor + 0.02 * rms;
      }

      const now = Date.now();

      // Adaptive Dynamic VAD tuned for conversational sensitivity
      const dynamicSpeechThreshold = Math.max(0.012, this.noiseFloor * 1.6 + 0.005);
      const isVoice = rms > dynamicSpeechThreshold;

      if (!this.isSpeaking) {
        // Continuously maintain rolling circular pre-roll ring buffer during LISTENING
        this.preRollBuffer.push(rawChunk);
        if (this.preRollBuffer.length > this.PRE_ROLL_FRAMES) {
          this.preRollBuffer.shift();
        }

        if (isVoice) {
          this.consecutiveSpeechFrames += 1;

          if (this.consecutiveSpeechFrames >= this.SPEECH_START_FRAMES) {
            this.isSpeaking = true;
            this.speechStartTime = now;
            this.silenceStartTime = null;
            this.setState("USER_SPEAKING");

            // Flush complete pre-roll buffer (~350ms) to ensure zero syllables are clipped!
            while (this.preRollBuffer.length > 0) {
              const chunk = this.preRollBuffer.shift();
              this.ws.send(chunk);
            }
          }
        } else {
          this.consecutiveSpeechFrames = 0;
        }
      } else {
        // Active speech turn: stream current 16kHz PCM audio chunk directly to Deepgram
        this.ws.send(rawChunk);

        if (isVoice) {
          this.silenceStartTime = null;

          // Safety cutoff for max speech duration (25s)
          if (this.speechStartTime && now - this.speechStartTime > this.MAX_SPEECH_DURATION_MS) {
            console.log("🛑 Max speech duration reached. Processing question...");
            this.isSpeaking = false;
            this.consecutiveSpeechFrames = 0;
            this.speechStartTime = null;
            this.silenceStartTime = null;
            this.preRollBuffer = [];
            this.setState("PROCESSING");
            this.ws.send(JSON.stringify({ type: "speech_end" }));
          }
        } else {
          // Silence during active speech turn (750ms timeout for snappy, natural conversational turn-taking)
          if (!this.silenceStartTime) {
            this.silenceStartTime = now;
          } else if (now - this.silenceStartTime > this.SILENCE_DURATION_MS) {
            console.log("🛑 Speech ended (silence detected). Processing question...");
            this.isSpeaking = false;
            this.consecutiveSpeechFrames = 0;
            this.speechStartTime = null;
            this.silenceStartTime = null;
            this.preRollBuffer = [];
            this.setState("PROCESSING");
            this.ws.send(JSON.stringify({ type: "speech_end" }));
          }
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
      case "session_started":
      case "listening":
        if (this.state !== "ASSISTANT_SPEAKING" && !this.isPlaying && this.state !== "PROCESSING") {
          this.setState("LISTENING");
        }
        break;

      case "speech_started":
        if (this.state !== "USER_SPEAKING" && !this.isMuted && this.state !== "ASSISTANT_SPEAKING" && !this.isPlaying) {
          this.setState("USER_SPEAKING");
        }
        break;

      case "processing_started":
        this.setState("PROCESSING");
        break;

      case "transcript_partial":
        if (this.isMuted || this.state === "ASSISTANT_SPEAKING" || this.isPlaying) return;
        if (data.transcript) {
          this.latestInterimText = data.transcript;
          this.onInterimTranscript(data.transcript);
          if (this.state === "LISTENING") {
            this.setState("USER_SPEAKING");
          }
        }
        break;

      case "transcript_final":
        if (this.isMuted || this.state === "ASSISTANT_SPEAKING" || this.isPlaying) return;
        const resolvedText = (data.transcript || this.latestInterimText || "").trim();
        if (resolvedText) {
          this.onTranscript(resolvedText);
        }
        this.latestInterimText = "";
        this.onInterimTranscript("");
        break;

      case "transcript_empty":
        if (this.state !== "ASSISTANT_SPEAKING" && !this.isPlaying) {
          this.setState("LISTENING");
        }
        break;

      case "status_chunk":
        if (this.onStatusChunk) {
          this.onStatusChunk(data.status, data.message);
        }
        break;

      case "content_chunk":
        if (data.token) {
          this.onTokenChunk(data.token, data.user_query);
        }
        break;

      case "assistant_text":
        this.onAssistantMessage(data);
        break;

      case "tts_started":
        this.setState("ASSISTANT_SPEAKING");
        this.serverTtsCompleted = false;
        this.playbackQueue = [];
        this.pendingDecodes = 0;
        break;

      case "tts_audio_chunk":
        if (data.audio) {
          this._queueAudioChunk(data.audio);
        }
        break;

      case "tts_completed":
        console.log("🔊 Backend indicated all TTS chunks sent.");
        this.serverTtsCompleted = true;
        this._checkPlaybackCompletion();
        break;

      case "interrupted":
        this._stopAudioPlayback();
        this.setState("USER_SPEAKING");
        break;

      case "error":
        console.error("Server voice error:", data.message);
        this.onError(data.message || "An error occurred");
        if (!this.isPlaying && this.playbackQueue.length === 0) {
          this.setState("LISTENING");
        }
        break;

      default:
        break;
    }
  }

  _queueAudioChunk(base64Audio) {
    if (!this.audioContext || this.state === "IDLE" || !base64Audio) return;

    this.pendingDecodes++;

    this._decodePromiseChain = this._decodePromiseChain
      .then(async () => {
        if (!this.audioContext || this.state === "IDLE") {
          this.pendingDecodes = Math.max(0, this.pendingDecodes - 1);
          return;
        }

        if (this.audioContext.state === "suspended") {
          try {
            await this.audioContext.resume();
          } catch (e) {}
        }

        const binaryString = atob(base64Audio);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
          bytes[i] = binaryString.charCodeAt(i);
        }

        const bufferCopy = bytes.buffer.slice(0);
        let audioBuffer = null;
        try {
          audioBuffer = await new Promise((resolve, reject) => {
            this.audioContext.decodeAudioData(bufferCopy, resolve, reject);
          });
        } catch (decErr) {
          try {
            audioBuffer = await this.audioContext.decodeAudioData(bytes.buffer.slice(0));
          } catch (e2) {
            console.error("Audio decode error:", e2);
          }
        }

        this.pendingDecodes = Math.max(0, this.pendingDecodes - 1);

        if (audioBuffer) {
          this.playbackQueue.push(audioBuffer);
          if (!this.isPlaying) {
            this._playNextInQueue();
          }
        } else {
          this._checkPlaybackCompletion();
        }
      })
      .catch((e) => {
        console.error("Failed to decode audio chunk in chain:", e);
        this.pendingDecodes = Math.max(0, this.pendingDecodes - 1);
        this._checkPlaybackCompletion();
      });
  }

  _playNextInQueue() {
    if (this.playbackQueue.length === 0) {
      this.isPlaying = false;
      this._checkPlaybackCompletion();
      return;
    }

    this.isPlaying = true;
    this.setState("ASSISTANT_SPEAKING");

    if (this.audioContext && this.audioContext.state === "suspended") {
      this.audioContext.resume().catch((e) => console.warn("Could not resume AudioContext:", e));
    }

    const buffer = this.playbackQueue.shift();

    if (!this.audioContext || !this.playbackAnalyser) {
      this.isPlaying = false;
      this._checkPlaybackCompletion();
      return;
    }

    const source = this.audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(this.playbackAnalyser);

    this.currentSourceNode = source;

    let hasEnded = false;
    const finishCurrentNode = () => {
      if (hasEnded) return;
      hasEnded = true;
      if (this.currentSourceNode === source) {
        this.currentSourceNode = null;
      }
      setTimeout(() => {
        if (this.isActive) {
          this._playNextInQueue();
        }
      }, 20);
    };

    source.onended = finishCurrentNode;

    // Safety timeout in case onended doesn't fire
    const durationMs = (buffer.duration || 1) * 1000;
    setTimeout(() => {
      if (!hasEnded && this.currentSourceNode === source) {
        finishCurrentNode();
      }
    }, durationMs + 1000);

    try {
      source.start(0);
    } catch (err) {
      console.warn("Source start error:", err);
      finishCurrentNode();
    }
  }

  _checkPlaybackCompletion() {
    if (
      this.serverTtsCompleted &&
      this.pendingDecodes === 0 &&
      this.playbackQueue.length === 0 &&
      !this.isPlaying &&
      (this.state === "ASSISTANT_SPEAKING" || this.state === "PROCESSING")
    ) {
      this._handlePlaybackCompleted();
    }
  }

  _handlePlaybackCompleted() {
    console.log("🏁 All assistant TTS audio played completely -> Returning cleanly to Listening");
    this._stopAudioPlayback();
    // 350ms acoustic grace period to prevent room speaker reverb from triggering speech onset
    this.playbackSettlingUntil = Date.now() + 350;
    this.isSpeaking = false;
    this.consecutiveSpeechFrames = 0;
    this.silenceStartTime = null;
    this.preRollBuffer = [];
    this.latestInterimText = "";
    this.setState("LISTENING");

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "playback_finished" }));
    }
  }

  _stopAudioPlayback() {
    this.playbackQueue = [];
    this.isPlaying = false;
    this.pendingDecodes = 0;
    if (this.currentSourceNode) {
      try {
        this.currentSourceNode.stop();
        this.currentSourceNode.disconnect();
      } catch (e) {}
      this.currentSourceNode = null;
    }
  }

  prepareSentenceStreaming() {
    this._stopAudioPlayback();
    this.serverTtsCompleted = false;
    this.pendingDecodes = 0;
    this.playbackQueue = [];
    this._sentenceChunkIndex = 0;
    this.isSpeaking = false;
    this.preRollBuffer = [];
    this.setState("ASSISTANT_SPEAKING");
  }

  queueSentence(sentenceText, isLast = false) {
    if (!sentenceText || !sentenceText.trim() || !this.isActive) return;
    this.setState("ASSISTANT_SPEAKING");
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: "tts_sentence",
          sentence: sentenceText.trim(),
          chunk_index: this._sentenceChunkIndex++,
          is_last: isLast,
        })
      );
    }
  }

  finishSentences() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: "tts_sentence",
          sentence: "",
          is_last: true,
        })
      );
    }
  }

  speak(text) {
    if (!text || !text.trim() || !this.isActive) {
      if (this.state === "PROCESSING") {
        this.setState("LISTENING");
      }
      return;
    }
    this._stopAudioPlayback();
    this.serverTtsCompleted = false;
    this.pendingDecodes = 0;
    this.playbackQueue = [];
    this.setState("ASSISTANT_SPEAKING");
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: "tts_request",
          text: text.trim(),
        })
      );
    }
  }

  interrupt() {
    console.log("⚡ [VoiceSession] User requested speech interruption.");
    this._stopAudioPlayback();
    this.serverTtsCompleted = true;
    this.isSpeaking = false;
    this.silenceStartTime = null;
    this.preRollBuffer = [];
    this.setState("LISTENING");
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "interrupt" }));
    }
    try {
      this.onInterrupt();
    } catch (e) {
      console.error("Error in onInterrupt callback:", e);
    }
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
