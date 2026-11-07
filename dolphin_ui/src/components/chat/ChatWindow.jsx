import {
  Box,
  Typography,
  IconButton,
  TextareaAutosize,
  CircularProgress,
} from "@mui/material";
import React, { useEffect, useRef, useState, useCallback } from "react";
import { SendIcon } from "../../assets/svgIcons/sendIcon";
import { marked } from "marked";
import DOMPurify from "dompurify";
import WelcomeChatScreen from "./WelcomeChatScreen";
import {
  ensureSession,
  sendMessage,
  saveSession,
  getSavedSessions,
  submitMessageFeedback,
  fetchTopicDetails,
} from "../../api/fetchApi";
import ChatMessage, { markdownContainerSx } from "./ChatMessage";
import MediaInspectorDrawer from "./MediaInspectorDrawer";
import { resolveImageUrl } from "../../api/config";
import { useThemeMode } from "../../context/ThemeModeContext";
import { Message } from "../../assets/svgIcons/message";
import { Saveoutlined } from "../../assets/svgIcons/SaveIconOutlined";
import { SaveIcon } from "../../assets/svgIcons/Saveicon";
import DolphinIconW from "../../assets/images/dolphin_w.png";
import DolphinIconB from "../../assets/images/dolphin_b.png";
import { getContentWidth } from "../../theme/layoutScale";
import { Dialog, DialogContent, DialogActions, Button } from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import CloseIcon from "@mui/icons-material/Close";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";
import StopRoundedIcon from "@mui/icons-material/StopRounded";

const formatGlossaryContent = (content) => {
  if (!content) return "";
  // Only convert standalone, unbulleted raw glossary lines (e.g., "ECDIS: Electronic Chart...")
  // Do NOT touch lines that are already markdown list items (- , * , • ) or already bolded (**...)
  const lines = content.split(/\r?\n/);
  const formattedLines = lines.map((line) => {
    const trimmed = line.trim();
    if (
      !trimmed ||
      /^[•\-\*\⁃\◦\▪\▫\–\d\.]/.test(trimmed) ||
      trimmed.startsWith("#") ||
      trimmed.startsWith("**")
    ) {
      return line;
    }
    const match = trimmed.match(/^([A-Z][A-Za-z0-9\s]{1,30}):\s+(.+)$/);
    if (match) {
      const term = match[1].trim();
      const desc = match[2].trim();
      return `- **${term}**: ${desc}`;
    }
    return line;
  });
  return formattedLines.join("\n");
};

export const formatMarkdownContent = (content) => {
  if (!content) return "";

  // ── Protection Layer: Preserve Images, Data URIs, and Code Blocks ──
  // Prevents downstream formula/glossary regexes from corrupting Base64 image payloads or code blocks
  const protectedTokens = [];
  const mask = (match) => {
    const token = `@@PROTECTED_CONTENT_${protectedTokens.length}@@`;
    protectedTokens.push(match);
    return token;
  };

  // 1. Mask code blocks first (fenced and inline)
  let masked = content.replace(/```[\s\S]*?```/g, mask);
  masked = masked.replace(/`[^`\n]+`/g, mask);

  // 2. Mask markdown images: ![alt](url)
  masked = masked.replace(/!\[[\s\S]*?\]\([\s\S]*?\)/g, mask);

  // 3. Mask HTML img tags: <img ... />
  masked = masked.replace(/<img\b[^>]*\/?>/gi, mask);

  // 4. Mask any standalone data URIs
  masked = masked.replace(/data:image\/[^;]+;base64,[a-zA-Z0-9+/=]+/gi, mask);

  let formatted = formatGlossaryContent(masked);

  // Remove thinking text
  formatted = formatted.replace(/Dolphin is thinking\.\.\./gi, "");

  // Clean up broken inline step linebreaks e.g. (step\n7. and ... -> (step 7) and ...
  formatted = formatted.replace(/\(step\s*[\r\n]+\s*(\d+)[\.\)]?/gi, "(step $1)");
  formatted = formatted.replace(/\(step\s+(\d+)\s*[\r\n]+\s*(\d+)[\.\)]?/gi, "(step $1, $2)");

  // Ensure markdown headings start on new lines with blank lines before & after
  formatted = formatted.replace(/([^\n])\s*(#{1,6}\s+[^\n]+)/g, "$1\n\n$2\n\n");

  // Common standalone section headers (e.g., Advantages, Disadvantages, Precautions, etc.)
  formatted = formatted.replace(
    /(^|\n)\s*(Advantages|Disadvantages|Merits|Demerits|Key Points|Precautions|Procedures|Requirements|Overview|Summary|Safety Controls|Emergency Procedures|Operational Guidelines|Responsibilities|Checklist)(?::|\.?\s*[\n\r]|$)/gi,
    "$1\n\n### $2\n\n",
  );

  // If a title is merged mid-paragraph after a sentence ending period (e.g., "...operation. Unloading Operations The unloading process starts...")
  formatted = formatted.replace(
    /(?<=[.?!])\s+([A-Z][A-Za-z0-9&/\-\s]{2,50}?)\s+(The |This |Accidental |In terms of |During |Before |After |When |It is |These |Proper |Safety |All |Step )/g,
    "\n\n### $1\n\n$2",
  );

  // If a title is at the start of a block/line followed by a sentence (e.g., "Loading and Unloading Procedures Load and Discharge Plan Accidental stress...")
  formatted = formatted.replace(
    /(^|\n{2,})([A-Z][A-Za-z0-9&/\-\s]{2,60}?)\s+(The |This |Accidental |In terms of |During |Before |After |When |It is |These |Proper |Safety |All |Step )/g,
    "$1### $2\n\n$3",
  );

  // Standalone line that looks like a title (Title Cased or with colon, not a list item)
  formatted = formatted.replace(
    /(^|\n{2,})([A-Z][A-Za-z0-9\s,&/\-]{2,50})(?::|\s*\n)\s*(?=[A-Z])/g,
    "$1### $2\n\n",
  );

  // Fix inline numbered steps in parentheses (1) -> 1.
  formatted = formatted.replace(/(?:^|[ \t]+)\((\d+)\)[ \t]+/g, "\n$1. ");

  // Attribution / organization lines in parenthesis e.g. "International Association of Classification Societies Ltd (IACS)." alone on line
  formatted = formatted.replace(
    /(^|\n)\s*([A-Z][A-Za-z\s]+(?:Ltd|Inc|Org|IACS|IMO|SOLAS|MARPOL|STCW|ISGOTT|ICS)\s*(?:\([A-Z0-9]+\))?\.?)\s*($|\n)/g,
    "$1\n> **$2**\n$3",
  );

  // Remove orphan "(" appearing alone on a line
  formatted = formatted.replace(/^\s*\(\s*$/gm, "");

  // Remove trailing "(" at end of a line
  formatted = formatted.replace(/\s+\($/gm, "");

  // Bring source references to the same line as the preceding text
  formatted = formatted.replace(
    /\n+\s*(@@SOURCE_REF_\d+@@|\[\[\s*Ref:?\s*\d+\s*\]\])/gi,
    " $1",
  );

  // Ensure specific terms requested by user are always bolded
  formatted = formatted.replace(/\b(company name|vessel name|course name)\b/gi, "**$1**");

  // Structure lists and sub-bullet indentation cleanly
  const rawLines = formatted.split(/\r?\n/);
  const processedLines = [];
  let inNumberedContext = false;

  for (let i = 0; i < rawLines.length; i++) {
    const rawLine = rawLines[i];
    const trimmed = rawLine.trim();

    // Check if line is a numbered item e.g. "1. Item" or "1) Item"
    const numMatch = rawLine.match(/^(\s*)(\d+)[\.\)]\s+(.*)$/);
    // Check if line is a bullet item e.g. "- item", "* item", "• item"
    const bulletMatch = rawLine.match(/^(\s*)[•\-\*\⁃\◦\▪\▫\–]\s+(.*)$/);

    if (numMatch) {
      inNumberedContext = true;
      processedLines.push(`${numMatch[2]}. ${numMatch[3]}`);
    } else if (bulletMatch) {
      const existingIndent = bulletMatch[1] || "";
      const text = bulletMatch[2];
      if (inNumberedContext) {
        // Nested sub-bullet under a numbered list item
        processedLines.push(`   - ${text}`);
      } else if (existingIndent.length >= 2) {
        // Retain existing sub-bullet indentation
        processedLines.push(`   - ${text}`);
      } else {
        // Standard top-level bullet point
        processedLines.push(`- ${text}`);
      }
    } else if (trimmed === "") {
      // Lookahead: if next non-empty line is a bullet and we're in a numbered item, omit empty line to keep list tight
      let nextIsBullet = false;
      for (let j = i + 1; j < rawLines.length; j++) {
        const nextTrimmed = rawLines[j].trim();
        if (nextTrimmed !== "") {
          nextIsBullet = /^[•\-\*\⁃\◦\▪\▫\–]\s+/.test(nextTrimmed);
          break;
        }
      }
      if (inNumberedContext && nextIsBullet) {
        // Skip blank line between numbered item and its sub-bullets
        continue;
      }
      processedLines.push("");
    } else {
      // Regular text or heading
      if (/^(?:#{1,6}\s+|[A-Z][a-z]|Note:|Important:)/.test(trimmed)) {
        inNumberedContext = false;
      }
      processedLines.push(rawLine);
    }
  }

  formatted = processedLines.join("\n");

  // Remove excessive blank lines
  formatted = formatted.replace(/\n{3,}/g, "\n\n");

  // Balance unclosed bold and italic markers
  const boldMatches = formatted.match(/\*\*/g);
  if (boldMatches && boldMatches.length % 2 !== 0) {
    formatted += "**";
  }
  const italicMatches = formatted.replace(/\*\*/g, "").match(/\*/g);
  if (italicMatches && italicMatches.length % 2 !== 0) {
    formatted += "*";
  }

  // ── Dynamic Maritime Formula & Subscript Formatting ──
  // 1. Dynamic wind/heeling levers: lw1, lw2, l_w1, l_w2 -> <var>l</var><sub>w1</sub>, <var>l</var><sub>w2</sub>, etc.
  formatted = formatted.replace(/(?<!<var[^>]*>)\b[lL]_?w([0-9a-zA-Z]+)\b(?!<\/sub>)/g, "<var>l</var><sub>w$1</sub>");
  formatted = formatted.replace(/\bl(?=<sub>w[0-9a-zA-Z]+<\/sub>)/gi, "<var>l</var>");

  // 2. Universal Greek variable + Subscript pattern: ϕ0, ϕ1, ϕ2, ϕf, θf, etc. (dynamic for any symbol & index)
  formatted = formatted.replace(
    /(?<=^|[^a-zA-Z0-9<>/])([ϕφθλαβγμρσΔ])_?([0-9a-z])(?![a-zA-Z0-9<>/])/gi,
    "<var>$1</var><sub>$2</sub>"
  );

  // 3. Common maritime variables with subscripts: GM0, GM_0, GMo
  formatted = formatted.replace(/\b(?:GMo|GM0|GM_0)\b(?!<\/sub>)/g, "<var>GM</var><sub>0</sub>");

  // 4. Universal units with power exponents: m3, m2, cm3, cm2, mm3, etc.
  formatted = formatted.replace(/\b(\d+)\s*(m|cm|mm|km)([23])\b(?!<\/sup>)/gi, "$1 $2<sup>$3</sup>");

  // 5. Maritime emissions, gases, and chemicals
  formatted = formatted.replace(/\bCO2\b(?!<\/sub>)/g, "CO<sub>2</sub>");
  formatted = formatted.replace(/\bSOx\b(?!<\/sub>)/g, "SO<sub>x</sub>");
  formatted = formatted.replace(/\bNOx\b(?!<\/sub>)/g, "NO<sub>x</sub>");
  formatted = formatted.replace(/\bH2S\b(?!<\/sub>)/g, "H<sub>2</sub>S");
  formatted = formatted.replace(/\bCH4\b(?!<\/sub>)/g, "CH<sub>4</sub>");
  formatted = formatted.replace(/\bO2\b(?!<\/sub>)/g, "O<sub>2</sub>");
  formatted = formatted.replace(/\bN2\b(?!<\/sub>)/g, "N<sub>2</sub>");
  formatted = formatted.replace(/\bH2O\b(?!<\/sub>)/g, "H<sub>2</sub>O");

  // Wrap remaining standalone mathematical variables and Greek symbols in <var>
  formatted = formatted.replace(/(?<!<var[^>]*>)(ϕ|φ|θ|Δ|α|β|γ|λ|μ|π|ρ|σ|Σ|Ω)(?!<\/var>)/g, "<var>$1</var>");

  // ── Restoration Layer: Restore Protected Images, Data URIs, and Code Blocks ──
  for (let i = protectedTokens.length - 1; i >= 0; i--) {
    formatted = formatted.replace(`@@PROTECTED_CONTENT_${i}@@`, () => protectedTokens[i]);
  }

  return formatted.trim();
};
export const sanitizeMarkdown = (content, skipFormatting = false) => {
  if (!content) return "";

  let finalContent = skipFormatting ? content : formatMarkdownContent(content);

  const html = marked.parse(finalContent, {
    gfm: true,
    breaks: true,
  });

  return DOMPurify.sanitize(html, {
    ADD_TAGS: ["input", "sub", "sup", "var"],
    ADD_ATTR: ["type", "checked", "disabled", "style", "class"],
    ADD_DATA_URI_TAGS: ["img"],
    ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|cid|xmpp|data):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
  });
};

// ─── Normalisers ──
const normalizeVideo = (v) => ({
  title: v.title || v.Title || "",
  url: v.url || v.Url || v.videourl || "",
  thumbnail: v.thumbnail || v.Thumbnail || "",
  video_id: String(v.video_id || v.Id || v.id || (v.url ? v.url.split("/").pop().split("?")[0].replace(/\.mp4$/i, "") : "")),
  topic_code: String(v.topic_code || ""),
  topic_name: String(v.topic_name || ""),
  source_type: String(v.source_type || "curriculum"),
  content: String(v.content || ""),
});

const normalizeImage = (img) => {
  if (!img) return { title: "", url: "", thumbnail: "" };
  if (typeof img === "string") {
    const src = resolveImageUrl(img);
    return { title: "Topic image", url: src, thumbnail: src };
  }
  const imageSrc = img.base64
    ? (img.base64.startsWith("data:")
        ? img.base64
        : `data:image/${img.format || "jpeg"};base64,${img.base64}`)
    : resolveImageUrl(img.url || img.Url || "");

  const thumbSrc = img.thumbnail
    ? resolveImageUrl(img.thumbnail)
    : (img.Url || img.url ? resolveImageUrl(img.Url || img.url) : imageSrc);

  return {
    title: img.title || img.Title || "",
    url: imageSrc,
    thumbnail: thumbSrc,
  };
};

const normalizePdf = (pdf) => {
  if (!pdf) return { title: "", link: "" };
  if (typeof pdf === "string") {
    return { title: "Document", link: pdf };
  }
  return {
    title: pdf.title || pdf.Title || "",
    link: pdf.link || pdf.Link || pdf.url || pdf.Url || "",
  };
};


const EMPTY_LIVE = {
  active: false,
  content: "",
  company_content: "",
  suggestions: [],
  media: { videos: [], images: [], pdfs: [] },
  topics: [],
  transcripts: [],
  matched_pdf_chunks: [],
  checkLicCoursesData: null
};

// Factory so we always get a fresh object (avoids accidental mutation sharing)
const EMPTY_ACC = () => ({
  content: "",
  company_content: "",
  suggestions: [],
  media: { videos: [], images: [], pdfs: [] },
  topics: [],
  pendingTopics: [],
  transcripts: [],
  matched_pdf_chunks: [],
  checkLicCoursesData: null,
});

// ─── Component ────
const ChatWindow = ({
  currentSessionData,
  currentSessionId,
  setCurrentSessionId,
  activeIndex,
  messages,
  setmessages,
  setDisableNewChat,
  fetchSessions,
  setActiveIndex,
  loading,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [liveMessage, setLiveMessage] = useState(EMPTY_LIVE);
  const [showInitialThinking, setShowInitialThinking] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Dolphin is thinking...");
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);
  const [savedSessions, setSavedSessions] = useState([]);
  const [saveDialog, setSaveDialog] = useState({
    open: false,
    message: "",
    isError: false,
  });

  const [sourcesData, setSourcesData] = useState({
    open: false,
    loading: false,
    topics: [],
    selectedTopicCode: null,
    detailTopic: null,
  });

  // ── Testing: Media & Topic Inspector Drawer ──
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [inspectorData, setInspectorData] = useState(null);

  const handleOpenInspector = useCallback((data) => {
    setInspectorData(data);
    setInspectorOpen(true);
  }, []);

  const handleCloseInspector = useCallback(() => {
    setInspectorOpen(false);
  }, []);

  // Close the sources panel when a new chat is started
  useEffect(() => {
    if (!currentSessionId && (!messages || messages.length === 0)) {
      setSourcesData((prev) => ({ ...prev, open: false, detailTopic: null }));
    }
  }, [currentSessionId, messages]);

  const { mode, fontLevel } = useThemeMode();

  const containerRef = useRef(null);
  const bottomRef = useRef(null);
  const abortControllerRef = useRef(null);
  const statusTimerRef = useRef(null);
  const alreadyCommittedRef = useRef(false);
  const userScrolledRef = useRef(false);
  const hasContentStartedRef = useRef(false);
  const sidebarLoadedRef = useRef(false);
  const accRef = useRef(EMPTY_ACC());

  // ── Sync session messages ────
  useEffect(() => {
    setmessages(
      Array.isArray(currentSessionData?.messages)
        ? currentSessionData.messages
        : [],
    );
  }, [currentSessionData, setmessages]);

  // ── Auto-scroll ───────
  useEffect(() => {
    if (!autoScrollEnabled) return;
    const el = containerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [
    messages,
    liveMessage.content,
    liveMessage.active,
    autoScrollEnabled,
    showInitialThinking,
    statusMessage,
  ]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onScroll = () => {
      const dist = el.scrollHeight - el.scrollTop - el.clientHeight;
      if (dist > 80) {
        userScrolledRef.current = true;
        setAutoScrollEnabled(false);
      } else {
        userScrolledRef.current = false;
        setAutoScrollEnabled(true);
      }
    };
    el.addEventListener("scroll", onScroll);
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // ── Saved sessions ──
  const isCurrentSaved =
    Boolean(currentSessionData?.is_saved) ||
    savedSessions.some((s) => s.session_id === currentSessionId);

  useEffect(() => {
    getSavedSessions()
      .then((res) => setSavedSessions(res.saved_sessions || []))
      .catch((err) => console.error("Failed to load saved sessions", err));
  }, [currentSessionId]);

  // ── Feedback submission handler ──
  const handleFeedbackSubmit = useCallback(async (feedbackData) => {
    try {
      const response = await submitMessageFeedback(feedbackData);
      console.log("Feedback submitted:", feedbackData);
      return response;
    } catch (error) {
      console.error("Failed to submit feedback:", error);
      throw error;
    }
  }, []);

  // ── Shared UI reset (called by both handleStop and onDone/onError) ─────────
  const resetStreamingUI = useCallback(() => {
    if (statusTimerRef.current) {
      clearInterval(statusTimerRef.current);
      statusTimerRef.current = null;
    }
    setLiveMessage(EMPTY_LIVE);
    setShowInitialThinking(false);
    setStatusMessage("Dolphin is thinking...");
    setIsStreaming(false);
    setDisableNewChat(false);
  }, [setDisableNewChat]);

  // ── Termination / Stop Chat handler ──
  const handleStop = useCallback(() => {
    if (statusTimerRef.current) {
      clearInterval(statusTimerRef.current);
      statusTimerRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    alreadyCommittedRef.current = true;
    const acc = accRef.current;
    if (acc.content || acc.company_content) {
      setmessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: acc.content,
          company_content: acc.company_content,
          videos: acc.media.videos || [],
          images: acc.media.images || [],
          pdfs: acc.media.pdfs || [],
          topics: acc.topics || [],
          transcripts: acc.transcripts || [],
          matched_pdf_chunks: acc.matched_pdf_chunks || [],
          question_suggestions: acc.suggestions || [],
          checkLicCoursesData: acc.checkLicCoursesData,
          timestamp: new Date().toISOString(),
          mediaLoaded: true,
        },
      ]);
    }
    accRef.current = EMPTY_ACC();
    resetStreamingUI();
  }, [resetStreamingUI, setmessages]);

  // Handle topic click
  const handleTopicClick = useCallback(
    async (topicCode, allMessageTopics = []) => {
      setSourcesData((prev) => ({
        ...prev,
        open: true,
        loading: true,
        selectedTopicCode: topicCode,
      }));

      try {
        const data = await fetchTopicDetails(topicCode);
        const clickedIndex = allMessageTopics.indexOf(topicCode);
        const resolvedTopic = {
          code: topicCode,
          index: clickedIndex >= 0 ? clickedIndex + 1 : 1,
          topicName: data.topic_name || topicCode,
          courseName: data.course_name || "",
          content:
            data.topic_content ||
            data.content ||
            data.text ||
            "No content found.",
          _fetched: true,
        };

        setSourcesData((prev) => ({
          ...prev,
          topics: [resolvedTopic],
          totalSources: allMessageTopics.length,
          loading: false,
          detailTopic: null,
        }));
      } catch (err) {
        console.error("Failed to fetch topics details:", err);
        setSourcesData((prev) => ({
          ...prev,
          loading: false,
        }));
      }
    },
    [],
  );

  // ── Send ───
  const handleSend = useCallback(
    async (queryOverride) => {
      if (isStreaming) return;

      const messageText = (queryOverride ?? searchQuery).trim();
      if (!messageText) return;

      alreadyCommittedRef.current = false;
      accRef.current = EMPTY_ACC();
      hasContentStartedRef.current = false;
      sidebarLoadedRef.current = false;

      setmessages((prev = []) => [
        ...prev,
        {
          role: "user",
          content: messageText,
          timestamp: new Date().toISOString(),
        },
      ]);

      setSearchQuery("");
      setIsStreaming(true);
      setDisableNewChat(true);
      setAutoScrollEnabled(true);
      userScrolledRef.current = false;

      setStatusMessage("Dolphin is thinking...");
      setShowInitialThinking(true);
      setLiveMessage({ ...EMPTY_LIVE, active: false });

      // Progressive fallback timer to ensure status keeps moving if network has latency
      let statusStep = 0;
      const statusTimer = setInterval(() => {
        statusStep += 1;
        if (statusStep === 1) {
          setStatusMessage((prev) =>
            prev === "Dolphin is thinking..."
              ? "Dolphin is fetching relevant information..."
              : prev
          );
        } else if (statusStep >= 3) {
          setStatusMessage((prev) =>
            prev === "Dolphin is thinking..." ||
              prev === "Dolphin is fetching relevant information..."
              ? "Dolphin is generating response..."
              : prev
          );
        }
      }, 2500);
      statusTimerRef.current = statusTimer;

      try {
        const sessionId = currentSessionId
          ? await ensureSession(currentSessionId)
          : await ensureSession();

        setCurrentSessionId(sessionId);
        localStorage.setItem("active_session_id", sessionId);

        if (!currentSessionId && fetchSessions) {
          await fetchSessions("", true);
          setActiveIndex?.(0);
        }

        abortControllerRef.current = new AbortController();

        await sendMessage(
          sessionId,
          messageText,
          abortControllerRef.current.signal,
          {
            onStatus: (msg) => {
              if (msg) {
                setStatusMessage(msg);
              }
            },

            onContentToken: (token, streamType) => {
              if (streamType === "content") {
                clearInterval(statusTimer);
                setShowInitialThinking(false);
                hasContentStartedRef.current = true;

                if (
                  !sidebarLoadedRef.current &&
                  !currentSessionId &&
                  fetchSessions
                ) {
                  sidebarLoadedRef.current = true;
                  setTimeout(() => {
                    fetchSessions("", true);
                    setActiveIndex?.(0);
                  }, 300);
                }

                accRef.current.content += token;
                setLiveMessage((prev) => ({
                  ...prev,
                  active: true,
                  content: accRef.current.content,
                }));
              }
            },

            onCompanyContent: (contentChunk) => {
              accRef.current.company_content += contentChunk;
              setLiveMessage((prev) => ({
                ...prev,
                company_content: accRef.current.company_content,
              }));
            },

            onSuggestions: (suggestions) => {
              accRef.current.suggestions = suggestions;
              setLiveMessage((prev) => ({ ...prev, suggestions }));
            },

            onMedia: (rawMedia) => {
              const normVideos = (rawMedia.videos || []).map(normalizeVideo);
              accRef.current.media = {
                videos: normVideos,
                images: (rawMedia.images || []).map(normalizeImage),
                pdfs: (rawMedia.pdfs || []).map(normalizePdf),
              };
              if (rawMedia.topics && Array.isArray(rawMedia.topics)) {
                for (const t of rawMedia.topics) {
                  const tObj = typeof t === "object" ? t : { code: String(t), name: String(t) };
                  if (!accRef.current.topics.some((x) => (typeof x === "object" ? x.code === tObj.code : x === tObj.code))) {
                    accRef.current.topics.push(tObj);
                  }
                }
              }
              setLiveMessage((prev) => ({
                ...prev,
                media: accRef.current.media,
                topics: [...accRef.current.topics],
              }));
            },

            onTopic: (topicData) => {
              const { code, name } =
                typeof topicData === "string"
                  ? { code: topicData, name: topicData }
                  : (topicData || {});

              if ((code && String(code).trim()) || (name && String(name).trim())) {
                const topicObj = {
                  code: String(code || "").trim(),
                  name: String(name || "").trim(),
                };
                const alreadyExists = accRef.current.topics.some(
                  (t) => (typeof t === "object" ? t.code === topicObj.code : t === topicObj.code)
                );
                if (!alreadyExists) {
                  accRef.current.topics.push(topicObj);
                }
                setLiveMessage((prev) => ({
                  ...prev,
                  topics: [...accRef.current.topics],
                }));
              }
            },

            onCheckLicCourses: (data) => {
              accRef.current.checkLicCoursesData = data;
              setLiveMessage((prev) => ({
                ...prev,
                checkLicCoursesData: data,
              }));
            },

            onTranscriptResult: (chunks) => {
              accRef.current.transcripts = chunks;
              setLiveMessage((prev) => ({
                ...prev,
                transcripts: accRef.current.transcripts,
              }));
            },

            onPdfResult: (chunks) => {
              accRef.current.matched_pdf_chunks = chunks;
              setLiveMessage((prev) => ({
                ...prev,
                matched_pdf_chunks: accRef.current.matched_pdf_chunks,
              }));
            },

            onError: (errMsg) => {
              clearInterval(statusTimer);
              console.error("SSE error:", errMsg);
              setmessages((prev) => [
                ...prev,
                {
                  role: "assistant",
                  content: "Sorry, something went wrong. Please try again.",
                  timestamp: new Date().toISOString(),
                  videos: [],
                  images: [],
                  pdfs: [],
                  question_suggestions: [],
                  mediaLoaded: true,
                },
              ]);
              resetStreamingUI();
            },

            onDone: async () => {
              clearInterval(statusTimer);
              setShowInitialThinking(false);

              if (!alreadyCommittedRef.current) {
                const acc = accRef.current;
                setmessages((prev) => [
                  ...prev,
                  {
                    role: "assistant",
                    content: acc.content,
                    company_content: acc.company_content,
                    videos: acc.media.videos,
                    images: acc.media.images,
                    pdfs: acc.media.pdfs,
                    topics: acc.topics,
                    transcripts: acc.transcripts,
                    matched_pdf_chunks: acc.matched_pdf_chunks || [],
                    question_suggestions: acc.suggestions || [],
                    checkLicCoursesData: acc.checkLicCoursesData,
                    timestamp: new Date().toISOString(),
                    mediaLoaded: true,
                  },
                ]);
              }

              accRef.current = EMPTY_ACC();
              resetStreamingUI();
              fetchSessions?.("", true);
            },
          },
        );
      } catch (err) {
        clearInterval(statusTimer);
        if (err.name === "AbortError" || err.name === "CanceledError") return;

        console.error("handleSend error:", err);
        setmessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "Sorry, something went wrong. Please try again.",
            timestamp: new Date().toISOString(),
            videos: [],
            images: [],
            pdfs: [],
            question_suggestions: [],
            mediaLoaded: true,
          },
        ]);
        resetStreamingUI();
      }
    },
    [
      isStreaming,
      searchQuery,
      currentSessionId,
      setmessages,
      setCurrentSessionId,
      setDisableNewChat,
      fetchSessions,
      setActiveIndex,
      resetStreamingUI,
    ],
  );

  // ── Save chat ───
  const handleSaveChat = async () => {
    if (!currentSessionId) {
      setSaveDialog({
        open: true,
        message: "No session to save",
        isError: true,
      });
      return;
    }
    try {
      const res = await saveSession(currentSessionId);
      const isSaved = Boolean(res.is_saved);

      setSaveDialog({
        open: true,
        message: isSaved ? "Chat saved successfully" : "Removed from saved chats",
        isError: false,
      });

      // Update local state immediately
      if (isSaved) {
        setSavedSessions((prev) => {
          if (prev.some((s) => s.session_id === currentSessionId)) return prev;
          return [...prev, { session_id: currentSessionId, ...currentSessionData, is_saved: true }];
        });
      } else {
        setSavedSessions((prev) => prev.filter((s) => s.session_id !== currentSessionId));
      }

      if (currentSessionData) {
        currentSessionData.is_saved = isSaved;
      }

      await fetchSessions?.();
      const savedRes = await getSavedSessions();
      if (savedRes && Array.isArray(savedRes.saved_sessions)) {
        setSavedSessions(savedRes.saved_sessions);
        const savedIds = new Set(
          savedRes.saved_sessions.map((s) => s.session_id),
        );
        fetchSessions?.(undefined, (prev) =>
          prev.map((s) => ({ ...s, is_saved: savedIds.has(s.session_id) })),
        );
      }
    } catch {
      setSaveDialog({
        open: true,
        message: "Failed to save chat",
        isError: true,
      });
    }
  };

  // ── Sub-components ──
  const ProcessStatusBubble = ({ message }) => (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        width: "fit-content",
        animation: "fadeIn 0.25s ease-in",
        "@keyframes fadeIn": {
          from: { opacity: 0, transform: "translateY(6px)" },
          to: { opacity: 1, transform: "translateY(0)" },
        },
      }}
    >
      <Box
        sx={{
          width: 40,
          height: 40,
          borderRadius: "50%",
          backgroundColor: "primary.main",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
        }}
      >
        <Box
          component="img"
          src={DolphinIconW}
          alt="Dolphin"
          sx={{
            width: 24,
            height: 24,
            animation: "swimBubble 2s ease-in-out infinite",
            "@keyframes swimBubble": {
              "0%": { transform: "translateY(0px) rotate(0deg)" },
              "25%": { transform: "translateY(-3px) rotate(-10deg)" },
              "50%": { transform: "translateY(0px) rotate(0deg)" },
              "75%": { transform: "translateY(3px) rotate(10deg)" },
              "100%": { transform: "translateY(0px) rotate(0deg)" },
            },
          }}
        />
      </Box>
      <Box
        sx={{
          px: 2.2,
          py: 1.4,
          borderRadius: 3,
          backgroundColor: "background.chatbackground",
          color: "primary.main",
          fontWeight: 500,
          fontSize: 14,
          display: "flex",
          alignItems: "center",
          gap: 0.5,
          boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
        }}
      >
        <Typography
          component="span"
          sx={{
            fontSize: 14,
            fontWeight: 500,
            color: "primary.main",
          }}
        >
          {message || "Dolphin is thinking..."}
        </Typography>
        <Box
          component="span"
          sx={{
            display: "inline-flex",
            ml: 0.2,
            "& span": { animation: "blink 1.4s infinite both" },
            "& span:nth-of-type(2)": { animationDelay: "0.2s" },
            "& span:nth-of-type(3)": { animationDelay: "0.4s" },
            "@keyframes blink": {
              "0%": { opacity: 0.2 },
              "20%": { opacity: 1 },
              "100%": { opacity: 0.2 },
            },
          }}
        >
          <span>.</span>
          <span>.</span>
          <span>.</span>
        </Box>
      </Box>
    </Box>
  );

  const showWelcome =
    !loading &&
    !liveMessage.active &&
    !showInitialThinking &&
    (messages?.length === 0 || !messages) &&
    activeIndex === null &&
    !currentSessionId;

  // ── Render ──
  return (
    <Box
      sx={{
        width: { xs: "100vw", md: getContentWidth(fontLevel) },
        backgroundColor: "background.light1",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          px: { xs: 1.5, sm: 4, md: 7 },
          py: { xs: 1, md: 2 },
        }}
      >
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
            width: { xs: "50%", md: "80%" },
          }}
        >
          <Message size={22} color={mode === "dark" ? "#1cb0f6" : "#106BA3"} />
          <Typography
            variant="h4"
            sx={{
              color: "text.primary",
              width: "80%",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              fontWeight: 700,
            }}
          >
            {currentSessionData
              ? currentSessionData?.title?.charAt(0)?.toUpperCase() +
              currentSessionData?.title?.slice(1)
              : "New Chat"}
          </Typography>
        </Box>

        <Box
          onClick={handleSaveChat}
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
            cursor: "pointer",
            transition: "opacity 0.2s ease",
            "&:hover": { opacity: 0.8 },
          }}
        >
          {isCurrentSaved ? (
            <SaveIcon
              size={22}
              color={mode === "dark" ? "#1cb0f6" : "#106BA3"}
            />
          ) : (
            <Saveoutlined
              size={22}
              color={mode === "dark" ? "#1cb0f6" : "#106BA3"}
            />
          )}
          <Typography
            variant="body1"
            sx={{
              color: isCurrentSaved ? (mode === "dark" ? "#1cb0f6" : "#106BA3") : "text.primary",
              fontWeight: isCurrentSaved ? 600 : 500,
            }}
          >
            {isCurrentSaved ? "Saved Chat" : "Save Chat"}
          </Typography>
        </Box>
      </Box>

      {/* Message list */}
      {showWelcome ? (
        <WelcomeChatScreen
          handleSend={handleSend}
          setSearchQuery={setSearchQuery}
        />
      ) : loading ? (
        <Box sx={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", gap: 2 }}>
          <Box
            component="img"
            src={mode === "dark" ? DolphinIconW : DolphinIconB}
            alt="Loading..."
            sx={{
              width: 80,
              height: 80,
              animation: "swimCenter 2s ease-in-out infinite",
              "@keyframes swimCenter": {
                "0%": { transform: "translateY(0px) rotate(0deg)" },
                "25%": { transform: "translateY(-15px) rotate(-10deg)" },
                "50%": { transform: "translateY(0px) rotate(0deg)" },
                "75%": { transform: "translateY(15px) rotate(10deg)" },
                "100%": { transform: "translateY(0px) rotate(0deg)" },
              }
            }}
          />
          <Typography
            variant="body1"
            sx={{
              color: "text.secondary",
              fontWeight: 600,
              animation: "pulseText 2s infinite ease-in-out",
              "@keyframes pulseText": {
                "0%, 100%": { opacity: 0.5 },
                "50%": { opacity: 1 }
              }
            }}
          >
            Loading your chats...
          </Typography>
        </Box>
      ) : (
        <Box sx={{ display: "flex", flex: 1, overflow: "hidden" }}>
          <Box
            ref={containerRef}
            onWheel={() => {
              userScrolledRef.current = true;
              setAutoScrollEnabled(false);
            }}
            onTouchMove={() => {
              userScrolledRef.current = true;
              setAutoScrollEnabled(false);
            }}
            sx={{
              flex: 1,
              overflowY: "auto",
              pt: 2,
              pb: 4,
              px: { xs: 1, md: 5 },
              display: "flex",
              flexDirection: "column",
              gap: 3,
            }}
          >
            {/* Committed messages */}
            {messages?.map((msg, index) => {
              let prevQuestion = msg.question || "";
              if (!prevQuestion && msg.role === "assistant" && index > 0) {
                for (let j = index - 1; j >= 0; j--) {
                  if (messages[j]?.role === "user") {
                    prevQuestion = messages[j]?.content;
                    break;
                  }
                }
              }

              return (
                <ChatMessage
                  key={index}
                  handleSend={handleSend}
                  setSearchQuery={setSearchQuery}
                  sessionId={currentSessionId}
                  msg={msg}
                  userQuestion={prevQuestion}
                  messageIndex={index}
                  videos_suggestions={msg?.videos || msg?.video_suggestions || []}
                  images_suggestions={msg?.images || msg?.metadata?.images || []}
                  pdf_suggestions={msg?.pdfs || msg?.metadata?.pdfs || []}
                  onFeedbackSubmit={handleFeedbackSubmit}
                  onTopicClick={(topicCode) =>
                    handleTopicClick(topicCode, msg.topics)
                  }
                  onOpenInspector={handleOpenInspector}
                  isStreaming={false}
                />
              );
            })}

            {/* Status bubble during thinking / fetching / generating */}
            {showInitialThinking && !liveMessage.active && (
              <ProcessStatusBubble message={statusMessage} />
            )}

            {/* Live streaming answer */}
            {liveMessage.active && (
              <ChatMessage
                key="live-answer"
                handleSend={handleSend}
                setSearchQuery={setSearchQuery}
                sessionId={currentSessionId}
                msg={{
                  role: "assistant",
                  content: liveMessage.content || "",
                  company_content: liveMessage.company_content,
                  mediaLoaded: true,
                  timestamp: new Date().toISOString(),
                  question_suggestions: liveMessage.suggestions || [],
                  topics: liveMessage.topics,
                  transcripts: liveMessage.transcripts,
                  matched_pdf_chunks: liveMessage.matched_pdf_chunks || [],
                  images: liveMessage.media?.images || [],
                  pdfs: liveMessage.media?.pdfs || [],
                  videos: liveMessage.media?.videos || [],
                }}
                videos_suggestions={liveMessage.media?.videos || []}
                images_suggestions={liveMessage.media?.images || []}
                pdf_suggestions={liveMessage.media?.pdfs || []}
                onTopicClick={(topicCode) =>
                  handleTopicClick(topicCode, liveMessage.topics)
                }
                onOpenInspector={handleOpenInspector}
                isStreaming={true}
              />
            )}


            <div ref={bottomRef} />
          </Box>

          {/* Sources side panel - Matching Screenshot Design */}
          {sourcesData.open && (
            <Box
              sx={{
                width: { xs: "100%", md: "350px" },
                borderLeft: "1px solid",
                borderColor: "divider",
                backgroundColor: mode === "dark" ? "background.paper" : "#f5faff", // Light blue/gray background from screenshot
                display: "flex",
                flexDirection: "column",
                position: { xs: "fixed", md: "relative" },
                top: 0,
                right: 0,
                bottom: 0,
                zIndex: 1000,
                height: "100%",
                animation: "slideIn 0.3s ease-out",
                "@keyframes slideIn": {
                  from: { transform: "translateX(100%)" },
                  to: { transform: "translateX(0)" },
                },
              }}
            >
              {/* Header */}
              <Box
                sx={{
                  p: 2,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  borderBottom: "1px solid rgba(0,0,0,0.05)",
                }}
              >
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 800,
                    color: "primary.main",
                    fontSize: "1.1rem",
                  }}
                >
                  {sourcesData.totalSources || sourcesData.topics.length} Sources
                </Typography>
                <IconButton
                  onClick={() => setSourcesData((p) => ({ ...p, open: false }))}
                  sx={{ color: "text.secondary" }}
                >
                  <CloseIcon />
                </IconButton>
              </Box>

              <Box
                sx={{
                  p: 2,
                  flex: 1,
                  overflowY: "auto",
                  display: "flex",
                  flexDirection: "column",
                  gap: 2,
                  "&::-webkit-scrollbar": { width: "6px" },
                  "&::-webkit-scrollbar-track": { background: "transparent" },
                  "&::-webkit-scrollbar-thumb": {
                    background: "rgba(0,0,0,0.1)",
                    borderRadius: "10px",
                  },
                }}
              >
                {sourcesData.loading ? (
                  <Box sx={{ py: 4, textAlign: "center" }}>
                    <CircularProgress size={24} />
                  </Box>
                ) : sourcesData.detailTopic ? (
                  // Detail View
                  <Box
                    sx={{ display: "flex", flexDirection: "column", gap: 2 }}
                  >
                    <Button
                      startIcon={
                        <KeyboardArrowUpIcon
                          style={{ transform: "rotate(-90deg)" }}
                        />
                      }
                      onClick={() =>
                        setSourcesData((p) => ({ ...p, detailTopic: null }))
                      }
                      sx={{
                        alignSelf: "flex-start",
                        textTransform: "none",
                        color: "primary.main",
                        fontWeight: 600,
                      }}
                    >
                      Back to Sources
                    </Button>

                    <Box
                      sx={{
                        backgroundColor: mode === "dark" ? "background.default" : "#fff",
                        borderRadius: "12px",
                        overflow: "hidden",
                        boxShadow: "0 2px 12px rgba(0,0,0,0.04)",
                        border: "1px solid",
                        borderColor: mode === "dark" ? "divider" : "rgba(0,0,0,0.05)",
                        display: "flex",
                        flexDirection: "column",
                      }}
                    >
                      <Box sx={{ p: 2 }}>
                        <Box sx={{ display: "flex", gap: 1.5, mb: 2 }}>
                          <Box
                            sx={{
                              width: 28,
                              height: 28,
                              borderRadius: "50%",
                              backgroundColor: "primary.main",
                              color: "#fff",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: "0.85rem",
                              fontWeight: 700,
                            }}
                          >
                            {sourcesData.detailTopic.index}
                          </Box>
                          <Typography
                            variant="h6"
                            sx={{
                              fontWeight: 800,
                              color: "text.primary",
                              lineHeight: 1.2,
                            }}
                          >
                            {sourcesData.detailTopic.topicName}
                          </Typography>
                        </Box>

                        <Box
                          className="chat-markdown"
                          sx={{
                            ...markdownContainerSx,
                            fontSize: "0.85rem",
                            lineHeight: 1.6,
                            color: "text.primary",
                          }}
                          dangerouslySetInnerHTML={{
                            __html: sanitizeMarkdown(
                              sourcesData.detailTopic.content,
                            ),
                          }}
                        />
                      </Box>

                      {sourcesData.detailTopic.courseName && (
                        <Box
                          sx={{
                            py: 1.5,
                            px: 2,
                            backgroundColor: mode === "dark" ? "rgba(255, 255, 255, 0.05)" : "#eef6ff",
                            borderTop: "1px solid",
                            borderColor: mode === "dark" ? "divider" : "rgba(0,0,0,0.03)",
                          }}
                        >
                          <Typography
                            variant="caption"
                            sx={{
                              color: "primary.main",
                              fontWeight: 700,
                              fontSize: "0.75rem",
                            }}
                          >
                            Course: {sourcesData.detailTopic.courseName}
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  </Box>
                ) : (
                  // List View
                  sourcesData.topics.map((topic, i) => (
                    <Box
                      key={topic.code}
                      sx={{
                        backgroundColor: mode === "dark" ? "background.default" : "#fff",
                        borderRadius: "12px",
                        boxShadow: "0 2px 12px rgba(0,0,0,0.04)",
                        border: sourcesData.selectedTopicCode === topic.code ? "2px solid" : "1px solid",
                        borderColor: sourcesData.selectedTopicCode === topic.code
                          ? "primary.main"
                          : mode === "dark"
                            ? "divider"
                            : "rgba(0,0,0,0.07)",
                        display: "flex",
                        flexDirection: "column",
                        transition: "all 0.2s ease",
                      }}
                    >
                      {/* Title row */}
                      <Box
                        sx={{
                          px: 2,
                          pt: 2,
                          pb: 0.5,
                          display: "flex",
                          gap: 1.5,
                          alignItems: "flex-start",
                        }}
                      >
                        <Box
                          sx={{
                            width: 24,
                            height: 24,
                            minWidth: 24,
                            borderRadius: "50%",
                            backgroundColor: "primary.main",
                            color: "#fff",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "0.75rem",
                            fontWeight: 700,
                            mt: "2px",
                          }}
                        >
                          {topic.index}
                        </Box>
                        <Typography
                          variant="subtitle1"
                          sx={{
                            fontWeight: 800,
                            color: "text.primary",
                            lineHeight: 1.25,
                            fontSize: "0.95rem",
                          }}
                        >
                          {topic.topicName}
                        </Typography>
                      </Box>

                      {/* Preview text — clamped */}
                      <Box sx={{ px: 2, pt: 0.5 }}>
                        <Typography
                          variant="body2"
                          sx={{
                            color: "text.secondary",
                            fontSize: "0.85rem",
                            lineHeight: 1.5,
                            display: "-webkit-box",
                            WebkitLineClamp: 3,
                            WebkitBoxOrient: "vertical",
                            overflow: "hidden",
                          }}
                        >
                          {topic.content.replace(/[#*`]/g, "")}
                        </Typography>
                      </Box>

                      {/* Read More — always fully visible */}
                      <Box sx={{ px: 2, pt: 0.5, pb: 1.5 }}>
                        <Typography
                          component="span"
                          variant="body2"
                          sx={{
                            color: "primary.main",
                            fontWeight: 700,
                            fontSize: "0.8rem",
                            cursor: "pointer",
                            "&:hover": { textDecoration: "underline" },
                          }}
                          onClick={() =>
                            setSourcesData((p) => ({
                              ...p,
                              detailTopic: topic,
                            }))
                          }
                        >
                          Read More...
                        </Typography>
                      </Box>

                      {/* Course footer */}
                      {topic.courseName && (
                        <Box
                          sx={{
                            py: 1,
                            px: 2,
                            backgroundColor: mode === "dark" ? "rgba(255, 255, 255, 0.05)" : "#eef6ff",
                            borderTop: "1px solid",
                            borderColor: mode === "dark" ? "divider" : "rgba(0,0,0,0.06)",
                            borderRadius: "0 0 12px 12px",
                          }}
                        >
                          <Typography
                            variant="caption"
                            sx={{
                              color: "primary.main",
                              fontWeight: 600,
                              fontSize: "0.7rem",
                              display: "block",
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                            }}
                          >
                            Course: {topic.courseName}
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  ))
                )}
              </Box>
            </Box>
          )}
        </Box>
      )}

      {/* Input bar */}
      <Box
        sx={{
          px: { xs: 1, sm: 4, md: 7 },
          py: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-end",
        }}
      >
        <Box
          sx={{
            position: "relative",
            width: "100%",
            display: "flex",
            alignItems: "center",
            "& textarea": {
              width: "100%",
              resize: "none",
              borderRadius: 2,
              padding: "20px 56px 20px 50px",
              fontSize: 14,
              fontFamily: "inherit",
              maxHeight: 120,
              overflowY: "auto",
              boxSizing: "border-box",
              backgroundColor: "background.paper",
              color: "text.primary",
              border: "1px solid",
              borderColor: "divider",
              outline: "none",
              scrollbarWidth: "thin",
              scrollbarColor: "primary.main transparent",
              "&::placeholder": { color: "text.placeholder1", opacity: 1 },
              "&::-webkit-scrollbar": { width: 6 },
              "&::-webkit-scrollbar-thumb": {
                backgroundColor: "primary.main",
                borderRadius: 2,
              },
              "&::-webkit-scrollbar-button": { display: "none" },
            },
          }}
        >
          <TextareaAutosize
            minRows={1}
            maxRows={6}
            placeholder="Message Dolphin AI"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (isStreaming) return; // prevent sending while streaming
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />

          <Box
            sx={{
              position: "absolute",
              left: 16,
              top: "50%",
              transform: "translateY(-50%)",
              display: "flex",
            }}
          >
            <Message
              size={22}
              color={mode === "dark" ? "#1cb0f6" : "#106BA3"}
            />
          </Box>

          {isStreaming ? (
            <IconButton
              onClick={handleStop}
              aria-label="Stop generating response"
              title="Stop generating"
              sx={{
                position: "absolute",
                right: 16,
                top: "50%",
                transform: "translateY(-50%)",
                height: 36,
                width: 36,
                borderRadius: "50%",
                backgroundColor:
                  mode === "dark"
                    ? "rgba(28, 176, 246, 0.18)"
                    : "rgba(28, 176, 246, 0.12)",
                border: "1.5px solid",
                borderColor: mode === "dark" ? "#1cb0f6" : "#1989D0",
                color: mode === "dark" ? "#1cb0f6" : "#106BA3",
                transition: "all 0.2s ease-in-out",
                "&:hover": {
                  backgroundColor:
                    mode === "dark" ? "#1cb0f6" : "#106BA3",
                  borderColor: mode === "dark" ? "#1cb0f6" : "#106BA3",
                  color: "#ffffff",
                  transform: "translateY(-50%) scale(1.08)",
                },
              }}
            >
              <StopRoundedIcon sx={{ fontSize: 20 }} />
            </IconButton>
          ) : (
            <IconButton
              onClick={() => handleSend()}
              disabled={!searchQuery.trim()}
              aria-label="Send message"
              title="Send"
              sx={{
                position: "absolute",
                right: 16,
                top: "50%",
                transform: "translateY(-50%)",
                height: 36,
                width: 36,
                borderRadius: 2,
                opacity: searchQuery.trim() ? 1 : 0.4,
                transition: "all 0.2s ease-in-out",
                "&:hover": {
                  transform: searchQuery.trim()
                    ? "translateY(-50%) scale(1.05)"
                    : "translateY(-50%)",
                },
              }}
            >
              <SendIcon
                size={20}
                color={mode === "dark" ? "#1989D0" : "#106BA3"}
              />
            </IconButton>
          )}
        </Box>

        <Typography
          variant="caption"
          sx={{
            fontWeight: 500,
            textAlign: "center",
            p: 1,
            color: "text.caption",
          }}
        >
          This AI-generated content is for educational purposes only and may not
          reflect the most current regulations or company policies. Always
          verify with official sources and your organization's safety management
          system (SMS) before applying in practice.
        </Typography>
      </Box>

      {/* Save dialog */}
      <Dialog
        open={saveDialog.open}
        onClose={() => setSaveDialog({ ...saveDialog, open: false })}
        maxWidth="xs"
        fullWidth
        BackdropProps={{
          sx: {
            backdropFilter: "blur(6px)",
            backgroundColor: "rgba(0,0,0,0.2)",
          },
        }}
        PaperProps={{
          sx: {
            borderRadius: 3,
            backdropFilter: "blur(10px)",
            background: "rgba(255,255,255,0.8)",
          },
        }}
      >
        <DialogContent
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            py: 4,
            px: 3,
            textAlign: "center",
          }}
        >
          {saveDialog.isError ? (
            <ErrorIcon sx={{ fontSize: 50, color: "error.main", mb: 1 }} />
          ) : (
            <CheckCircleIcon sx={{ fontSize: 50, color: "#1cb0f6", mb: 1 }} />
          )}
          <Typography
            variant="body1"
            sx={{ mt: 1, fontWeight: 500, color: "text.primary" }}
          >
            {saveDialog.message}
          </Typography>
        </DialogContent>
        <DialogActions sx={{ justifyContent: "center", pb: 3 }}>
          <Button
            onClick={() => setSaveDialog({ ...saveDialog, open: false })}
            variant="contained"
            sx={{
              width: 100,
              height: 40,
              borderRadius: 1,
              textTransform: "none",
              fontWeight: 600,
            }}
          >
            OK
          </Button>
        </DialogActions>
      </Dialog>

      {/* Testing: Media & Source Inspector Drawer */}
      <MediaInspectorDrawer
        open={inspectorOpen}
        onClose={handleCloseInspector}
        data={inspectorData}
      />
    </Box>
  );
};

export default ChatWindow;
