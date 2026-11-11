import React, { useState, useMemo } from "react";
import {
  Box,
  Typography,
  Avatar,

} from "@mui/material";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";
import QuizDisplay from "./QuizDisplay";
import { sanitizeMarkdown } from "./ChatWindow";
import DolphinIconW from "../../assets/images/dolphin_w.png";
import { useThemeMode } from "../../context/ThemeModeContext";
import { VideoIcon } from "../../assets/svgIcons/VideoIcon";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import { ImageIcon } from "../../assets/svgIcons/ImageIcon";
import { DocumentIcon } from "../../assets/svgIcons/DocumentIcon";
import MediaPreviewModal from "./MediaPreviewModal";
import FeedbackRatingButtons from "./FeedbackRatingButtons";

import { resolveImageUrl } from "../../api/config";
import PdfThumbnail from "./PdfThumbnail";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";

// ─── Testing Feature Flag ───
// Set to false to revert UI 100% to original layout with zero inspector/citation elements.
export const ENABLE_MEDIA_INSPECTOR = true;

// ─── Normalisers ───
const normalizeVideo = (v) => {
  const url = v.url || v.Url || v.videourl || "";
  const rawId = v.video_id || v.Id || v.id || "";
  const fallbackId = (!rawId && url) ? url.split("/").pop().split("?")[0].replace(/\.mp4$/i, "") : "";
  return {
    title: v.title || v.Title || "",
    url: url,
    thumbnail: v.thumbnail || v.Thumbnail || "",
    video_id: String(rawId || fallbackId || ""),
    topic_code: String(v.topic_code || ""),
    topic_name: String(v.topic_name || ""),
    course_code: String(v.course_code || v.CourseCode || v.courseCode || ""),
    course_name: String(v.course_name || v.CourseName || v.courseName || ""),
    source_type: String(v.source_type || "curriculum"),
    content: String(v.content || ""),
  };
};

const normalizeImage = (img) => {
  if (!img) return { title: "", url: "", thumbnail: "" };
  if (typeof img === "string") {
    const src = resolveImageUrl(img);
    return { title: "Topic image", url: src, thumbnail: src };
  }

  const rawBase64 = img.base64 || img.Base64;
  const hasValidBase64 =
    rawBase64 &&
    typeof rawBase64 === "string" &&
    rawBase64.trim() !== "" &&
    rawBase64.trim().toLowerCase() !== "none" &&
    rawBase64.trim().toLowerCase() !== "null" &&
    rawBase64.trim().length > 50;

  const imageSrc = hasValidBase64
    ? (rawBase64.startsWith("data:")
      ? rawBase64
      : `data:image/${img.format || "jpeg"};base64,${rawBase64}`)
    : resolveImageUrl(
      img.url ||
      img.Url ||
      img.image_url ||
      img.imageUrl ||
      img.image ||
      img.src ||
      img.path ||
      img.id ||
      img.Id ||
      ""
    );

  const thumbSrc = img.thumbnail || img.Thumbnail
    ? resolveImageUrl(img.thumbnail || img.Thumbnail)
    : (img.Url || img.url ? resolveImageUrl(img.Url || img.url) : imageSrc);

  const displayTitle =
    img.title ||
    img.Title ||
    img.name ||
    (img.About && typeof img.About === "string" && img.About.trim().length > 0 && img.About.length < 60
      ? img.About.trim()
      : (img.about && typeof img.about === "string" && img.about.trim().length > 0 && img.about.length < 60
        ? img.about.trim()
        : "Topic image"));

  return {
    title: displayTitle,
    url: imageSrc,
    thumbnail: thumbSrc,
  };
};

const normalizePdf = (pdf) => {
  if (!pdf) return { title: "", link: "", thumbnail: "" };
  if (typeof pdf === "string") {
    return {
      title: "",
      link: pdf,
      thumbnail: `/api/pdf_thumbnail?url=${encodeURIComponent(pdf)}`,
    };
  }
  const link = pdf.link || pdf.Link || pdf.url || pdf.Url || "";

  let title = (pdf.title || pdf.Title || pdf.name || pdf.Name || "").trim();
  if (title.toLowerCase() === "reference document" || title.toLowerCase() === "document") {
    title = "";
  }

  if (!title && link) {
    try {
      const pathname = new URL(link, window.location.origin).pathname;
      const filename = pathname.split("/").pop().replace(/\.pdf$/i, "");
      if (filename && !/^[0-9a-f]{8}-[0-9a-f]{4}/i.test(filename) && !/^[0-9a-f]{20,}/i.test(filename)) {
        title = decodeURIComponent(filename).replace(/[-_]+/g, " ").trim();
      }
    } catch (_) { }
  }

  return {
    title: title,
    link: link,
    thumbnail:
      pdf.thumbnail ||
      pdf.Thumbnail ||
      (link ? `/api/pdf_thumbnail?url=${encodeURIComponent(link)}` : ""),
  };
};

const extractShortTopicLabel = (questionText) => {
  if (!questionText || typeof questionText !== "string") return "Maritime Topic";
  let clean = questionText.replace(/^(\d+[.)]|[-*•])\s*/, "").replace(/[?.,!]+$/, "").trim();

  // If it's already a title or permit name (not a conversational question starting with question words or ending with ?),
  // keep the ENTIRE title dynamically without truncating words!
  const isQuestion =
    /^(what|how|why|can you|explain|describe|tell me|where|when|is|are|do|does)\b/i.test(clean) ||
    questionText.trim().endsWith("?");

  if (!isQuestion) {
    return clean;
  }

  // If it's a conversational question sentence, strip conversational fluff
  clean = clean.replace(
    /^(what are the\s*(key|main|standard|vital|critical|emergency)?\s*(actions (for|during)\s*)?|procedure (for|of)\s*|how (do you|does|is|to|are)\s*|why is\s*|can you (explain|describe|tell me about)\s*|explain (the\s*)?|describe (the\s*)?|tell me about\s*|what is (the\s*)?|what keeps\s*|learn about\s*|explore\s*|review\s*|practice\s*|study\s*)/i,
    ""
  ).trim();
  clean = clean.replace(
    /\s+(aid navigation|safe at sea|vital onboard|used afloat|underway|rules|tips|steps|basics)\??$/i,
    ""
  ).trim();

  if (!clean) return "Maritime Topic";

  return clean
    .split(/\s+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
};

const normalizeSuggestionItem = (item) => {
  if (!item) return { label: "", query: "" };
  if (typeof item === "object") {
    const rawQuery = String(item.query || item.question || item.label || "").trim();
    let rawLabel = String(item.label || item.topic || "").trim();
    if (!rawLabel && rawQuery) {
      rawLabel = extractShortTopicLabel(rawQuery);
    }
    return {
      label: rawLabel || rawQuery,
      query: rawQuery || rawLabel,
    };
  }

  const queryStr = String(item).trim();
  return {
    label: extractShortTopicLabel(queryStr),
    query: queryStr,
  };
};

const escapeRegex = (str) => str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export const prepareClickableSubtopics = (rawContent, candidates) => {
  if (!rawContent) return "";
  let processed = rawContent;

  // 1. Match against known candidates (from suggestions / clarification options)
  // Strictly match ONLY bulleted or numbered list items.
  // Never turn bold words in opening paragraphs, sentences, or prose into links.
  if (candidates && candidates.length) {
    for (const candidate of candidates) {
      const lbl = (candidate.label || "").trim();
      const q = candidate.query || lbl;
      if (!lbl) continue;

      const encodedTarget = `#ask:${encodeURIComponent(q)}`;
      const escapedLbl = escapeRegex(lbl);

      // Match list item formats:
      // a) "- **Title**", "* **Title**", "• **Title**", "1. **Title**", "1) **Title**"
      const listBoldRegex = new RegExp(
        `(^|\\n)([ \\t]*(?:[-*•]|\\d+[.)])[ \\t]+)\\*\\*(${escapedLbl})(:?)\\*\\*(?![\\(\\]])`,
        "gi"
      );
      processed = processed.replace(listBoldRegex, `$1$2**[$3](${encodedTarget})**$4`);

      // b) "**1. Title**" or "**1) Title**"
      const numInsideBoldRegex = new RegExp(
        `(^|\\n)([ \\t]*)\\*\\*(\\d+[.)][ \\t]+)(${escapedLbl})(:?)\\*\\*(?![\\(\\]])`,
        "gi"
      );
      processed = processed.replace(numInsideBoldRegex, `$1$2**$3[$4](${encodedTarget})**$5`);
    }
  }

  // 2. Auto-link intentional catalog / choices lists (like SMS permits, checklists, and option lists)
  // Only link if the content explicitly indicates an option/catalog context
  const isCatalogContext =
    /(?:available permits|sms template|checklist|checklist items|permits to work|did you mean|which of these|choose (?:one|an option|any)|tap any|select (?:one|any)|following options)/i.test(processed);

  if (isCatalogContext) {
    processed = processed.replace(
      /(^|\n)(\s*\d+[.)]\s+)\*\*([^\n*\[\]]+?)\*\*(?![\(\]])/g,
      (match, prefix, numPrefix, title) => {
        if (title.includes("[") || title.includes("]")) return match;
        const cleanTitle = title.trim();
        const encodedTarget = `#ask:${encodeURIComponent(cleanTitle)}`;
        return `${prefix}${numPrefix}**[${cleanTitle}](${encodedTarget})**`;
      }
    );
  }

  return processed;
};

// ── Markdown prose styles ───
export const markdownContainerSx = {
  lineHeight: 1.7,
  wordBreak: "break-word",
  overflowWrap: "break-word",

  // Paragraphs
  "& p": {
    mt: 0,
    mb: "0.65em",
    "&:last-child": { mb: 0 },
  },

  // Headings
  "& h1, & h2, & h3, & h4, & h5, & h6": {
    mt: "1.25em",
    mb: "0.4em",
    fontWeight: 600,
    lineHeight: 1.3,
    "&:first-of-type": { mt: 0 },
  },
  "& h1": { fontSize: "1.35em" },
  "& h2": { fontSize: "1.2em" },
  "& h3": { fontSize: "1.05em" },

  // Lists — clean, aligned spacing
  "& ol": {
    mt: "0.35em",
    mb: "0.6em",
    pl: "1.4em",
    listStyleType: "decimal",
    "&:last-child": { mb: 0 },
  },
  "& ul": {
    mt: "0.35em",
    mb: "0.6em",
    pl: "1.4em",
    listStyleType: "disc",
    "&:last-child": { mb: 0 },
  },
  "& li": {
    display: "list-item",
    mb: "0.35em",
    lineHeight: 1.65,
    "&:last-child": { mb: 0 },
  },
  "& li > ul": {
    mt: "0.25em",
    mb: "0.35em",
    pl: "1.3em",
    listStyleType: "circle",
  },
  "& li > ol": {
    mt: "0.25em",
    mb: "0.35em",
    pl: "1.3em",
    listStyleType: "lower-alpha",
  },
  "& li > ul > li > ul": {
    listStyleType: "square",
  },
  "& li > p": {
    mt: 0,
    mb: "0.25em",
  },

  // Inline code
  "& code": {
    fontFamily: "monospace",
    fontSize: "0.875em",
    px: "0.35em",
    py: "0.1em",
    borderRadius: "4px",
    backgroundColor: "rgba(0,0,0,0.08)",
  },

  // Code blocks
  "& pre": {
    mt: "0.5em",
    mb: "0.75em",
    p: "0.75em 1em",
    borderRadius: "6px",
    overflowX: "auto",
    backgroundColor: "rgba(0,0,0,0.06)",
    "& code": {
      backgroundColor: "transparent",
      px: 0,
      py: 0,
      fontSize: "0.85em",
    },
  },

  // Blockquotes
  "& blockquote": {
    mt: "0.5em",
    mb: "0.75em",
    pl: "1em",
    borderLeft: "3px solid",
    borderColor: "divider",
    opacity: 0.85,
    "& p": { mb: 0 },
  },

  // HR
  "& hr": {
    my: "1em",
    border: "none",
    borderTop: "1px solid",
    borderColor: "divider",
  },

  "& strong": { fontWeight: 600 },
  "& em": { fontStyle: "italic" },

  // Links (e.g. clickable subtopics inside message text)
  "& a": {
    color: "primary.main",
    textDecoration: "underline",
    textUnderlineOffset: "3px",
    fontWeight: 600,
    cursor: "pointer",
    transition: "all 0.15s ease",
    "&:hover": {
      color: "primary.main",
      opacity: 0.8,
      textDecoration: "underline",
    },
  },

  // Tables
  "& table": {
    width: "100%",
    borderCollapse: "collapse",
    my: "1em",
    fontSize: "0.9em",
    overflowX: "auto",
    display: "table",
  },
  "& th, & td": {
    border: "1px solid",
    borderColor: "divider",
    p: "8px 12px",
    textAlign: "left",
    verticalAlign: "middle",
  },
  "& th": {
    backgroundColor: "action.hover",
    fontWeight: 600,
  },
  "& tr:nth-of-type(even)": {
    backgroundColor: "action.selected",
  },

  // Task list checkboxes
  "& input[type='checkbox']": {
    mr: "8px",
    verticalAlign: "middle",
    accentColor: "primary.main",
    width: "16px",
    height: "16px",
    cursor: "default",
  },

  // Inline images and diagrams
  "& img": {
    maxWidth: "100%",
    height: "auto",
    borderRadius: "10px",
    my: "1.25em",
    display: "block",
    boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
    border: "1px solid",
    borderColor: "divider",
  },
};

// ─── ChatMessage ──
const ChatMessage = ({
  msg,
  userQuestion = "",
  videos_suggestions,
  images_suggestions,
  pdf_suggestions,
  sessionId,
  setSearchQuery,
  handleSend,
  messageIndex,
  onFeedbackSubmit,
  onTopicClick,
  onOpenInspector,
  isStreaming,
  skipMarkdownFormatting = false,
  plainText = false,
}) => {
  const isUser = msg.role === "user";

  const cleanPlainText = (text) => {
    if (!text) return "";
    return text
      // Remove markdown bullet points
      .replace(/(^|\n)\s*[-*•]\s+/g, "$1")
      // Remove numbered list markers
      .replace(/(^|\n)\s*\d+[.)]\s+/g, "$1")
      // Remove excessive line breaks
      .replace(/\n{2,}/g, "\n")
      .trim();
  };

  const { mode } = useThemeMode();
  const [feedback, setFeedback] = useState(null);
  const [commentDialogOpen, setCommentDialogOpen] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [isSubmittingComment, setIsSubmittingComment] = useState(false);
  const [commentPopup, setCommentPopup] = useState({
    open: false,
    message: "",
    severity: "success",
  });

  const [previewMedia, setPreviewMedia] = useState({
    open: false,
    type: null,
    src: null,
    title: "",
  });
  const openPreview = (type, src, title = "", page = null) => {
    let finalSrc = src;
    if (type === "pdf" && finalSrc && page && !String(finalSrc).includes("#page=")) {
      finalSrc = `${finalSrc}#page=${page}`;
    }
    setPreviewMedia({ open: true, type, src: finalSrc, title });
  };
  const closePreview = () =>
    setPreviewMedia({ open: false, type: null, src: null, title: "" });

  const handleFollowUpQuestion = async (query) => {
    setSearchQuery(query);
    await handleSend(query);
  };

  const handleLikeDislike = async (type) => {
    if (type === "dislike") {
      // For dislike: open comment dialog to collect reason, API called on submit
      setFeedback("dislike");
      setCommentText("");
      setCommentDialogOpen(true);
      return;
    }

    // For like: toggle and call API immediately
    const newFeedback = feedback === type ? null : type;
    setFeedback(newFeedback);

    const messageId = messageIndex + 1;
    const userId = localStorage.getItem("user_id");

    if (onFeedbackSubmit && newFeedback) {
      try {
        await onFeedbackSubmit({
          session_id: sessionId,
          message_id: messageId,
          like: 1,
          user_id: userId,
        });
      } catch (error) {
        console.error("Failed to submit feedback:", error);
      }
    }
  };

  const handleCloseCommentDialog = () => {
    setCommentDialogOpen(false);
    setCommentText("");
  };

  const handleSubmitComment = async () => {
    if (!commentText.trim()) return;

    setIsSubmittingComment(true);
    const messageId = messageIndex + 1;
    const userId = localStorage.getItem("user_id");

    try {
      if (onFeedbackSubmit) {
        await onFeedbackSubmit({
          session_id: sessionId,
          message_id: messageId,
          like: 0,
          user_id: userId,
          commond: commentText.trim(),
        });
      }

      handleCloseCommentDialog();
      setCommentPopup({
        open: true,
        message: "Feedback submitted successfully!",
        severity: "success",
      });
    } catch (error) {
      console.error("Failed to submit comment:", error);
      setCommentPopup({
        open: true,
        message: "Failed to submit feedback. Please try again.",
        severity: "error",
      });
    } finally {
      setIsSubmittingComment(false);
    }
  };

  const isOutOfScope =
    msg.metadata?.out_of_scope === true ||
    msg.category === "FALLBACK" ||
    msg.category === "OFF_TOPIC" ||
    (typeof msg.content === "string" && (
      msg.content.toLowerCase().includes("outside the marine training curriculum") ||
      msg.content.toLowerCase().includes("outside the maritime curriculum") ||
      msg.content.toLowerCase().includes("specialized exclusively in maritime")
    ));

  const isGreeting =
    msg.category === "GREETING" ||
    msg.type === "greeting" ||
    (typeof msg.content === "string" && (
      (/^(\s*hello|\s*hi\b|\s*hey\b|\s*good\s+morning|\s*good\s+evening|\s*good\s+day)/i.test(msg.content) ||
        msg.content.includes("Welcome to Dolphin AI") ||
        msg.content.includes("maritime AI assistant")) &&
      !/(video|videos|watch|clip)/i.test(msg.content)
    ));

  // 1. Unified, deduplicated videos list (capped to strictly maximum 5; greetings return none)
  const unifiedVideos = React.useMemo(() => {
    if (isGreeting || isOutOfScope || isUser) return [];

    const rawList = [
      ...(msg.transcripts || []).map((t) => ({
        title: t.video_title || t.Title || t.title || (t.content ? `${t.content.substring(0, 45)}...` : "Course Video"),
        url: t.video_link || t.Url || t.url || t.videourl || "",
        thumbnail: t.video_thumbnail || t.thumbnail || t.Thumbnail || t.image || t.image_url || t.imageUrl || ((t.video_link || t.Url || t.url) ? (t.video_link || t.Url || t.url).replace(/\.mp4$/i, ".png") : ""),
      })),
      ...(videos_suggestions || []).map(normalizeVideo),
      ...(msg.videos || []).map(normalizeVideo),
    ];

    const seen = new Set();
    const result = [];

    for (const v of rawList) {
      if (!v || !v.url) continue;
      const cleanUrl = v.url.trim().toLowerCase().replace(/\/+$/, "");
      const cleanTitle = (v.title || "").trim().toLowerCase();
      const key = cleanUrl || cleanTitle;
      if (!key || seen.has(key) || (cleanTitle && seen.has(cleanTitle))) continue;
      seen.add(key);
      if (cleanTitle) seen.add(cleanTitle);

      result.push({
        title: v.title || "Course video",
        url: v.url,
        thumbnail: v.thumbnail || (v.url.endsWith(".mp4") ? v.url.replace(/\.mp4$/i, ".png") : ""),
      });

      if (result.length >= 5) break;
    }

    return result;
  }, [msg.transcripts, msg.videos, videos_suggestions, isGreeting, isOutOfScope, isUser]);

  // Topic metadata extraction
  const primaryTopic = React.useMemo(() => {
    if (!msg.topics || msg.topics.length === 0) return null;
    const first = msg.topics[0];
    if (typeof first === "object" && first !== null) {
      return { code: String(first.code || first.topic_code || ""), name: String(first.name || first.topic_name || "") };
    }
    return { code: String(first), name: String(first) };
  }, [msg.topics]);

  // Course metadata extraction
  const primaryCourse = React.useMemo(() => {
    // 1. From related courses list
    const licData = msg.checkLicCoursesData || msg.courses || [];
    if (Array.isArray(licData) && licData.length > 0) {
      for (const item of licData) {
        const c = item.data?.course || item.course || item;
        const code = c.CourseCode || c.courseCode || c.course_code;
        const name = c.CourseName || c.courseName || c.course_name;
        if (code || name) {
          return { code: String(code || ""), name: String(name || "") };
        }
      }
    }
    // 2. From topic objects if embedded
    if (msg.topics && msg.topics.length > 0) {
      for (const t of msg.topics) {
        if (typeof t === "object" && t !== null && (t.course_code || t.courseCode)) {
          return { code: String(t.course_code || t.courseCode || ""), name: String(t.course_name || t.courseName || "") };
        }
      }
    }
    return null;
  }, [msg.checkLicCoursesData, msg.courses, msg.topics]);

  // 1a. Dedicated Topic / Curriculum Videos (for testing inspector)
  const topicVideos = React.useMemo(() => {
    if (isGreeting || isOutOfScope || isUser) return [];
    const firstTopicCode = primaryTopic?.code || "";
    const firstTopicName = primaryTopic?.name || "";
    const rawList = [
      ...(videos_suggestions || []).map(normalizeVideo),
      ...(msg.videos || []).map(normalizeVideo),
    ];
    const seen = new Set();
    const result = [];
    for (const v of rawList) {
      if (!v || !v.url) continue;
      const cleanUrl = v.url.trim().toLowerCase().replace(/\/+$/, "");
      const cleanTitle = (v.title || "").trim().toLowerCase();
      const key = cleanUrl || cleanTitle;
      if (!key || seen.has(key) || (cleanTitle && seen.has(cleanTitle))) continue;
      seen.add(key);
      if (cleanTitle) seen.add(cleanTitle);

      const resolvedTopicCode = v.topic_code || firstTopicCode || "";
      const resolvedTopicName = v.topic_name || firstTopicName || "";
      result.push({
        ...v,
        title: v.title || "Course video",
        url: v.url,
        thumbnail: v.thumbnail || (v.url.endsWith(".mp4") ? v.url.replace(/\.mp4$/i, ".png") : ""),
        video_id: v.video_id || (v.url ? v.url.split("/").pop().split("?")[0].replace(/\.mp4$/i, "") : ""),
        topic_code: resolvedTopicCode,
        topic_name: resolvedTopicName,
        source_type: "curriculum",
      });
      if (result.length >= 5) break;
    }
    return result;
  }, [msg.videos, videos_suggestions, primaryTopic, isGreeting, isOutOfScope, isUser]);

  // 1b. Dedicated Transcript-Matched Videos (for testing inspector)
  const transcriptVideos = React.useMemo(() => {
    if (isGreeting || isOutOfScope || isUser) return [];
    const rawTranscripts = msg.transcripts || msg?.metadata?.transcripts || [];
    const rawList = (rawTranscripts || []).map((t) => {
      const vUrl = t.video_link || t.Url || t.url || t.videourl || "";
      const vId = String(t.video_id || t.Id || t.id || (vUrl ? vUrl.split("/").pop().split("?")[0].replace(/\.mp4$/i, "") : ""));
      return {
        title: t.video_title || t.Title || t.title || (t.content ? `${t.content.substring(0, 45)}...` : "Course Video"),
        url: vUrl,
        thumbnail: t.video_thumbnail || t.thumbnail || t.Thumbnail || (vUrl ? vUrl.replace(/\.mp4$/i, ".png") : ""),
        video_id: vId,
        topic_code: String(t.topic_code || ""),
        topic_name: String(t.topic_name || ""),
        course_code: String(t.course_code || t.CourseCode || ""),
        course_name: String(t.course_name || t.CourseName || ""),
        content: String(t.content || ""),
        source_type: "transcript_vector",
      };
    });

    const seen = new Set();
    const result = [];
    for (const v of rawList) {
      if (!v || !v.url) continue;
      const cleanUrl = v.url.trim().toLowerCase().replace(/\/+$/, "");
      const cleanTitle = (v.title || "").trim().toLowerCase();
      const key = cleanUrl || cleanTitle;
      if (!key || seen.has(key) || (cleanTitle && seen.has(cleanTitle))) continue;
      seen.add(key);
      if (cleanTitle) seen.add(cleanTitle);

      result.push(v);
      if (result.length >= 5) break;
    }
    return result;
  }, [msg.transcripts, msg?.metadata?.transcripts, isGreeting, isOutOfScope, isUser]);

  const [failedImageUrls, setFailedImageUrls] = useState(() => new Set());

  // 2. Unified, deduplicated images list (capped to strictly maximum 5; broken images and raw scanned text pages excluded)
  const normalizedImages = React.useMemo(() => {
    if (isGreeting || isOutOfScope || isUser) return [];
    const seen = new Set();
    return (images_suggestions || msg?.images || msg?.metadata?.images || [])
      .map(normalizeImage)
      .filter((img) => {
        if (!img || !img.url || typeof img.url !== "string" || img.url.trim().length === 0) return false;
        if (failedImageUrls.has(img.url)) return false;

        const normKey = img.url.toLowerCase().replace(/\/+/g, "/").replace(/\/+$/, "");
        if (!normKey || seen.has(normKey)) return false;

        const cleanTitle = (img.title || "").trim().toLowerCase();
        const normTitleKey = cleanTitle.replace(/[^a-z0-9]/g, "");
        if (normTitleKey && seen.has(normTitleKey)) return false;

        seen.add(normKey);
        if (normTitleKey) seen.add(normTitleKey);

        const lowerUrl = img.url.toLowerCase();
        if (
          (lowerUrl.includes("/storage/pdf_images/") || lowerUrl.includes("_img_")) &&
          (cleanTitle.includes("guide") ||
            cleanTitle.includes("manual") ||
            cleanTitle.includes("checklist") ||
            cleanTitle.includes("handbook") ||
            cleanTitle.includes("permit") ||
            cleanTitle.includes("form") ||
            cleanTitle.includes("procedure"))
        ) {
          return false;
        }
        return true;
      })
      .slice(0, 5);
  }, [images_suggestions, msg?.images, msg?.metadata?.images, failedImageUrls, isGreeting, isOutOfScope, isUser]);

  // 3. Unified, deduplicated PDFs list (capped to strictly maximum 5)
  const normalizedPdfs = React.useMemo(() => {
    if (isGreeting || isOutOfScope || isUser) return [];
    const seen = new Set();
    const result = [];
    const rawList = [
      ...(pdf_suggestions || []),
      ...(msg?.pdfs || []),
      ...(msg?.metadata?.pdfs || []),
    ];

    for (const rawPdf of rawList) {
      const pdf = normalizePdf(rawPdf);
      if (!pdf || !pdf.link || typeof pdf.link !== "string" || pdf.link.trim().length === 0) {
        continue;
      }

      const cleanLink = pdf.link.trim().toLowerCase().replace(/\/+$/, "");
      let cleanTitle = (pdf.title || "").trim().toLowerCase();
      cleanTitle = cleanTitle.replace(/\s*\(\d+\)$/, "").trim();
      if (cleanTitle.endsWith(" (document)")) {
        cleanTitle = cleanTitle.slice(0, -11).trim();
      }
      const normTitleKey = cleanTitle.replace(/[^a-z0-9]/g, "");

      // Deduplicate by cleanLink and normalized alphanumeric title key
      if (seen.has(cleanLink) || (normTitleKey && seen.has(normTitleKey))) {
        continue;
      }
      seen.add(cleanLink);
      if (normTitleKey) seen.add(normTitleKey);

      let displayTitle = (pdf.title || "").trim();
      displayTitle = displayTitle.replace(/\s*\(\d+\)$/, "").trim();
      if (displayTitle.endsWith(" (Document)")) {
        displayTitle = displayTitle.slice(0, -11).trim();
      }

      result.push({
        ...pdf,
        title: displayTitle || "Reference Document",
      });

      if (result.length >= 5) break;
    }

    return result;
  }, [pdf_suggestions, msg?.pdfs, msg?.metadata?.pdfs, isGreeting, isOutOfScope, isUser]);

  const matchedPdfChunks = React.useMemo(() => {
    if (isGreeting || isOutOfScope || isUser) return [];
    return msg?.matched_pdf_chunks || [];
  }, [msg?.matched_pdf_chunks, isGreeting, isOutOfScope, isUser]);

  const groupedVectorPdfs = React.useMemo(() => {
    if (isGreeting || isOutOfScope || isUser) return [];
    const rawChunks = msg?.matched_pdf_chunks || [];
    if (!rawChunks || rawChunks.length === 0) return [];

    const map = new Map();
    for (const chunk of rawChunks) {
      if (!chunk) continue;
      // Leave raw title untouched - do NOT override "Untitled Document" per instruction
      const docTitle = String(chunk.title || chunk.document || chunk.source_pdf || "Untitled Document").trim();
      const p = chunk.page;
      const parsedPage = typeof p === "number" ? p : (parseInt(p, 10) || 1);
      const score = Number(chunk.score || chunk.similarity || 0);
      const matchPct = chunk.match_pct || (score > 0 ? (score <= 1.0 ? Math.round(score * 100) : Math.round(score)) : null);
      const cleanUrl = String(chunk.link || chunk.url || chunk.pdf_url || "").trim().toLowerCase();
      const topicCode = String(chunk.topic_code || "").trim().toLowerCase();

      // Truly identify the unique document:
      // 1. By non-empty PDF URL / file path
      // 2. By non-generic named document title (when title is not "Untitled Document")
      // 3. If untitled and no URL, differentiate by topic_code + chunk/page id so different PDFs never merge together
      let docKey = "";
      if (cleanUrl) {
        docKey = cleanUrl;
      } else if (docTitle && docTitle.toLowerCase() !== "untitled document" && docTitle.toLowerCase() !== "document") {
        docKey = `${topicCode}_${docTitle}`.toLowerCase();
      } else {
        docKey = `${topicCode}_doc_${chunk.chunk_index || chunk.page || Math.random()}`;
      }

      if (!map.has(docKey)) {
        map.set(docKey, {
          ...chunk,
          title: docTitle,
          pages: [parsedPage],
          bestScore: score,
          bestMatchPct: matchPct,
          firstPage: parsedPage,
          link: chunk.link || chunk.url || chunk.pdf_url || "",
          thumbnail: chunk.thumbnail || "",
        });
      } else {
        const existing = map.get(docKey);
        if (parsedPage && !existing.pages.includes(parsedPage)) {
          existing.pages.push(parsedPage);
          existing.pages.sort((a, b) => a - b);
        }
        if (score > existing.bestScore) {
          existing.bestScore = score;
          existing.bestMatchPct = matchPct;
          if (chunk.text_preview) existing.text_preview = chunk.text_preview;
        }
        if (!existing.link && (chunk.link || chunk.url || chunk.pdf_url)) {
          existing.link = chunk.link || chunk.url || chunk.pdf_url;
        }
      }
    }
    return Array.from(map.values());
  }, [msg?.matched_pdf_chunks, isGreeting, isOutOfScope, isUser]);

  const rawSuggestions = msg.question_suggestions || [];
  const normalizedSuggestions = useMemo(() => {
    return (rawSuggestions || [])
      .map(normalizeSuggestionItem)
      .filter((s) => s.label && s.query);
  }, [rawSuggestions]);

  const subtopicCandidates = useMemo(() => {
    const map = new Map();
    // 1. From clarification payload if available
    if (msg.clarification?.options && Array.isArray(msg.clarification.options)) {
      for (const opt of msg.clarification.options) {
        const lbl = String(opt.label || "").trim();
        const q = String(opt.query || lbl).trim();
        if (lbl && opt.kind !== "other") {
          map.set(lbl.toLowerCase(), { label: lbl, query: q });
        }
      }
    }
    // 2. From normalizedSuggestions
    for (const s of normalizedSuggestions) {
      if (s.label && !map.has(s.label.toLowerCase())) {
        map.set(s.label.toLowerCase(), s);
      }
    }
    return Array.from(map.values());
  }, [msg.clarification, normalizedSuggestions]);

  const isClarification = Boolean(
    msg.clarification ||
    msg.metadata?.clarification ||
    msg.metadata?.needs_clarification === true ||
    msg.metadata?.routing_reason === "clarification" ||
    msg.metadata?.routing_reason === "cross_domain_clarification" ||
    msg.category?.toLowerCase() === "clarification" ||
    (typeof msg.content === "string" && (
      msg.content.includes("Tap one of the options") ||
      msg.content.includes("Which of these do you mean")
    ))
  );

  const shouldShowMedia =
    !isOutOfScope &&
    !isGreeting &&
    Boolean(msg.content && msg.content.length > 0);
  const shouldShowQuestions =
    !isOutOfScope && !isClarification && normalizedSuggestions.length > 0;


  const sanitizeDisplayContent = (content) => {
    if (!content || typeof content !== "string") return "";
    let clean = content.replace(/^(?:#{1,6}\s*|\*{2})?(?:Out of Scope|Off Topic)(?:\*{2})?[:\s]*\n*/i, "");
    if (!ENABLE_MEDIA_INSPECTOR) {
      clean = clean.replace(/\[\[\s*(?:PDF|VIDEO|TRANSCRIPT):[^\]]+\]\]/gi, "");
    }
    return clean;
  };

  const getFormattedTime = (timestamp) => {
    if (!timestamp) return "";
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) return "";

    const day = String(date.getDate()).padStart(2, "0");
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const year = date.getFullYear();

    const time = date.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });

    return `${day}/${month}/${year}, ${time}`;
  };

  const decorateWithCitations = (html, defaultCode = "") => {
    if (!ENABLE_MEDIA_INSPECTOR || !html) return html;

    // Collect all available topic metadata
    const topicList = (msg.topics && msg.topics.length > 0)
      ? msg.topics.map(t => typeof t === "object" && t !== null ? t : { code: String(t), name: String(t) })
      : (primaryTopic ? [primaryTopic] : (topicVideos?.[0]?.topic_code ? [{ code: topicVideos[0].topic_code, name: topicVideos[0].topic_name || "Course Topic" }] : []));

    const defaultTopic = topicList[0] || {
      code: defaultCode || primaryTopic?.code || topicVideos?.[0]?.topic_code || "01",
      name: primaryTopic?.name || topicVideos?.[0]?.topic_name || "Course Curriculum",
    };

    let output = html;

    // Helper to format short clean display label
    const formatDisplayCode = (code, name, index) => {
      if (!code || code === "N/A") return `Topic ${index + 1}`;
      if (code.length > 10) {
        return `Topic: ${code.slice(0, 8)}…`;
      }
      return `Topic: ${code}`;
    };

    // 0. Replace explicit PDF reference tokens: [[PDF: Document Title | p. 14 | search phrase]]
    output = output.replace(
      /\[\[\s*PDF:\s*([^|\]]+?)\s*(?:\|\s*p\.?\s*(\d+))?\s*(?:\|\s*([^\]]+?))?\s*\]\]/gi,
      (match, rawDocTitle, rawPage, rawSearch) => {
        const docTitle = (rawDocTitle || "").trim();
        const pageNum = (rawPage || "").trim() || "1";
        const searchPhrase = (rawSearch || "").trim();

        // Match PDF from groupedVectorPdfs
        const matched = (groupedVectorPdfs || []).find(p =>
          p.title && docTitle && (
            p.title.toLowerCase().includes(docTitle.toLowerCase()) ||
            docTitle.toLowerCase().includes(p.title.toLowerCase())
          )
        ) || groupedVectorPdfs?.[0] || null;

        const pdfUrl = matched?.link || matched?.url || matched?.pdf_url || "";
        const shortTitle = docTitle.length > 22 ? `${docTitle.slice(0, 20)}…` : docTitle;
        const disp = `📄 ${shortTitle}${pageNum ? `, p. ${pageNum}` : ""}`;

        return `<span class="pdf-citation-pill" data-pdf-url="${pdfUrl}" data-pdf-page="${pageNum}" data-pdf-title="${docTitle}" data-search="${encodeURIComponent(searchPhrase || docTitle)}" style="display:inline-flex;align-items:center;padding:1px 7px;margin:0 4px;border-radius:4px;font-size:0.75rem;font-weight:700;cursor:pointer;background:rgba(217,119,6,0.15);color:#d97706;border:1px solid rgba(217,119,6,0.35);vertical-align:baseline;transition:all 0.15s ease;" title="${docTitle} (Page ${pageNum}) - Click to open PDF and highlight text">[${disp}]</span>`;
      }
    );

    // 0b. Replace explicit Video Transcript reference tokens: [[VIDEO: Video Title | t. 01:23 | search phrase]]
    output = output.replace(
      /\[\[\s*(?:VIDEO|TRANSCRIPT):\s*([^|\]]+?)\s*(?:\|\s*t\.?\s*([0-9:]+))?\s*(?:\|\s*([^\]]+?))?\s*\]\]/gi,
      (match, rawVideoTitle, rawTime, rawSearch) => {
        const videoTitle = (rawVideoTitle || "").trim();
        const timeStamp = (rawTime || "").trim() || "00:00";
        const searchPhrase = (rawSearch || "").trim();

        // Match video from transcriptVideos or topicVideos
        const matched = (transcriptVideos || []).find(v =>
          v.title && videoTitle && (
            v.title.toLowerCase().includes(videoTitle.toLowerCase()) ||
            videoTitle.toLowerCase().includes(v.title.toLowerCase())
          )
        ) || (topicVideos || []).find(v =>
          v.title && videoTitle && (
            v.title.toLowerCase().includes(videoTitle.toLowerCase()) ||
            videoTitle.toLowerCase().includes(v.title.toLowerCase())
          )
        ) || transcriptVideos?.[0] || topicVideos?.[0] || null;

        const videoUrl = matched?.url || "";
        const shortTitle = videoTitle.length > 22 ? `${videoTitle.slice(0, 20)}…` : videoTitle;
        const disp = `🎬 ${shortTitle}${timeStamp ? `, ${timeStamp}` : ""}`;

        return `<span class="transcript-citation-pill" data-video-url="${videoUrl}" data-timestamp="${timeStamp}" data-video-title="${videoTitle}" data-search="${encodeURIComponent(searchPhrase || videoTitle)}" style="display:inline-flex;align-items:center;padding:1px 7px;margin:0 4px;border-radius:4px;font-size:0.75rem;font-weight:700;cursor:pointer;background:rgba(22,163,74,0.15);color:#16a34a;border:1px solid rgba(22,163,74,0.35);vertical-align:baseline;transition:all 0.15s ease;" title="${videoTitle} (${timeStamp}) - Click to play video from timestamp">[${disp}]</span>`;
      }
    );

    // If matched transcript videos exist, attach citation pills contextually to corresponding paragraphs
    if (transcriptVideos && transcriptVideos.length > 0) {
      for (const vid of transcriptVideos) {
        if (!vid || !vid.url) continue;
        const rawTitle = vid.title || "Course Video";
        const shortTitle = rawTitle.length > 20 ? `${rawTitle.slice(0, 18)}…` : rawTitle;
        const disp = `🎬 ${shortTitle}`;

        // Don't duplicate if a pill for this video title is already present
        if (output.includes(`data-video-title="${rawTitle}"`) || output.includes(shortTitle)) continue;

        const pillHtml = ` <span class="transcript-citation-pill" data-video-url="${vid.url}" data-timestamp="00:00" data-video-title="${rawTitle}" data-search="" style="display:inline-flex;align-items:center;padding:1px 7px;margin:0 4px;border-radius:4px;font-size:0.75rem;font-weight:700;cursor:pointer;background:rgba(22,163,74,0.15);color:#16a34a;border:1px solid rgba(22,163,74,0.35);vertical-align:middle;transition:all 0.15s ease;" title="${rawTitle} - Click to play video">[${disp}]</span>`;

        const keywords = `${rawTitle} ${vid.topic_name || ""}`.toLowerCase().split(/\s+/).filter(w => w.length > 3 && !["video", "course", "topic", "lesson", "module", "part", "intro", "introduction"].includes(w));
        if (keywords.length > 0) {
          const matchPattern = new RegExp(`(<p[^>]*>(?:(?!<\\/p>|transcript-citation-pill|pdf-citation-pill)[\\s\\S])*?(?:${keywords.join("|")})[\\s\\S]*?)(<\\/p>)`, "i");
          if (matchPattern.test(output)) {
            output = output.replace(matchPattern, `$1${pillHtml}$2`);
          }
        }
      }
    }

    // If high-confidence matched vector PDFs exist, attach citation pills to corresponding paragraphs
    if (groupedVectorPdfs && groupedVectorPdfs.length > 0) {
      for (const pdf of groupedVectorPdfs) {
        if (!pdf || !pdf.link) continue;
        const pNum = pdf.firstPage || (pdf.pages && pdf.pages[0]) || 1;
        const rawTitle = pdf.title && pdf.title.toLowerCase() !== "untitled document" && pdf.title.toLowerCase() !== "document"
          ? pdf.title
          : (pdf.topic_name || "Document");
        const shortTitle = rawTitle.length > 20 ? `${rawTitle.slice(0, 18)}…` : rawTitle;
        const searchPhrase = (pdf.text_preview || "").slice(0, 30).trim();
        const disp = `📄 ${shortTitle}, p. ${pNum}`;

        // Don't duplicate if a pill for this specific page & title is already present
        if (output.includes(`data-pdf-page="${pNum}"`) && output.includes(shortTitle)) continue;

        const pillHtml = ` <span class="pdf-citation-pill" data-pdf-url="${pdf.link}" data-pdf-page="${pNum}" data-pdf-title="${rawTitle}" data-search="${encodeURIComponent(searchPhrase)}" style="display:inline-flex;align-items:center;padding:1px 7px;margin:0 4px;border-radius:4px;font-size:0.75rem;font-weight:700;cursor:pointer;background:rgba(217,119,6,0.15);color:#d97706;border:1px solid rgba(217,119,6,0.35);vertical-align:middle;transition:all 0.15s ease;" title="${rawTitle} (Page ${pNum}) - Click to open PDF and highlight text">[${disp}]</span>`;

        // Contextual matching: Only attach if a paragraph actually discusses concepts from this PDF.
        // We never forcefully attach citations to unrelated paragraphs.
        const keywords = `${rawTitle} ${pdf.topic_name || ""}`.toLowerCase().split(/\s+/).filter(w => w.length > 3 && !["document", "untitled", "code", "part", "volume", "regulations", "guide"].includes(w));
        if (keywords.length > 0) {
          const matchPattern = new RegExp(`(<p[^>]*>(?:(?!<\\/p>|pdf-citation-pill)[\\s\\S])*?(?:${keywords.join("|")})[\\s\\S]*?)(<\\/p>)`, "i");
          if (matchPattern.test(output)) {
            output = output.replace(matchPattern, `$1${pillHtml}$2`);
          }
        }
      }
    }

    // 1. Replace explicit ref markers if present: @@SOURCE_REF_1@@ or [[Ref: 1]]
    output = output.replace(
      /(?:@@SOURCE_REF_|\[\[\s*Ref:?\s*)(\d+)\s*(?:@@|\]\])/gi,
      (match, refNum) => {
        const idx = Math.max(0, parseInt(refNum, 10) - 1);
        const targetTopic = topicList[idx] || defaultTopic;
        const disp = formatDisplayCode(targetTopic.code, targetTopic.name, idx);
        return `<span class="citation-pill" data-ref="${targetTopic.code}" data-topic-name="${targetTopic.name}" style="display:inline-flex;align-items:center;padding:1px 6px;margin:0 4px;border-radius:4px;font-size:0.75rem;font-weight:700;cursor:pointer;background:rgba(2,132,199,0.15);color:#0284c7;border:1px solid rgba(2,132,199,0.3);vertical-align:baseline;transition:all 0.15s ease;" title="${targetTopic.name} [${targetTopic.code}] - Click to inspect source">[${disp}]</span>`;
      }
    );

    // 2. Add citation badge to markdown section headings (h1, h2, h3, h4)
    let headingCounter = 0;
    const hasHeadings = /<\/(h[1-4])>/i.test(output);

    output = output.replace(
      /(<h[1-4][^>]*>)([\s\S]*?)(<\/(h[1-4])>)/gi,
      (fullMatch, openTag, headingContent, closeTag) => {
        // Find matching topic for this heading: either by keyword match or sequential distribution
        let matchedTopic = null;
        if (topicList.length > 1) {
          const lowerHeading = headingContent.toLowerCase();
          matchedTopic = topicList.find(t => {
            if (!t.name) return false;
            const words = t.name.toLowerCase().split(/\s+/).filter(w => w.length > 3);
            return words.some(w => lowerHeading.includes(w));
          });
        }
        if (!matchedTopic) {
          matchedTopic = topicList[headingCounter % Math.max(1, topicList.length)] || defaultTopic;
        }
        const disp = formatDisplayCode(matchedTopic.code, matchedTopic.name, headingCounter);
        headingCounter++;

        return `${openTag}${headingContent} <span class="citation-pill" data-ref="${matchedTopic.code}" data-topic-name="${matchedTopic.name}" style="display:inline-flex;align-items:center;padding:2px 7px;margin-left:6px;border-radius:4px;font-size:0.72rem;font-weight:700;cursor:pointer;background:rgba(2,132,199,0.15);color:#0284c7;border:1px solid rgba(2,132,199,0.3);vertical-align:middle;transition:all 0.15s ease;" title="${matchedTopic.name} [${matchedTopic.code}] - Click to inspect topic & media">[${disp}]</span>${closeTag}`;
      }
    );

    // 3. If NO headings exist in the markdown output, append citation badge beside paragraphs (<p>)
    if (!hasHeadings && topicList.length > 0) {
      let pCounter = 0;
      output = output.replace(
        /(<\/p>)/gi,
        (match) => {
          const targetTopic = topicList[pCounter % topicList.length] || defaultTopic;
          const disp = formatDisplayCode(targetTopic.code, targetTopic.name, pCounter);
          pCounter++;
          return ` <span class="citation-pill" data-ref="${targetTopic.code}" data-topic-name="${targetTopic.name}" style="display:inline-flex;align-items:center;padding:1px 6px;margin-left:6px;border-radius:4px;font-size:0.72rem;font-weight:700;cursor:pointer;background:rgba(2,132,199,0.15);color:#0284c7;border:1px solid rgba(2,132,199,0.3);vertical-align:middle;transition:all 0.15s ease;" title="${targetTopic.name} [${targetTopic.code}] - Click to inspect topic & media">[${disp}]</span>${match}`;
        }
      );
    }

    return output;
  };

  const handleMarkdownClick = (e) => {
    const targetLink = e.target.closest("a");
    if (targetLink) {
      const href = targetLink.getAttribute("href") || "";
      if (href.startsWith("#ask:") || href.startsWith("ask:")) {
        e.preventDefault();
        e.stopPropagation();
        const rawQuery = href.startsWith("#ask:") ? href.slice(5) : href.slice(4);
        const query = decodeURIComponent(rawQuery).trim();
        if (query) {
          handleFollowUpQuestion(query);
        }
        return;
      }
    }

    // Handle in-text PDF citation pill click (jump to page and highlight text)
    const pdfPill = e.target.closest(".pdf-citation-pill");
    if (pdfPill) {
      e.preventDefault();
      e.stopPropagation();
      const pdfUrl = pdfPill.getAttribute("data-pdf-url") || "";
      const pdfPage = pdfPill.getAttribute("data-pdf-page") || "1";
      const pdfTitle = pdfPill.getAttribute("data-pdf-title") || "PDF Document";
      const rawSearch = pdfPill.getAttribute("data-search") || "";
      const searchPhrase = rawSearch ? decodeURIComponent(rawSearch).trim() : "";

      if (pdfUrl) {
        const searchParam = searchPhrase ? `&search=${encodeURIComponent(searchPhrase.slice(0, 40))}` : "";
        const targetUrl = `${pdfUrl}#page=${pdfPage}${searchParam}`;
        openPreview("pdf", targetUrl, `${pdfTitle} (Page ${pdfPage})`);
      }
      return;
    }

    // Handle in-text Video Transcript citation pill click (jump to video timestamp)
    const transcriptPill = e.target.closest(".transcript-citation-pill");
    if (transcriptPill) {
      e.preventDefault();
      e.stopPropagation();
      const videoTitle = transcriptPill.getAttribute("data-video-title") || "Course Video";
      const timestampStr = transcriptPill.getAttribute("data-timestamp") || "00:00";
      const videoUrlAttr = transcriptPill.getAttribute("data-video-url") || "";

      // Match video from transcriptVideos or topicVideos
      const matched = (transcriptVideos || []).find(v =>
        v.title && videoTitle && (
          v.title.toLowerCase().includes(videoTitle.toLowerCase()) ||
          videoTitle.toLowerCase().includes(v.title.toLowerCase())
        )
      ) || (topicVideos || []).find(v =>
        v.title && videoTitle && (
          v.title.toLowerCase().includes(videoTitle.toLowerCase()) ||
          videoTitle.toLowerCase().includes(v.title.toLowerCase())
        )
      ) || transcriptVideos?.[0] || topicVideos?.[0] || null;

      const targetUrl = videoUrlAttr || matched?.url || "";
      if (targetUrl) {
        let seekSeconds = 0;
        if (timestampStr.includes(":")) {
          const parts = timestampStr.split(":").map(Number);
          seekSeconds = parts.length === 2 ? parts[0] * 60 + parts[1] : (parts[0] * 3600 + parts[1] * 60 + parts[2]);
        } else if (!isNaN(Number(timestampStr))) {
          seekSeconds = Number(timestampStr);
        }
        const cleanBaseUrl = targetUrl.split("#")[0];
        const playerUrl = `${cleanBaseUrl}#t=${seekSeconds}`;
        openPreview("video", playerUrl, `${matched?.title || videoTitle} (${timestampStr})`);
      }
      return;
    }

    // Handle in-text topic citation pill click
    const citationBadge = e.target.closest(".citation-pill");
    if (citationBadge) {
      e.preventDefault();
      e.stopPropagation();
      const refId = citationBadge.getAttribute("data-ref") || primaryTopic?.code || topicVideos?.[0]?.topic_code || "01";
      const refTopicName = citationBadge.getAttribute("data-topic-name") || primaryTopic?.name || topicVideos?.[0]?.topic_name || "Course Topic";

      const matchedTopicObj = (Array.isArray(msg.topics) ? msg.topics : []).find(
        (t) => (t && typeof t === "object" && (t.code === refId || t.topic_code === refId))
      ) || null;

      const matchedVideo = (topicVideos || []).find(v => v.topic_code === refId) ||
        (transcriptVideos || []).find(v => v.topic_code === refId) ||
        topicVideos?.[0] || transcriptVideos?.[0] || null;

      const matchedImage = (normalizedImages || []).find(img => img.topic_code === refId) ||
        normalizedImages?.[0] || null;

      if (onOpenInspector) {
        onOpenInspector({
          sectionTitle: `Topic Source [${refId.length > 10 ? refId.slice(0, 8) + '…' : refId}]`,
          topic_name: refTopicName,
          topic_code: refId,
          course_code: matchedTopicObj?.course_code || matchedTopicObj?.courseCode || matchedVideo?.course_code || primaryCourse?.code || "",
          course_name: matchedTopicObj?.course_name || matchedTopicObj?.courseName || matchedVideo?.course_name || primaryCourse?.name || "",
          video: matchedVideo,
          image: matchedImage,
          pdf: normalizedPdfs?.[0] || null,
        });
      }
    }
  };

  const renderSingleVideoCard = (video, i, badgeText, isSpeech = false) => (
    <Box
      key={`${video.url}-${i}`}
      sx={mediaCardSx}
      onClick={() => openPreview("video", video.url, video.title)}
    >
      {/* Test Mode: Origin badge + Info Inspector Icon */}
      {ENABLE_MEDIA_INSPECTOR && (
        <Box
          sx={{
            position: "absolute",
            top: 6,
            left: 6,
            right: 6,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            zIndex: 3,
            pointerEvents: "none",
          }}
        >
          <Box
            sx={{
              bgcolor: isSpeech ? "rgba(245, 158, 11, 0.9)" : "rgba(2, 132, 199, 0.9)",
              color: "#fff",
              fontSize: "0.65rem",
              fontWeight: 700,
              px: 0.8,
              py: 0.2,
              borderRadius: "4px",
              boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
              maxWidth: "75%",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {badgeText}
          </Box>
          <Box
            sx={{
              pointerEvents: "auto",
              cursor: "pointer",
              bgcolor: "rgba(15, 23, 42, 0.85)",
              color: "#fff",
              width: 22,
              height: 22,
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
              "&:hover": {
                bgcolor: "#0284c7",
                transform: "scale(1.1)",
              },
              transition: "all 0.15s ease",
            }}
            onClick={(e) => {
              e.stopPropagation();
              if (onOpenInspector) {
                onOpenInspector({
                  sectionTitle: isSpeech ? "Transcript Vector Video" : "Curriculum Video",
                  topic_name: video.topic_name || primaryTopic?.name || "Maritime Curriculum",
                  topic_code: video.topic_code || primaryTopic?.code || "Curriculum",
                  course_code: video.course_code || primaryCourse?.code || "",
                  course_name: video.course_name || primaryCourse?.name || "",
                  video,
                });
              }
            }}
            title="Inspect Provenance (Video ID & Topic Code)"
          >
            <InfoOutlinedIcon sx={{ fontSize: 14 }} />
          </Box>
        </Box>
      )}

      {video.thumbnail && (
        <Box
          component="img"
          src={video.thumbnail}
          alt={video.title}
          sx={mediaThumbnailSx}
          onError={(e) => {
            e.target.style.display = 'none';
            const fallback = e.target.nextElementSibling;
            if (fallback && fallback.classList.contains('fallback-icon-container')) {
              fallback.style.display = 'flex';
            }
          }}
        />
      )}
      <Box
        className="fallback-icon-container"
        sx={{
          ...mediaThumbnailSx,
          display: video.thumbnail ? "none" : "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "background.paper",
        }}
      >
        <VideoIcon size={40} color="primary.main" />
      </Box>
      <Box
        sx={{
          position: "absolute",
          top: "40%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 36,
          height: 36,
          borderRadius: "50%",
          backgroundColor: "rgba(0,0,0,0.45)",
        }}
      >
        <PlayArrowRoundedIcon
          sx={{ color: "#fff", fontSize: 22 }}
        />
      </Box>
      <Typography variant="caption" sx={mediaCaptionSx}>
        {video.title}
      </Typography>
    </Box>
  );

  // ── Shared card style ───
  const mediaCardSx = {
    position: "relative",
    display: "flex",
    flexDirection: "column",
    justifyContent: "space-between",
    width: { xs: "43%", sm: "23%" },
    height: { xs: 140, sm: 170 },
    textDecoration: "none",
    borderRadius: 2,
    p: 0.5,
    backgroundColor: "background.light",
    transition: "0.2s",
    border: "1px solid transparent",
    borderColor: "text.caption",
    cursor: "pointer",
    "&:hover": { borderColor: "primary.main", transform: "translateY(-2px)" },
  };

  const mediaThumbnailSx = {
    width: "100%",
    height: { xs: 100, sm: 130 },
    borderRadius: 1,
    objectFit: "cover",
  };

  const mediaCaptionSx = {
    width: "100%",
    textAlign: "center",
    color: "primary.main",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  };
  // ── Render ────
  return (
    <>
      <Box
        sx={{
          display: "flex",
          alignItems: "flex-start",
          gap: 1,
          flexDirection: isUser ? "row-reverse" : "row",
        }}
      >
        {/* Avatar */}
        {isUser ? (
          <Avatar
            sx={{
              width: { xs: 40, sm: 50 },
              height: { xs: 40, sm: 50 },
              backgroundColor: "primary.main",
            }}
          />
        ) : (
          <Box
            sx={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              width: { xs: 40, sm: 50 },
              height: { xs: 40, sm: 50 },
              borderRadius: 60,
              backgroundColor: "primary.main",
              flexShrink: 0,
            }}
          >
            <Box
              component="img"
              src={DolphinIconW}
              alt="Dolphin"
              sx={{ width: { xs: 25, sm: 30 }, height: { xs: 25, sm: 30 } }}
            />
          </Box>
        )}

        {/* Content column */}
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            width: isUser ? "auto" : "90%",
            maxWidth: "90%",
            gap: 0.5,
          }}
        >
          {/* Name + timestamp */}
          <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
            <Typography
              variant={isUser ? "h4" : "body1"}
              sx={{ fontWeight: 700, color: "text.heading1" }}
            >
              {isUser ? "You" : "Dolphin AI"}
            </Typography>
            <Typography variant="caption" sx={{ color: "text.caption" }}>
              {getFormattedTime(msg?.timestamp)}
            </Typography>
          </Box>

          {/* Bubble */}
          <Box
            sx={{
              bgcolor: isUser
                ? "background.light"
                : "background.chatbackground",
              px: 2.5,
              py: 2,
              borderRadius: isUser
                ? "18px 4px 18px 18px"
                : "4px 18px 18px 18px",
            }}
          >
            {msg.category !== "QUIZ" ? (
              <Box sx={{ display: "flex", flexDirection: "column" }}>
                {/* Understanding section */}
                {msg.understanding && (
                  <Box
                    sx={{
                      mb: 1.5,
                      pb: 1.5,
                      borderBottom: "1px solid",
                      borderColor: "divider",
                      opacity: 0.9,
                    }}
                  >
                    <Typography
                      component="p"
                      sx={{
                        m: 0,
                        lineHeight: 1.7,
                        wordBreak: "break-word",
                        overflowWrap: "break-word",
                        whiteSpace: "normal",
                      }}
                    >
                      {(msg.understanding || "")
                        // Remove bullet points
                        .replace(/(^|\n)\s*[-*•]\s+/g, "$1")
                        // Remove numbered points
                        .replace(/(^|\n)\s*\d+[.)]\s+/g, "$1")
                        // Convert line breaks to spaces
                        .replace(/\s+/g, " ")
                        .trim()}
                    </Typography>
                  </Box>
                )}

                {/* Test Mode: Interactive Topic Pill Banner */}
                {ENABLE_MEDIA_INSPECTOR && !isUser && (Boolean(primaryTopic?.name) || Boolean(primaryTopic?.code) || (msg.topics && msg.topics.length > 0) || Boolean(topicVideos?.[0]?.topic_code)) && (
                  <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.8, mb: 1.5, alignItems: "center" }}>
                    <Typography variant="caption" sx={{ color: "text.caption", fontWeight: 700, fontSize: "0.72rem" }}>
                      TOPIC REF:
                    </Typography>
                    {(msg.topics && msg.topics.length > 0 ? msg.topics : [primaryTopic || { code: topicVideos?.[0]?.topic_code || "01", name: topicVideos?.[0]?.topic_name || "Course Topic" }]).map((t, tIdx) => {
                      const tObj = typeof t === "object" && t !== null ? t : { code: String(t), name: String(t) };
                      const tName = tObj.name || tObj.topic_name || primaryTopic?.name || topicVideos?.[0]?.topic_name || "Curriculum Lesson";
                      const tCode = tObj.code || tObj.topic_code || primaryTopic?.code || topicVideos?.[0]?.topic_code || "Ref";
                      return (
                        <Box
                          key={tIdx}
                          onClick={() => {
                            if (onOpenInspector) {
                              onOpenInspector({
                                sectionTitle: `Curriculum Lesson`,
                                topic_name: tName,
                                topic_code: tCode,
                                course_code: tObj.course_code || primaryCourse?.code || "",
                                course_name: tObj.course_name || primaryCourse?.name || "",
                                video: topicVideos?.[0] || null,
                                image: normalizedImages?.[0] || null,
                                pdf: normalizedPdfs?.[0] || null,
                              });
                            }
                          }}
                          sx={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 0.6,
                            cursor: "pointer",
                            py: 0.3,
                            px: 1,
                            borderRadius: "6px",
                            bgcolor: mode === "dark" ? "rgba(56, 189, 248, 0.12)" : "rgba(2, 132, 199, 0.08)",
                            border: "1px solid",
                            borderColor: mode === "dark" ? "rgba(56, 189, 248, 0.25)" : "rgba(2, 132, 199, 0.2)",
                            color: mode === "dark" ? "#38bdf8" : "#0284c7",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            "&:hover": {
                              bgcolor: mode === "dark" ? "rgba(56, 189, 248, 0.2)" : "rgba(2, 132, 199, 0.16)",
                              transform: "translateY(-1px)",
                            },
                            transition: "all 0.15s ease",
                          }}
                          title="Click to inspect Topic Code and media"
                        >
                          <span>{tName}</span>
                          {tCode && (
                            <span style={{ opacity: 0.85, fontFamily: "monospace", fontSize: "0.72rem", fontWeight: 700 }}>
                              [{tCode}]
                            </span>
                          )}
                          <InfoOutlinedIcon sx={{ fontSize: 13, ml: 0.2 }} />
                        </Box>
                      );
                    })}
                  </Box>
                )}

                {/* Main content and Sources */}
                <Box
                  sx={{
                    display: "block",
                    lineHeight: 1.7,
                  }}
                >
                  {plainText ? (
                    <Typography
                      component="div"
                      sx={{
                        lineHeight: 1.7,
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                        overflowWrap: "break-word",
                      }}
                    >
                      {cleanPlainText(sanitizeDisplayContent(msg.content || ""))}
                    </Typography>
                  ) : (
                    <Box
                      component="div"
                      className="chat-markdown"
                      onClick={handleMarkdownClick}
                      sx={{
                        ...markdownContainerSx,
                        display: "block",
                      }}
                      dangerouslySetInnerHTML={{
                        __html: decorateWithCitations(
                          sanitizeMarkdown(
                            prepareClickableSubtopics(
                              sanitizeDisplayContent(msg.content || ""),
                              subtopicCandidates
                            ),
                            skipMarkdownFormatting
                          )
                        ),
                      }}
                    />
                  )}
                </Box>

                {/* Company Content section */}
                {(msg.company_content || msg.companyContent) && (
                  <Box
                    sx={{
                      mt: 1.5,
                      pt: 1.5,
                      borderTop: "1px solid",
                      borderColor: "divider",
                      display: "block",
                      lineHeight: 1.7,
                    }}
                  >
                    <Box
                      className="chat-markdown"
                      onClick={handleMarkdownClick}
                      sx={{
                        ...markdownContainerSx,
                        display: "block",
                      }}
                      dangerouslySetInnerHTML={{
                        __html: decorateWithCitations(
                          sanitizeMarkdown(msg.company_content || msg.companyContent, true)
                        ),
                      }}
                    />
                  </Box>
                )}

              </Box>
            ) : (
              <QuizDisplay quizContent={msg.content || []} />
            )}

            {/* Image Suggestions */}
            {!isUser && shouldShowMedia && normalizedImages.length > 0 && (
              <Box sx={{ mt: 2.5 }}>
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 0.5,
                    mb: 1,
                  }}
                >
                  <ImageIcon
                    size={20}
                    color={mode === "dark" ? "#e8f1fb" : "#0f1c2e"}
                  />
                  <Typography variant="h3" sx={{ color: "text.primary" }}>
                    Images
                  </Typography>
                </Box>

                <Box
                  sx={{
                    display: "flex",
                    gap: 2,
                    flexWrap: "wrap",
                    py: 1,
                  }}
                >
                  {normalizedImages.map((img, i) => (
                    <Box
                      key={`${img.url}-${i}`}
                      sx={mediaCardSx}
                      onClick={() => openPreview("image", img.url, img.title)}
                    >
                      <Box
                        component="img"
                        src={img.url}
                        alt={img.title}
                        sx={mediaThumbnailSx}
                        onError={(e) => {
                          const currentSrc = e.target.src || "";
                          if (currentSrc.endsWith(".png") && !e.target.dataset.triedJpg) {
                            e.target.dataset.triedJpg = "true";
                            e.target.src = currentSrc.replace(/\.png$/, ".jpg");
                          } else if (currentSrc.endsWith(".jpg") && !e.target.dataset.triedJpeg) {
                            e.target.dataset.triedJpeg = "true";
                            e.target.src = currentSrc.replace(/\.jpg$/, ".jpeg");
                          } else {
                            const card = e.target.parentElement;
                            if (card) card.style.display = "none";
                            setFailedImageUrls((prev) => new Set(prev).add(img.url));
                          }
                        }}
                      />
                      <Typography variant="caption" sx={mediaCaptionSx}>
                        {img.title}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </Box>
            )}

            {/* Videos Section */}
            {!isUser && shouldShowMedia && (
              ENABLE_MEDIA_INSPECTOR ? (
                <>
                  {/* Part 1: Videos Taken From Text Content */}
                  {topicVideos.length > 0 && (
                    <Box sx={{ mt: 2.5 }}>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 0.8, mb: 1 }}>
                        <VideoIcon size={26} color={mode === "dark" ? "#e8f1fb" : "#0f1c2e"} />
                        <Typography variant="h3" sx={{ color: "text.primary" }}>
                          Part 1: Videos Taken From Text Content
                        </Typography>
                        <Typography variant="caption" sx={{ color: "text.caption", ml: 0.5, fontWeight: 600 }}>
                          ({topicVideos.length})
                        </Typography>
                      </Box>
                      <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap", py: 1 }}>
                        {topicVideos.map((v, i) =>
                          renderSingleVideoCard(
                            v,
                            i,
                            `Topic: ${v.topic_code || primaryTopic?.code || "Curriculum"}`,
                            false
                          )
                        )}
                      </Box>
                    </Box>
                  )}

                  {/* Part 2: Videos Taken From Transcribe Matched Content */}
                  <Box sx={{ mt: 2.5 }}>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.8, mb: 1 }}>
                      <VideoIcon size={26} color="#f59e0b" />
                      <Typography variant="h3" sx={{ color: "text.primary" }}>
                        Part 2: Videos Taken From Transcribe Matched Content
                      </Typography>
                      <Typography variant="caption" sx={{ color: "text.caption", ml: 0.5, fontWeight: 600 }}>
                        ({transcriptVideos.length})
                      </Typography>
                    </Box>
                    {transcriptVideos.length > 0 ? (
                      <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap", py: 1 }}>
                        {transcriptVideos.map((v, i) =>
                          renderSingleVideoCard(
                            v,
                            i,
                            "Speech Match",
                            true
                          )
                        )}
                      </Box>
                    ) : (
                      <Box
                        sx={{
                          p: 1.5,
                          borderRadius: 2,
                          bgcolor: mode === "dark" ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.02)",
                          border: "1px dashed",
                          borderColor: "divider",
                          display: "flex",
                          alignItems: "center",
                          gap: 1,
                        }}
                      >
                        <Typography variant="caption" sx={{ color: "text.caption", fontStyle: "italic" }}>
                          No spoken transcript matches found in audio database for this query.
                        </Typography>
                      </Box>
                    )}
                  </Box>
                </>
              ) : (
                /* Original Production Layout */
                unifiedVideos.length > 0 && (
                  <Box sx={{ mt: 2.5 }}>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 0.5,
                        mb: 1,
                      }}
                    >
                      <VideoIcon
                        size={30}
                        color={mode === "dark" ? "#e8f1fb" : "#0f1c2e"}
                      />
                      <Typography variant="h3" sx={{ color: "text.primary" }}>
                        Videos
                      </Typography>
                    </Box>

                    <Box
                      sx={{
                        display: "flex",
                        gap: 2,
                        flexWrap: "wrap",
                        py: 1,
                      }}
                    >
                      {unifiedVideos.map((video, i) => (
                        <Box
                          key={`${video.url}-${i}`}
                          sx={mediaCardSx}
                          onClick={() => openPreview("video", video.url, video.title)}
                        >
                          {video.thumbnail && (
                            <Box
                              component="img"
                              src={video.thumbnail}
                              alt={video.title}
                              sx={mediaThumbnailSx}
                              onError={(e) => {
                                e.target.style.display = 'none';
                                const fallback = e.target.nextElementSibling;
                                if (fallback && fallback.classList.contains('fallback-icon-container')) {
                                  fallback.style.display = 'flex';
                                }
                              }}
                            />
                          )}
                          <Box
                            className="fallback-icon-container"
                            sx={{
                              ...mediaThumbnailSx,
                              display: video.thumbnail ? "none" : "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              backgroundColor: "background.paper",
                            }}
                          >
                            <VideoIcon size={40} color="primary.main" />
                          </Box>
                          <Box
                            sx={{
                              position: "absolute",
                              top: "40%",
                              left: "50%",
                              transform: "translate(-50%, -50%)",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              width: 36,
                              height: 36,
                              borderRadius: "50%",
                              backgroundColor: "rgba(0,0,0,0.45)",
                            }}
                          >
                            <PlayArrowRoundedIcon
                              sx={{ color: "#fff", fontSize: 22 }}
                            />
                          </Box>
                          <Typography variant="caption" sx={mediaCaptionSx}>
                            {video.title}
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  </Box>
                )
              )
            )}

            {/* PDF Suggestions */}
            {!isUser && shouldShowMedia && (
              ENABLE_MEDIA_INSPECTOR ? (
                <>
                  {/* Part 1: PDFs Taken From Text Content */}
                  {normalizedPdfs.length > 0 && (
                    <Box sx={{ mt: 2.5 }}>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 0.8, mb: 1 }}>
                        <DocumentIcon size={22} color={mode === "dark" ? "#e8f1fb" : "#0f1c2e"} />
                        <Typography variant="h3" sx={{ color: "text.primary" }}>
                          Part 1: PDFs Taken From Text Content
                        </Typography>
                        <Typography variant="caption" sx={{ color: "text.caption", ml: 0.5, fontWeight: 600 }}>
                          ({normalizedPdfs.length})
                        </Typography>
                      </Box>
                      <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap", py: 1 }}>
                        {normalizedPdfs.map((pdf, i) => (
                          <Box
                            key={`${pdf.link}-${i}`}
                            sx={mediaCardSx}
                            onClick={() => openPreview("pdf", pdf.link, pdf.title)}
                            title={pdf.title}
                          >
                            <PdfThumbnail pdf={pdf} mediaThumbnailSx={mediaThumbnailSx} />
                            <Typography variant="caption" sx={mediaCaptionSx} title={pdf.title}>
                              {pdf.title}
                            </Typography>
                          </Box>
                        ))}
                      </Box>
                    </Box>
                  )}

                  {/* Part 2: PDFs Taken From Vector Matched Content */}
                  {groupedVectorPdfs.length > 0 && (
                    <Box sx={{ mt: 2.5 }}>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 0.8, mb: 1 }}>
                        <DocumentIcon size={22} color="#3b82f6" />
                        <Typography variant="h3" sx={{ color: "text.primary" }}>
                          Part 2: PDFs Taken From Vector Matched Content
                        </Typography>
                        <Typography variant="caption" sx={{ color: "text.caption", ml: 0.5, fontWeight: 600 }}>
                          ({groupedVectorPdfs.length})
                        </Typography>
                      </Box>
                      <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap", py: 1 }}>
                        {groupedVectorPdfs.map((pdf, i) => {
                          const pagesLabel = (pdf.pages || [pdf.page || 1]).join(", ");
                          const matchLabel = pdf.bestMatchPct ? `${pdf.bestMatchPct}% match` : "";

                          return (
                            <Box
                              key={`vector-pdf-${pdf.title}-${i}`}
                              sx={mediaCardSx}
                              onClick={() => {
                                if (pdf.link) {
                                  openPreview("pdf", pdf.link, pdf.title, pdf.firstPage || 1);
                                }
                              }}
                              title={`${pdf.title} (Page ${pagesLabel})`}
                            >
                              {/* Top Overlay: Page badge, Match % badge, and Info (i) button */}
                              <Box
                                sx={{
                                  position: "absolute",
                                  top: 6,
                                  left: 6,
                                  right: 6,
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "center",
                                  zIndex: 3,
                                  pointerEvents: "none",
                                }}
                              >
                                {/* Left badges: Page numbers + Match percentage */}
                                <Box sx={{ display: "flex", gap: 0.5, alignItems: "center", flexWrap: "wrap", maxWidth: "75%" }}>
                                  <Box
                                    sx={{
                                      bgcolor: "rgba(2, 132, 199, 0.9)",
                                      color: "#fff",
                                      fontSize: "0.65rem",
                                      fontWeight: 700,
                                      px: 0.8,
                                      py: 0.2,
                                      borderRadius: "4px",
                                      boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
                                      whiteSpace: "nowrap",
                                      overflow: "hidden",
                                      textOverflow: "ellipsis",
                                    }}
                                  >
                                    Page {pagesLabel}
                                  </Box>
                                  {matchLabel && (
                                    <Box
                                      sx={{
                                        bgcolor: "rgba(16, 185, 129, 0.9)",
                                        color: "#fff",
                                        fontSize: "0.65rem",
                                        fontWeight: 700,
                                        px: 0.8,
                                        py: 0.2,
                                        borderRadius: "4px",
                                        boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
                                      }}
                                    >
                                      {matchLabel}
                                    </Box>
                                  )}
                                </Box>

                                {/* Right (i) Info Inspector Button */}
                                <Box
                                  sx={{
                                    pointerEvents: "auto",
                                    cursor: "pointer",
                                    bgcolor: "rgba(15, 23, 42, 0.85)",
                                    color: "#fff",
                                    width: 22,
                                    height: 22,
                                    borderRadius: "50%",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
                                    "&:hover": {
                                      bgcolor: "#0284c7",
                                      transform: "scale(1.1)",
                                    },
                                    transition: "all 0.15s ease",
                                  }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onOpenInspector?.({
                                      sectionTitle: "Vector Matched PDF",
                                      type: "vector_pdf",
                                      title: pdf.title,
                                      url: pdf.link,
                                      pdf: pdf,
                                      page: pagesLabel,
                                      match_pct: pdf.bestMatchPct,
                                      text_preview: pdf.text_preview || pdf.raw_text || pdf.text,
                                      topic_code: pdf.topic_code || primaryTopic?.code || "",
                                      topic_name: pdf.topic_name || primaryTopic?.name || "",
                                      course_code: pdf.course_code || primaryCourse?.code || "",
                                      course_name: pdf.course_name || primaryCourse?.name || "",
                                    });
                                  }}
                                  title="Inspect PDF citation & origin metadata"
                                >
                                  <InfoOutlinedIcon sx={{ fontSize: 13 }} />
                                </Box>
                              </Box>

                              {/* Card Body: Identical to Part 1 Thumbnail */}
                              <PdfThumbnail pdf={pdf} mediaThumbnailSx={mediaThumbnailSx} />
                              <Typography variant="caption" sx={mediaCaptionSx} title={pdf.title}>
                                {pdf.title}
                              </Typography>
                            </Box>
                          );
                        })}
                      </Box>
                    </Box>
                  )}
                </>
              ) : (
                /* Original Production Layout */
                normalizedPdfs.length > 0 && (
                  <Box sx={{ mt: 2.5 }}>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 0.5,
                        mb: 1,
                      }}
                    >
                      <DocumentIcon
                        size={20}
                        color={mode === "dark" ? "#e8f1fb" : "#0f1c2e"}
                      />
                      <Typography variant="h3" sx={{ color: "text.primary" }}>
                        Documents
                      </Typography>
                    </Box>

                    <Box
                      sx={{
                        display: "flex",
                        gap: 2,
                        flexWrap: "wrap",
                        py: 1,
                      }}
                    >
                      {normalizedPdfs.map((pdf, i) => (
                        <Box
                          key={`${pdf.link}-${i}`}
                          sx={mediaCardSx}
                          onClick={() => openPreview("pdf", pdf.link, pdf.title)}
                          title={pdf.title}
                        >
                          <PdfThumbnail
                            pdf={pdf}
                            mediaThumbnailSx={mediaThumbnailSx}
                          />
                          <Typography variant="caption" sx={mediaCaptionSx} title={pdf.title}>
                            {pdf.title}
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  </Box>
                )
              )
            )}

            {/* Related Courses UI temporarily hidden.
            {(() => {
              if (isOutOfScope || !msg.checkLicCoursesData || !Array.isArray(msg.checkLicCoursesData) || msg.checkLicCoursesData.length === 0) return null;

              const userType = msg.checkLicCoursesData[0]?.user_type?.toLowerCase() || "";
              const isStudent = userType === "student";

              const coursesToShow = msg.checkLicCoursesData.filter((item) => {
                if (isStudent) return item.matched;
                return true;
              });

              const uniqueCoursesMap = new Map();
              coursesToShow.forEach((item) => {
                const courseInfo = item.data?.course;
                if (courseInfo) {
                  const code = courseInfo.CourseCode || courseInfo.courseCode;
                  if (code && !uniqueCoursesMap.has(code)) {
                    uniqueCoursesMap.set(code, {
                      ...courseInfo,
                      matched: item.matched,
                      topicName: item.data?.topic_name
                    });
                  }
                }
              });

              const uniqueCourses = Array.from(uniqueCoursesMap.values());

              if (uniqueCourses.length === 0) return null;

              return (
                <Box sx={{ mt: 3, mb: 1 }}>
                  <Typography
                    variant="overline"
                    sx={{
                      color: "text.secondary",
                      fontWeight: 700,
                      letterSpacing: "0.08em",
                      mb: 1.5,
                      display: "block"
                    }}
                  >
                    Related Courses
                  </Typography>
                  <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
                    {uniqueCourses.map((course, i) => (
                      <Box
                        key={i}
                        sx={(theme) => ({
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          p: 1.5,
                          borderRadius: 2,
                          backgroundColor: course.matched
                            ? theme.palette.mode === "dark" ? "rgba(46, 125, 50, 0.15)" : "rgba(46, 125, 50, 0.04)"
                            : theme.palette.mode === "dark" ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.02)",
                          border: `1px solid ${course.matched
                            ? theme.palette.mode === "dark" ? "rgba(76, 175, 80, 0.3)" : "rgba(46, 125, 50, 0.2)"
                            : theme.palette.divider
                            }`,
                        })}
                      >
                        <Box>
                          <Typography variant="body2" sx={{ fontWeight: 600, color: "text.primary" }}>
                            {course.CourseName || course.courseName || "Unknown Course"}
                          </Typography>
                          <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mt: 0.5 }}>
                            {course.topicName && `Topic: ${course.topicName}`}
                          </Typography>
                        </Box>
                        {course.matched && (
                          <Box sx={{ bgcolor: "success.main", color: "success.contrastText", px: 1.5, py: 0.5, borderRadius: 1.5, fontSize: "0.7rem", fontWeight: 700, letterSpacing: "0.05em" }}>
                            LICENSED
                          </Box>
                        )}
                      </Box>
                    ))}
                  </Box>
                </Box>
              );
            })()}


            */}

            {/* Follow-up suggestions (Preserved "Try asking..." full questions) */}
            {shouldShowQuestions && (
              <Box
                sx={{
                  mt: 2.5,
                  display: "flex",
                  flexDirection: "column",
                  gap: 1,
                }}
              >
                <Typography
                  variant="body1"
                  sx={{
                    color: "text.primary",
                    fontWeight: 600,
                    letterSpacing: "0.08em",
                  }}
                >
                  Try asking...
                </Typography>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                  {normalizedSuggestions.map((item, i) => (
                    <Box
                      key={`try-asking-${i}`}
                      sx={(theme) => ({
                        display: "flex",
                        alignItems: "center",
                        p: 1,
                        borderRadius: 3,
                        backgroundColor: "background.light",
                        cursor: "pointer",
                        transition: "all 0.2s ease",
                        border: "1.5px solid transparent",
                        "&:hover": {
                          borderColor: theme.palette.primary.main,
                          color: theme.palette.primary.main,
                        },
                      })}
                      onClick={() => handleFollowUpQuestion(item.query)}
                    >
                      <Typography variant="body2">
                        {item.query.replace(/^(\d+[.)]|[-*•])\s*/, "")}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </Box>
            )}

            {/* Feedback Rating Buttons (Thumbs Up / Down) */}
            {!isUser && !isStreaming && msg.content && (
              <Box sx={{ mt: 1.5, display: "flex", alignItems: "center" }}>
                <FeedbackRatingButtons
                  question={userQuestion || msg.question || ""}
                  originalResponse={typeof msg.content === "string" ? msg.content : JSON.stringify(msg.content)}
                  conversationId={sessionId}
                  messageId={msg.message_id || messageIndex + 1}
                  companyId={localStorage.getItem("company_id") || localStorage.getItem("companyId")}
                  shipType={localStorage.getItem("ship_type") || localStorage.getItem("shipType")}
                  sourceMetadata={{
                    category: msg.category || msg.router_decision?.category,
                    sections: msg.sections,
                    chunks_used: msg.chunks_used,
                  }}
                  initialRating={msg.like === 1 ? "positive" : msg.like === -1 ? "negative" : null}
                />
              </Box>
            )}
          </Box>
        </Box>

        <MediaPreviewModal
          open={previewMedia.open}
          type={previewMedia.type}
          src={previewMedia.src}
          title={previewMedia.title}
          onClose={closePreview}
        />
      </Box>
    </>
  );
};

export default React.memo(ChatMessage);
