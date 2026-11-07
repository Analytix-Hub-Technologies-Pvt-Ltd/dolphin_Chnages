import React, { useState, useEffect } from "react";
import {
  Drawer,
  Box,
  Typography,
  IconButton,
  Chip,
  Button,
  Tooltip,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import MenuBookIcon from "@mui/icons-material/MenuBook";
import OndemandVideoIcon from "@mui/icons-material/OndemandVideo";
import MicIcon from "@mui/icons-material/Mic";
import ImageIcon from "@mui/icons-material/Image";
import PictureAsPdfIcon from "@mui/icons-material/PictureAsPdf";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import PlayCircleOutlineIcon from "@mui/icons-material/PlayCircleOutline";
import { useThemeMode } from "../../context/ThemeModeContext";
import { APP_URL } from "../../api/config";

export default function MediaInspectorDrawer({
  open,
  onClose,
  data = null,
  onPlayVideo = null,
}) {
  const { mode } = useThemeMode();
  const isDark = mode === "dark";
  const [copiedKey, setCopiedKey] = useState("");
  const [fetchedCourse, setFetchedCourse] = useState(null);
  const [loadingCourse, setLoadingCourse] = useState(false);

  const video = data?.video || (data?.source_type || data?.video_id ? data : null);
  const rawTopicName = data?.topic_name || data?.topicName || video?.topic_name || "";
  const topicName = rawTopicName && rawTopicName !== "Course Topic" ? rawTopicName : (video?.title || "Maritime Training Curriculum");
  const topicCode = data?.topic_code || data?.topicCode || video?.topic_code || (data?.topic_codes?.[0]) || "N/A";
  
  const initialCourseCode = data?.course_code || data?.courseCode || video?.course_code || (data?.course && (data?.course.course_code || data?.course.CourseCode)) || "";
  const initialCourseName = data?.course_name || data?.courseName || video?.course_name || (data?.course && (data?.course.course_name || data?.course.CourseName)) || "";

  useEffect(() => {
    setFetchedCourse(null);
    if (!open || !topicCode || topicCode === "N/A" || topicCode === "Curriculum") {
      return;
    }
    if (initialCourseCode && initialCourseName) {
      return;
    }

    let isMounted = true;
    setLoadingCourse(true);
    fetch(`${APP_URL}/course/topic-info/${encodeURIComponent(topicCode)}`)
      .then((res) => {
        if (!res.ok) throw new Error("HTTP error " + res.status);
        return res.json();
      })
      .then((info) => {
        if (isMounted && info && (info.course_code || info.course_name)) {
          setFetchedCourse({
            code: info.course_code || "",
            name: info.course_name || "",
          });
        }
      })
      .catch((err) => {
        console.debug("Topic course info fetch failed (non-critical):", err);
      })
      .finally(() => {
        if (isMounted) setLoadingCourse(false);
      });

    return () => {
      isMounted = false;
    };
  }, [open, topicCode, initialCourseCode, initialCourseName]);

  const courseCode = initialCourseCode || fetchedCourse?.code || "";
  const courseName = initialCourseName || fetchedCourse?.name || "";

  if (!data) return null;

  const handleCopy = (text, key) => {
    if (!text) return;
    navigator.clipboard?.writeText(String(text));
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(""), 2000);
  };
  const image = data.image || null;
  const pdf = data.pdf || null;
  const sectionTitle = data.sectionTitle || "";

  const resolvedVideoId = video?.video_id || video?.id || (video?.url ? video.url.split("/").pop().split("?")[0].replace(/\.mp4$/i, "") : "N/A");
  const resolvedOriginCode = video?.topic_code || (topicCode !== "N/A" ? topicCode : "") || "Curriculum";

  const isTranscriptVector =
    video?.source_type === "transcript_vector" ||
    Boolean(video?.transcript_snippet || video?.content);

  return (
    <Drawer
      anchor="right"
      open={Boolean(open)}
      onClose={onClose}
      PaperProps={{
        sx: {
          width: { xs: "90vw", sm: 420 },
          maxWidth: 440,
          bgcolor: isDark ? "#0f172a" : "#f8fafc",
          color: isDark ? "#f1f5f9" : "#0f172a",
          borderLeft: "1px solid",
          borderColor: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)",
          boxShadow: isDark
            ? "-8px 0 32px rgba(0,0,0,0.5)"
            : "-8px 0 24px rgba(15,23,42,0.08)",
          p: 0,
          zIndex: 1400,
        },
      }}
    >
      {/* Top Header */}
      <Box
        sx={{
          p: 2.5,
          pb: 2,
          background: isDark
            ? "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)"
            : "linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 100%)",
          borderBottom: "1px solid",
          borderColor: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)",
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 1,
        }}
      >
        <Box>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
            <Chip
              label="TEST INSPECTOR"
              size="small"
              sx={{
                fontSize: "0.68rem",
                fontWeight: 800,
                letterSpacing: "0.08em",
                height: 20,
                bgcolor: isDark ? "rgba(56, 189, 248, 0.2)" : "rgba(2, 132, 199, 0.15)",
                color: isDark ? "#38bdf8" : "#0284c7",
                border: "1px solid",
                borderColor: isDark ? "rgba(56, 189, 248, 0.3)" : "rgba(2, 132, 199, 0.3)",
              }}
            />
            {sectionTitle && (
              <Chip
                label={sectionTitle}
                size="small"
                variant="outlined"
                sx={{ fontSize: "0.68rem", height: 20 }}
              />
            )}
          </Box>
          <Typography variant="h6" sx={{ fontWeight: 700, fontSize: "1.05rem", lineHeight: 1.25 }}>
            Media & Source Inspector
          </Typography>
          <Typography variant="caption" sx={{ color: isDark ? "#94a3b8" : "#64748b" }}>
            Provenance, Topic Grounding & Vector Attribution
          </Typography>
        </Box>
        <IconButton
          size="small"
          onClick={onClose}
          sx={{
            color: isDark ? "#cbd5e1" : "#475569",
            "&:hover": { bgcolor: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)" },
          }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      {/* Body Content */}
      <Box sx={{ p: 2.5, overflowY: "auto", display: "flex", flexDirection: "column", gap: 2.5 }}>
        {/* Card 1: Curriculum Topic Grounding */}
        <Box
          sx={{
            p: 2,
            borderRadius: 2,
            bgcolor: isDark ? "#1e293b" : "#ffffff",
            border: "1px solid",
            borderColor: isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)",
            boxShadow: isDark ? "0 2px 8px rgba(0,0,0,0.2)" : "0 2px 8px rgba(0,0,0,0.04)",
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5 }}>
            <MenuBookIcon sx={{ color: "#0284c7", fontSize: 20 }} />
            <Typography variant="subtitle2" sx={{ fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", fontSize: "0.75rem", color: isDark ? "#94a3b8" : "#64748b" }}>
              Curriculum Grounding
            </Typography>
          </Box>

          {/* Course Name and Course Code (Always visible in Curriculum Grounding) */}
          <Box sx={{ mb: 1.5, pb: 1.2, borderBottom: "1px dashed", borderColor: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)" }}>
            <Box sx={{ mb: 1 }}>
              <Typography variant="caption" sx={{ color: isDark ? "#64748b" : "#94a3b8", display: "block" }}>
                Course Name
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600, color: isDark ? "#f8fafc" : "#0f172a", mt: 0.2 }}>
                {courseName || (loadingCourse ? "Loading course..." : "Marine Engineering Curriculum")}
              </Typography>
            </Box>

            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <Box>
                <Typography variant="caption" sx={{ color: isDark ? "#64748b" : "#94a3b8", display: "block" }}>
                  Course Code
                </Typography>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.8, mt: 0.3 }}>
                  <Chip
                    label={courseCode || (loadingCourse ? "Loading..." : "N/A")}
                    size="small"
                    sx={{
                      fontFamily: "monospace",
                      fontWeight: 700,
                      bgcolor: isDark ? "rgba(56, 189, 248, 0.15)" : "rgba(2, 132, 199, 0.12)",
                      color: isDark ? "#38bdf8" : "#0284c7",
                      border: "1px solid",
                      borderColor: isDark ? "rgba(56, 189, 248, 0.3)" : "rgba(2, 132, 199, 0.3)",
                    }}
                  />
                </Box>
              </Box>
              {courseCode && courseCode !== "N/A" && (
                <Tooltip title={copiedKey === "course_code" ? "Copied!" : "Copy Course Code"}>
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={copiedKey === "course_code" ? <CheckCircleOutlineIcon fontSize="small" /> : <ContentCopyIcon fontSize="small" />}
                    onClick={() => handleCopy(courseCode, "course_code")}
                    sx={{
                      fontSize: "0.72rem",
                      textTransform: "none",
                      py: 0.2,
                      px: 1,
                      color: isDark ? "#38bdf8" : "#0284c7",
                      borderColor: isDark ? "rgba(56, 189, 248, 0.3)" : "rgba(2, 132, 199, 0.3)",
                      "&:hover": {
                        borderColor: isDark ? "#38bdf8" : "#0284c7",
                        bgcolor: isDark ? "rgba(56, 189, 248, 0.08)" : "rgba(2, 132, 199, 0.05)",
                      },
                    }}
                  >
                    Copy
                  </Button>
                </Tooltip>
              )}
            </Box>
          </Box>

          <Box sx={{ mb: 1.5 }}>
            <Typography variant="caption" sx={{ color: isDark ? "#64748b" : "#94a3b8", display: "block" }}>
              Topic Name
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 600, color: isDark ? "#f8fafc" : "#0f172a", mt: 0.2 }}>
              {topicName}
            </Typography>
          </Box>

          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", pt: 1, borderTop: "1px dashed", borderColor: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)" }}>
            <Box>
              <Typography variant="caption" sx={{ color: isDark ? "#64748b" : "#94a3b8", display: "block" }}>
                Topic Code
              </Typography>
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.8, mt: 0.3 }}>
                <Chip
                  label={topicCode}
                  size="small"
                  sx={{
                    fontFamily: "monospace",
                    fontWeight: 700,
                    bgcolor: isDark ? "rgba(34, 197, 94, 0.15)" : "rgba(22, 163, 74, 0.12)",
                    color: isDark ? "#4ade80" : "#16a34a",
                    border: "1px solid",
                    borderColor: isDark ? "rgba(34, 197, 94, 0.3)" : "rgba(22, 163, 74, 0.3)",
                  }}
                />
              </Box>
            </Box>
            <Tooltip title={copiedKey === "topic_code" ? "Copied!" : "Copy Topic Code"}>
              <Button
                size="small"
                variant="outlined"
                startIcon={copiedKey === "topic_code" ? <CheckCircleOutlineIcon fontSize="small" /> : <ContentCopyIcon fontSize="small" />}
                onClick={() => handleCopy(topicCode, "topic_code")}
                sx={{
                  fontSize: "0.72rem",
                  textTransform: "none",
                  py: 0.3,
                  px: 1,
                  borderColor: isDark ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.15)",
                }}
              >
                {copiedKey === "topic_code" ? "Copied" : "Copy"}
              </Button>
            </Tooltip>
          </Box>
        </Box>

        {/* Card 2: Video Provenance */}
        {video && (
          <Box
            sx={{
              p: 2,
              borderRadius: 2,
              bgcolor: isDark ? "#1e293b" : "#ffffff",
              border: "1px solid",
              borderColor: isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)",
              boxShadow: isDark ? "0 2px 8px rgba(0,0,0,0.2)" : "0 2px 8px rgba(0,0,0,0.04)",
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1.5 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                {isTranscriptVector ? (
                  <MicIcon sx={{ color: "#f59e0b", fontSize: 20 }} />
                ) : (
                  <OndemandVideoIcon sx={{ color: "#3b82f6", fontSize: 20 }} />
                )}
                <Typography variant="subtitle2" sx={{ fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", fontSize: "0.75rem", color: isDark ? "#94a3b8" : "#64748b" }}>
                  Video Provenance
                </Typography>
              </Box>
              <Chip
                label={isTranscriptVector ? "Speech Vector Match" : "Curriculum Pinned"}
                size="small"
                sx={{
                  fontSize: "0.68rem",
                  fontWeight: 700,
                  bgcolor: isTranscriptVector
                    ? isDark ? "rgba(245, 158, 11, 0.15)" : "rgba(217, 119, 6, 0.12)"
                    : isDark ? "rgba(59, 130, 246, 0.15)" : "rgba(37, 99, 235, 0.12)",
                  color: isTranscriptVector
                    ? isDark ? "#fbbf24" : "#d97706"
                    : isDark ? "#60a5fa" : "#2563eb",
                }}
              />
            </Box>

            <Box sx={{ mb: 1.5 }}>
              <Typography variant="caption" sx={{ color: isDark ? "#64748b" : "#94a3b8", display: "block" }}>
                Video Title
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600, color: isDark ? "#f8fafc" : "#0f172a", mt: 0.2 }}>
                {video.title || video.video_title || "Course Video"}
              </Typography>
            </Box>

            <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1.5, mb: 1.5 }}>
              <Box>
                <Typography variant="caption" sx={{ color: isDark ? "#64748b" : "#94a3b8", display: "block" }}>
                  Video ID
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: "0.8rem", color: isDark ? "#cbd5e1" : "#334155" }}>
                  {resolvedVideoId}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: isDark ? "#64748b" : "#94a3b8", display: "block" }}>
                  Origin Topic Code
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: "0.8rem", color: isDark ? "#cbd5e1" : "#334155" }}>
                  {resolvedOriginCode}
                </Typography>
              </Box>
            </Box>

            {/* Transcript Snippet if Vector Match */}
            {video.content && (
              <Box sx={{ p: 1.2, mb: 1.5, borderRadius: 1.5, bgcolor: isDark ? "#0f172a" : "#f1f5f9", border: "1px dashed", borderColor: isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)" }}>
                <Typography variant="caption" sx={{ color: isDark ? "#94a3b8" : "#64748b", fontStyle: "italic", display: "block", fontSize: "0.75rem" }}>
                  "{video.content.length > 140 ? `${video.content.substring(0, 140)}...` : video.content}"
                </Typography>
              </Box>
            )}

            {/* Actions */}
            <Box sx={{ display: "flex", gap: 1, pt: 1, borderTop: "1px dashed", borderColor: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)" }}>
              {video.url && onPlayVideo && (
                <Button
                  size="small"
                  variant="contained"
                  startIcon={<PlayCircleOutlineIcon fontSize="small" />}
                  onClick={() => onPlayVideo(video.url, video.title || "Course Video")}
                  sx={{ fontSize: "0.75rem", textTransform: "none", flex: 1 }}
                >
                  Play Video
                </Button>
              )}
              <Tooltip title={copiedKey === "video_id" ? "Copied!" : "Copy Video ID"}>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={copiedKey === "video_id" ? <CheckCircleOutlineIcon fontSize="small" /> : <ContentCopyIcon fontSize="small" />}
                  onClick={() => handleCopy(video.video_id || video.id || "", "video_id")}
                  sx={{ fontSize: "0.72rem", textTransform: "none" }}
                >
                  {copiedKey === "video_id" ? "Copied" : "Copy ID"}
                </Button>
              </Tooltip>
            </Box>
          </Box>
        )}

        {/* Card 3: Image Provenance */}
        {image && (
          <Box
            sx={{
              p: 2,
              borderRadius: 2,
              bgcolor: isDark ? "#1e293b" : "#ffffff",
              border: "1px solid",
              borderColor: isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)",
              boxShadow: isDark ? "0 2px 8px rgba(0,0,0,0.2)" : "0 2px 8px rgba(0,0,0,0.04)",
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5 }}>
              <ImageIcon sx={{ color: "#ec4899", fontSize: 20 }} />
              <Typography variant="subtitle2" sx={{ fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", fontSize: "0.75rem", color: isDark ? "#94a3b8" : "#64748b" }}>
                Image Diagram
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ fontWeight: 600, color: isDark ? "#f8fafc" : "#0f172a", mb: 1 }}>
              {image.title || "Topic Diagram"}
            </Typography>
            {image.url && (
              <Box
                component="img"
                src={image.url}
                alt={image.title}
                sx={{
                  width: "100%",
                  maxHeight: 140,
                  objectFit: "cover",
                  borderRadius: 1.5,
                  mb: 1,
                  border: "1px solid",
                  borderColor: isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)",
                }}
              />
            )}
          </Box>
        )}

        {/* Card 4: PDF Document */}
        {pdf && (
          <Box
            sx={{
              p: 2,
              borderRadius: 2,
              bgcolor: isDark ? "#1e293b" : "#ffffff",
              border: "1px solid",
              borderColor: isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)",
              boxShadow: isDark ? "0 2px 8px rgba(0,0,0,0.2)" : "0 2px 8px rgba(0,0,0,0.04)",
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1.5 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <PictureAsPdfIcon sx={{ color: "#ef4444", fontSize: 20 }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", fontSize: "0.75rem", color: isDark ? "#94a3b8" : "#64748b" }}>
                  {data?.type === "vector_pdf" ? "Vector Matched PDF" : "Reference Handbook"}
                </Typography>
              </Box>
              {data?.match_pct && (
                <Chip
                  label={`${data.match_pct}% Match`}
                  size="small"
                  sx={{
                    fontSize: "0.68rem",
                    fontWeight: 700,
                    bgcolor: "rgba(16,185,129,0.15)",
                    color: "#10b981",
                  }}
                />
              )}
            </Box>
            <Typography variant="body2" sx={{ fontWeight: 600, color: isDark ? "#f8fafc" : "#0f172a", mb: 0.5 }}>
              {pdf.title || "Reference Document"}
            </Typography>
            {data?.page && (
              <Typography variant="caption" sx={{ color: "primary.main", fontWeight: 700, display: "block", mb: 1 }}>
                Matched Pages: {data.page}
              </Typography>
            )}
            {data?.text_preview && (
              <Box sx={{ p: 1.2, mb: 1.5, borderRadius: 1.5, bgcolor: isDark ? "#0f172a" : "#f1f5f9", border: "1px dashed", borderColor: isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)" }}>
                <Typography variant="caption" sx={{ color: isDark ? "#94a3b8" : "#64748b", fontStyle: "italic", display: "block", fontSize: "0.75rem" }}>
                  "{data.text_preview.length > 250 ? `${data.text_preview.substring(0, 250)}...` : data.text_preview}"
                </Typography>
              </Box>
            )}
            {pdf.link && (
              <Button
                size="small"
                variant="outlined"
                component="a"
                href={pdf.link}
                target="_blank"
                rel="noreferrer"
                endIcon={<OpenInNewIcon fontSize="small" />}
                sx={{ fontSize: "0.75rem", textTransform: "none" }}
              >
                Open Document
              </Button>
            )}
          </Box>
        )}
      </Box>
    </Drawer>
  );
}

