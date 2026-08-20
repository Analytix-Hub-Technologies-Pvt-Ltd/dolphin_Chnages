import React, { useState } from "react";
import { Box, Typography, Avatar } from "@mui/material";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";
import QuizDisplay from "./QuizDisplay";
import { sanitizeMarkdown } from "./ChatWindow";
import DolphinIconW from "../../assets/images/dolphin_w.png";
import { useThemeMode } from "../../context/ThemeModeContext";
import { VideoIcon } from "../../assets/svgIcons/VideoIcon";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import { DocumentIcon } from "../../assets/svgIcons/DocumentIcon";
import MediaPreviewModal from "./MediaPreviewModal";

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
  const [showAllPdfs, setShowAllPdfs] = useState(false);
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

  const handleFollowUpQuestion = async (query) => {
    setSearchQuery(query);
    await handleSend(query);
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
            <div
              style={{ display: "flex", flexDirection: "column" }}
              dangerouslySetInnerHTML={{
                __html: sanitizeMarkdown(msg.content),
              }}
            />
          ) : (
            <QuizDisplay quizContet={msg.content} />
          )}

          {videos_suggestions?.length > 0 && (
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

          {/* {images_suggestions?.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 0.5,
                }}
              >
                <ImageIcon
                  size={24}
                  color={mode == "dark" ? "#e8f1fb" : "#0f1c2e"}
                />
                <Typography variant="h3" sx={{ color: "text.primary" }}>
                  Reference Images
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
                {images_suggestions.map((img, i) => (
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
                      "&:hover": {
                        borderColor: "primary.main",
                        transform: "translateY(-2px)",
                      },
                    }}
                      onClick={() => openPreview("image", img.Url)}
                  >
                    <Box
                      component="img"
                      src={img.thumbnail || img.Url}
                      alt={img.Title || "image"}
                      sx={{
                        width: "100%",
                        height: 130,
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
                      {img.Title || "Reference Image"}
                    </Typography>
                  </Box>
                ))}
              </Box>

              {images_suggestions.length > 4 && (
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
          )} */}

          {pdf_suggestions?.length > 0 && (
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
                {pdf_suggestions.map((pdf, i) => (
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
                      "&:hover": {
                        borderColor: "primary.main",
                        transform: "translateY(-2px)",
                      },
                    }}
                    onClick={() => openPreview("pdf", pdf.Link)}
                  >
                    {/* PDF Thumbnail */}
                    <Box
                      sx={{
                        width: "100%",
                        height: 130,
                        borderRadius: 1,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        backgroundColor: "background.paper",
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
                      {pdf?.Title || "Reference PDF"}
                    </Typography>
                  </Box>
                ))}
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
