import React, { useState } from "react";
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

// ─── Normalisers ───
const normalizeVideo = (v) => ({
  title: v.title || v.Title || "",
  url: v.url || v.Url || v.videourl || "",
  thumbnail: v.thumbnail || v.Thumbnail || "",
});

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
    } catch (_) {}
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
  const openPreview = (type, src, title = "") =>
    setPreviewMedia({ open: true, type, src, title });
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

  const questionSuggestions = msg.question_suggestions || [];

  const shouldShowMedia =
    !isOutOfScope &&
    !isGreeting &&
    Boolean(msg.content && msg.content.length > 0);
  const shouldShowQuestions =
    !isOutOfScope && questionSuggestions.length > 0;


  const sanitizeDisplayContent = (content) => {
    if (!content || typeof content !== "string") return "";
    return content.replace(/^(?:#{1,6}\s*|\*{2})?(?:Out of Scope|Off Topic)(?:\*{2})?[:\s]*\n*/i, "");
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
                      sx={{
                        ...markdownContainerSx,
                        display: "block",
                      }}
                      dangerouslySetInnerHTML={{
                        __html: sanitizeMarkdown(
                          sanitizeDisplayContent(msg.content || ""),
                          skipMarkdownFormatting
                        ).replace(
                          /(?:@@SOURCE_REF_|\[\[\s*Ref:?\s*)(\d+)\s*(?:@@|\]\])/gi,
                          "",
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
                      sx={{
                        ...markdownContainerSx,
                        display: "block",
                      }}
                      dangerouslySetInnerHTML={{
                        __html: sanitizeMarkdown(msg.company_content || msg.companyContent, true),
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

            {/* All Videos (Strictly deduplicated, max 5) */}
            {!isUser && shouldShowMedia && unifiedVideos.length > 0 && (
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
            )}

            {/* PDF Suggestions */}
            {!isUser && shouldShowMedia && normalizedPdfs.length > 0 && (
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

            {/* Follow-up suggestions */}
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
                  {questionSuggestions.map((q, i) => (
                    <Box
                      key={i}
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
                      onClick={() => handleFollowUpQuestion(q)}
                    >
                      <Typography variant="body2">
                        {q.replace(/^(\d+[.)]|[-*•])\s*/, "")}
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
