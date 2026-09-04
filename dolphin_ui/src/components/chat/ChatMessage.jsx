import React, { useState, useMemo } from "react";
import { Box, Typography, Avatar, Tooltip, IconButton } from "@mui/material";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";
import DownloadIcon from "@mui/icons-material/Download";
import QuizDisplay from "./QuizDisplay";
import { sanitizeMarkdown } from "./ChatWindow";
import DolphinIconW from "../../assets/images/dolphin_w.png";
import { useThemeMode } from "../../context/ThemeModeContext";
import { VideoIcon } from "../../assets/svgIcons/VideoIcon";
import { ImageIcon } from "../../assets/svgIcons/ImageIcon";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import { DocumentIcon } from "../../assets/svgIcons/DocumentIcon";
import MediaPreviewModal from "./MediaPreviewModal";
const exportMarkdownToWordDoc = (markdownText, filename = "document.doc") => {
  const htmlBody = sanitizeMarkdown(markdownText);

  const wordDocumentHtml = `
    <html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'>
    <head>
      <meta charset="utf-8">
      <title>${filename.replace(/\.[^/.]+$/, "")}</title>
      <!--[if gte mso 9]>
      <xml>
        <w:WordDocument>
          <w:View>Print</w:View>
          <w:Zoom>100</w:Zoom>
          <w:DoNotOptimizeForBrowser/>
        </w:WordDocument>
      </xml>
      <![endif]-->
      <style>
        @page Section1 {
          size: 8.5in 11.0in;
          margin: 1.0in 1.0in 1.0in 1.0in;
          mso-header-margin: 0.5in;
          mso-footer-margin: 0.5in;
          mso-paper-source: 0;
        }
        div.Section1 {
          page: Section1;
        }
        body {
          font-family: 'Calibri', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
          font-size: 11pt;
          line-height: 1.5;
          color: #222222;
        }
        h1 {
          font-size: 18pt;
          font-weight: bold;
          color: #1A365D;
          margin-top: 18pt;
          margin-bottom: 6pt;
          border-bottom: 2px solid #1A365D;
          padding-bottom: 4pt;
        }
        h2 {
          font-size: 14pt;
          font-weight: bold;
          color: #2B6CB0;
          margin-top: 14pt;
          margin-bottom: 4pt;
        }
        h3 {
          font-size: 12pt;
          font-weight: bold;
          color: #2D3748;
          margin-top: 10pt;
          margin-bottom: 3pt;
        }
        h4 {
          font-size: 11pt;
          font-weight: bold;
          color: #4A5568;
          margin-top: 8pt;
          margin-bottom: 2pt;
        }
        p {
          margin-top: 0;
          margin-bottom: 8pt;
        }
        ul, ol {
          margin-top: 0;
          margin-bottom: 8pt;
          padding-left: 24pt;
        }
        li {
          margin-bottom: 4pt;
        }
        table {
          border-collapse: collapse;
          width: 100%;
          margin-top: 10pt;
          margin-bottom: 12pt;
        }
        th, td {
          border: 1px solid #CBD5E0;
          padding: 6pt 8pt;
          text-align: left;
          font-size: 10pt;
        }
        th {
          background-color: #EDF2F7;
          font-weight: bold;
          color: #2D3748;
        }
        blockquote {
          border-left: 3pt solid #3182CE;
          margin: 8pt 0;
          padding-left: 12pt;
          color: #4A5568;
          font-style: italic;
        }
        code {
          font-family: 'Consolas', 'Courier New', monospace;
          background-color: #F7FAFC;
          padding: 2pt 4pt;
          font-size: 9.5pt;
        }
        pre {
          background-color: #F7FAFC;
          border: 1px solid #E2E8F0;
          padding: 8pt;
          font-family: 'Consolas', 'Courier New', monospace;
          font-size: 9.5pt;
          margin-bottom: 8pt;
        }
      </style>
    </head>
    <body>
      <div class="Section1">
        ${htmlBody}
      </div>
    </body>
    </html>
  `;

  const blob = new Blob(['\ufeff', wordDocumentHtml], {
    type: 'application/msword;charset=utf-8'
  });

  const downloadUrl = URL.createObjectURL(blob);
  const downloadLink = document.createElement('a');
  downloadLink.href = downloadUrl;
  downloadLink.download = filename;
  document.body.appendChild(downloadLink);
  downloadLink.click();
  document.body.removeChild(downloadLink);
  URL.revokeObjectURL(downloadUrl);
};

const ChatMessage = ({
  msg,
  videos_suggestions,
  images_suggestions,
  pdf_suggestions,
  sessionId,
  setSearchQuery,
  handleSend,
}) => {
  const [showAllVideos, setShowAllVideos] = useState(false);
  const [showAllImages, setShowAllImages] = useState(false);
  const [showAllPdfs, setShowAllPdfs] = useState(false);
  const [docError, setDocError] = useState("");
  const isUser = msg.role === "user";
  const { mode } = useThemeMode();
  const [previewMedia, setPreviewMedia] = useState({
    open: false,
    type: null,
    src: null,
  });

  const openPreview = (type, src) => {
    setPreviewMedia({ open: true, type, src });
  };

  const closePreview = () => {
    setPreviewMedia({ open: false, type: null, src: null });
  };

  const validImages = useMemo(() => {
    if (!images_suggestions || !Array.isArray(images_suggestions)) return [];
    const seen = new Set();
    const result = [];
    for (const img of images_suggestions) {
      if (!img) continue;
      const b64 = img.base64 && typeof img.base64 === "string" && img.base64.startsWith("data:image/") ? img.base64 : "";
      const directUrl = img.url || img.Url || img.thumbnail || img.Thumbnail || "";
      const imgSrc = b64 || directUrl || "";
      if (!imgSrc) continue;

      const rawId = String(img.id || img.Id || "").trim().toLowerCase();
      const rawTitle = String(img.title || img.Title || img.name || img.Name || "Reference Image").trim();
      const cleanTitle = rawTitle.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
      const uuidMatch = (rawId + " " + directUrl).match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
      const uuid = uuidMatch ? uuidMatch[0].toLowerCase() : rawId;

      const dedupeKey = uuid || cleanTitle || directUrl;
      if (dedupeKey && seen.has(dedupeKey)) continue;
      if (cleanTitle && cleanTitle.length > 3 && seen.has(`title:${cleanTitle}`)) continue;

      if (dedupeKey) seen.add(dedupeKey);
      if (cleanTitle && cleanTitle.length > 3) seen.add(`title:${cleanTitle}`);

      result.push({
        ...img,
        imgSrc,
        imgTitle: rawTitle,
        b64,
      });
    }
    return result;
  }, [images_suggestions]);

  const handleFollowUpQuestion = async (query) => {
    setSearchQuery(query);
    await handleSend(query);
  };

  const isGapAnalysis = msg.metadata?.category === "GAP_ANALYSIS" || (msg.sections && msg.sections[0] && msg.sections[0].topic_code === "GAP_ANALYSIS");
  const showDownloadButton = isGapAnalysis && !msg.isThinking;
  const isOutOfScope =
    msg.metadata?.category === "OUT_OF_SCOPE" ||
    msg.metadata?.routing_reason === "out_of_scope" ||
    (typeof msg.content === "string" && msg.content.includes("This is not part of the available course material"));

  const handleDownloadWordDoc = () => {
    try {
      setDocError("");

      let documentName = "";
      if (msg.sections && msg.sections[0] && msg.sections[0].topic_name) {
        const topicName = msg.sections[0].topic_name;
        if (topicName.startsWith("Gap Analysis - ")) {
          documentName = topicName.replace("Gap Analysis - ", "");
        }
      }

      const today = new Date();
      const YYYY = today.getFullYear();
      const MM = String(today.getMonth() + 1).padStart(2, "0");
      const DD = String(today.getDate()).padStart(2, "0");
      const todayStr = `${YYYY}-${MM}-${DD}`;

      let filename = "";
      if (documentName) {
        const safeDocName = documentName.replace(/\.[^/.]+$/, "");
        filename = `${safeDocName}_Gap_Analysis_${todayStr}.doc`;
      } else {
        filename = `Marine_Gap_Analysis_${todayStr}.doc`;
      }

      exportMarkdownToWordDoc(msg.content, filename);
    } catch (err) {
      console.error("Word Doc generation failed:", err);
      setDocError("Unable to generate Word document. Please try again.");
    }
  };

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "flex-start",
        gap: 1,
        flexDirection: isUser ? "row-reverse" : "row",
      }}
    >
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

      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          width: isUser ? "auto" : "90%",
          maxWidth: "90%",
          gap: 1,
        }}
      >
        {isUser ? (
          <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
            <Typography
              variant="h4"
              sx={{ fontWeight: 700, color: "text.heading1" }}
            >
              You
            </Typography>{" "}
            <Typography variant="caption" sx={{ color: "text.caption" }}>
              {new Date(msg?.timestamp).toLocaleTimeString("en-US", {
                hour: "numeric",
                minute: "2-digit",
                hour12: true,
              })}
            </Typography>
          </Box>
        ) : (
          <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
            <Typography
              variant="body1"
              sx={{ fontWeight: 700, color: "text.heading1" }}
            >
              Dolphin AI
            </Typography>
            {/* <Typography
              variant="body1"
              sx={{ fontWeight: 700, color: "text.heading1" }}
            >
              |
            </Typography>
            <Typography
              variant="body1"
              sx={{fontWeight: 700, color: "primary.main" }}
            >
              AI
            </Typography> */}
            <Typography variant="caption" sx={{ color: "text.caption" }}>
              {new Date(msg?.timestamp).toLocaleTimeString("en-US", {
                hour: "numeric",
                minute: "2-digit",
                hour12: true,
              })}
            </Typography>
          </Box>
        )}

        <Box
          sx={{
            bgcolor: isUser ? "background.light" : "background.chatbackground",
            p: 2,
            borderRadius: 5,
            whiteSpace: isUser ? "pre-wrap" : "normal",
            overflowX: "auto",
          }}
        >
          {isUser ? (
            <Typography variant="body1" sx={{ color: "text.secondary" }}>
              {msg.content}
            </Typography>
          ) : msg.category !== "QUIZ" ? (
            <div style={{ display: "flex", flexDirection: "column" }}>
              <div
                dangerouslySetInnerHTML={{
                  __html: sanitizeMarkdown(msg.content),
                }}
              />
              {showDownloadButton && (
                <Box
                  sx={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-end",
                    mt: 2,
                    pt: 1,
                    borderTop: "1px solid",
                    borderColor: mode === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.06)",
                  }}
                >
                  <Tooltip title="Download Word Document">
                    <IconButton
                      onClick={handleDownloadWordDoc}
                      size="small"
                      sx={{
                        color: "primary.main",
                        border: "1px solid",
                        borderColor: "primary.main",
                        borderRadius: "4px",
                        padding: "4px 8px",
                        fontSize: "0.8rem",
                        display: "flex",
                        alignItems: "center",
                        gap: 0.5,
                        textTransform: "none",
                        "&:hover": {
                          backgroundColor: "rgba(28, 176, 246, 0.08)",
                        },
                      }}
                    >
                      <DownloadIcon fontSize="small" />
                      <span>Download Word Doc</span>
                    </IconButton>
                  </Tooltip>
                  {docError && (
                    <Typography
                      variant="caption"
                      sx={{ color: "error.main", mt: 0.5 }}
                    >
                      {docError}
                    </Typography>
                  )}
                </Box>
              )}
            </div>
          ) : (
            <QuizDisplay quizContet={msg.content} />
          )}

          {videos_suggestions?.length > 0 && !isOutOfScope && (
            <Box sx={{ mt: 2 }}>
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 0.5,
                }}
              >
                <VideoIcon
                  size={30}
                  color={mode === "dark" ? "#e8f1fb" : "#0f1c2e"}
                />
                <Typography variant="h3" sx={{ color: "text.primary" }}>
                  Video Suggestions
                </Typography>
              </Box>

              <Box
                sx={{
                  display: "flex",
                  gap: 2,
                  flexWrap: "wrap",
                  maxHeight: showAllVideos ? "none" : { xs: 150, sm: 180 },
                  overflow: "hidden",
                  py: 1,
                }}
              >
                {videos_suggestions.map((video, i) => {
                  const videoUrl = video.url || video.Url || "";
                  const videoThumb = video.thumbnail || video.Thumbnail || video.thumbnail_url || "";
                  const videoTitle = video.title || video.Title || video.About || "Video";

                  return (
                    <Box
                      key={i}
                      sx={{
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
                        border: "1px solid",
                        borderColor: "text.caption",
                        cursor: "pointer",
                        "&:hover": {
                          borderColor: "primary.main",
                          transform: "translateY(-2px)",
                        },
                      }}
                      onClick={() => openPreview("video", videoUrl)}
                    >
                      <Box
                        component="img"
                        src={videoThumb}
                        alt={videoTitle}
                        sx={{
                          width: "100%",
                          height: { xs: 80, sm: 130 },
                          borderRadius: 1,
                          objectFit: "cover",
                        }}
                      />
                      <Box
                        sx={{
                          position: "absolute",
                          inset: 0,
                          display: "flex",
                          alignItems: "center",
                          left: 10,
                          bottom: -50,
                        }}
                      >
                        <PlayArrowRoundedIcon
                          sx={{
                            color: "background.default",
                            fontSize: 30,
                            "&:hover": {
                              borderColor: "primary.main",
                              fontSize: 32,
                            },
                          }}
                        />
                      </Box>
                      <Typography
                        variant="caption"
                        sx={{
                          width: "100%",
                          textAlign: "center",
                          color: "primary.main",
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {videoTitle}
                      </Typography>
                    </Box>
                  );
                })}
              </Box>

              {videos_suggestions.length > 4 && (
                <Typography
                  onClick={() => setShowAllVideos((prev) => !prev)}
                  variant="body1"
                  sx={{
                    mt: 1,
                    cursor: "pointer",
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    color: "text.primary",
                  }}
                >
                  {showAllVideos ? "Show less" : "Show more"}
                  {showAllVideos ? (
                    <KeyboardArrowUpIcon />
                  ) : (
                    <KeyboardArrowDownIcon />
                  )}
                </Typography>
              )}
            </Box>
          )}

          {validImages?.length > 0 && !isOutOfScope && (
            <Box className="ref-images-section" sx={{ mt: 2 }}>
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 0.5,
                }}
              >
                <ImageIcon
                  size={24}
                  color={mode === "dark" ? "#e8f1fb" : "#0f1c2e"}
                />
                <Typography variant="h3" sx={{ color: "text.primary" }}>
                  Reference Images
                </Typography>
              </Box>

              <Box
                className="ref-images-container"
                sx={{
                  display: "flex",
                  gap: 2,
                  flexWrap: "wrap",
                  maxHeight: showAllImages ? "none" : { xs: 150, sm: 180 },
                  overflow: "hidden",
                  py: 1,
                }}
              >
                {validImages.map((img, i) => (
                  <Box
                    key={img.id || i}
                    className="ref-image-item"
                    sx={{
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
                      border: "1px solid",
                      borderColor: "text.caption",
                      cursor: "pointer",
                      "&:hover": {
                        borderColor: "primary.main",
                        transform: "translateY(-2px)",
                      },
                    }}
                    onClick={() => openPreview("image", img.imgSrc)}
                  >
                    <Box
                      component="img"
                      src={img.imgSrc}
                      alt={img.imgTitle}
                      onError={(e) => {
                        if (img.b64 && e.target.src !== img.b64) {
                          e.target.src = img.b64;
                        } else {
                          const card = e.currentTarget.closest(".ref-image-item") || e.currentTarget.parentElement;
                          if (card) {
                            card.style.display = "none";
                            const container = card.parentElement;
                            if (container) {
                              const remaining = Array.from(container.querySelectorAll(".ref-image-item")).filter(
                                (el) => el.style.display !== "none"
                              );
                              if (remaining.length === 0) {
                                const section = container.closest(".ref-images-section") || container.parentElement;
                                if (section) section.style.display = "none";
                              }
                            }
                          }
                        }
                      }}
                      sx={{
                        width: "100%",
                        height: { xs: 80, sm: 130 },
                        borderRadius: 1,
                        objectFit: "cover",
                      }}
                    />

                    <Typography
                      variant="caption"
                      sx={{
                        width: "100%",
                        textAlign: "center",
                        color: "primary.main",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {img.imgTitle}
                    </Typography>
                  </Box>
                ))}
              </Box>

              {validImages.length > 4 && (
                <Typography
                  onClick={() => setShowAllImages((prev) => !prev)}
                  variant="body1"
                  sx={{
                    mt: 1,
                    cursor: "pointer",
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    color: "text.primary",
                  }}
                >
                  {showAllImages ? "Show less" : "Show more"}
                  {showAllImages ? (
                    <KeyboardArrowUpIcon />
                  ) : (
                    <KeyboardArrowDownIcon />
                  )}
                </Typography>
              )}
            </Box>
          )}

          {pdf_suggestions?.length > 0 && !isOutOfScope && (
            <Box sx={{ mt: 2 }}>
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 0.5,
                }}
              >
                <DocumentIcon
                  size={25}
                  color={mode === "dark" ? "#e8f1fb" : "#0f1c2e"}
                />
                <Typography variant="h3" sx={{ color: "text.primary" }}>
                  Reference PDFs
                </Typography>
              </Box>

              <Box
                sx={{
                  display: "flex",
                  gap: 2,
                  flexWrap: "wrap",
                  maxHeight: showAllPdfs ? "none" : { xs: 150, sm: 180 },
                  overflow: "hidden",
                  py: 1,
                }}
              >
                {pdf_suggestions.map((pdf, i) => {
                  const pdfUrl = pdf.url || pdf.Url || pdf.link || pdf.Link || pdf.file_url || "";
                  const pdfTitle = pdf.title || pdf.Title || pdf.name || pdf.Name || "Reference PDF";
                  return (
                    <Box
                      key={i}
                      sx={{
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
                        border: "1px solid",
                        borderColor: "text.caption",
                        cursor: "pointer",
                        "&:hover": {
                          borderColor: "primary.main",
                          transform: "translateY(-2px)",
                        },
                      }}
                      onClick={() => openPreview("pdf", pdfUrl)}
                    >
                      {/* PDF Thumbnail */}
                      <Box
                        sx={{
                          width: "100%",
                          height: { xs: 80, sm: 130 },
                          borderRadius: 1,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          backgroundColor: "background.paper",
                          fontSize: 32,
                        }}
                      >
                        📄
                      </Box>

                      {/* Title */}
                      <Typography
                        variant="caption"
                        sx={{
                          width: "100%",
                          textAlign: "center",
                          color: "primary.main",
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {pdfTitle}
                      </Typography>
                    </Box>
                  );
                })}
              </Box>

              {pdf_suggestions.length > 4 && (
                <Typography
                  onClick={() => setShowAllPdfs((prev) => !prev)}
                  variant="body1"
                  sx={{
                    mt: 1,
                    cursor: "pointer",
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    color: "text.primary",
                  }}
                >
                  {showAllPdfs ? "Show less" : "Show more"}
                  {showAllPdfs ? (
                    <KeyboardArrowUpIcon />
                  ) : (
                    <KeyboardArrowDownIcon />
                  )}
                </Typography>
              )}
            </Box>
          )}

          {msg.question_suggestions?.length > 0 && (
            <Box
              sx={{ mt: 2, display: "flex", flexDirection: "column", gap: 1 }}
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
                {" "}
                {msg.question_suggestions.map((q, i) => (
                  <Box
                    key={i}
                    sx={(theme) => ({
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      width: "auto",
                      p: 1,
                      borderRadius: 3,
                      backgroundColor: "background.light",
                      cursor: "pointer",
                      transition: "all 0.2s ease",

                      "&:hover": {
                        border: "1.5px solid",
                        borderColor: theme.palette.primary.main,
                        color: theme.palette.primary.main,
                      },
                    })}
                    onClick={() => {
                      handleFollowUpQuestion(q);
                    }}
                  >
                    <Typography variant="body2">{q}</Typography>
                  </Box>
                ))}
              </Box>
            </Box>
          )}
        </Box>
      </Box>
      <MediaPreviewModal
        open={previewMedia.open}
        type={previewMedia.type}
        src={previewMedia.src}
        onClose={closePreview}
      />
    </Box>
  );
};

export default React.memo(ChatMessage);
