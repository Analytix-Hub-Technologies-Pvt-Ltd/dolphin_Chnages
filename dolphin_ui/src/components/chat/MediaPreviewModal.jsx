import { Dialog, DialogContent, IconButton, Box, Stack } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import FullscreenIcon from "@mui/icons-material/Fullscreen";
import FullscreenExitIcon from "@mui/icons-material/FullscreenExit";
import { useEffect, useRef, useState } from "react";
import SecurePdfViewer from "./SecurePdfViewer";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

import { pdfjs } from "react-pdf";

pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const BLOCKED_KEYS = ["Escape", "F12", "PrintScreen"];

const MediaPreviewModal = ({ open, onClose, type, src, title }) => {
  const videoRef = useRef(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const isPdf = type === "pdf";

  /* 🔐 Security handlers */
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e) => {
      if (
        BLOCKED_KEYS.includes(e.key) ||
        e.ctrlKey ||
        e.metaKey ||
        e.shiftKey
      ) {
        e.preventDefault();
        onClose();
      }
    };

    const handleVisibilityChange = () => {
      if (document.hidden) onClose();
    };

    const handleContextMenu = (e) => {
      e.preventDefault();
      onClose();
    };

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    document.addEventListener("contextmenu", handleContextMenu);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      document.removeEventListener("contextmenu", handleContextMenu);
    };
  }, [open, onClose]);

  /* ⏹ Stop video & reset fullscreen on close */
  useEffect(() => {
    if (!open) {
      if (videoRef.current) {
        videoRef.current.pause();
        videoRef.current.currentTime = 0;
      }
      setIsFullscreen(false);
    }
  }, [open]);

  const toggleFullscreen = () => setIsFullscreen((p) => !p);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullScreen={isFullscreen}
      maxWidth={isFullscreen ? false : "md"}
      fullWidth
      PaperProps={{
        sx: {
          backgroundColor: "black",
          userSelect: "none",
          overflow: "hidden", // 🚫 no scroll in modal
          position: "relative",
          ...(isFullscreen && {
            width: "100vw",
            height: "100vh",
            maxWidth: "100vw",
            maxHeight: "100vh",
            m: 0,
            borderRadius: 0,
          }),
        },
      }}
    >
      {/* Top Right Controls */}
      <Stack
        direction="row"
        spacing={1.5}
        alignItems="center"
        sx={{
          position: "absolute",
          top: 12,
          right: 16,
          zIndex: 1400,
        }}
      >
        {title && (
          <Box
            sx={{
              color: "rgba(255,255,255,0.9)",
              backgroundColor: "rgba(0,0,0,0.65)",
              backdropFilter: "blur(6px)",
              px: 1.5,
              py: 0.6,
              borderRadius: "6px",
              maxWidth: { xs: "40vw", sm: "50vw" },
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              fontSize: "0.85rem",
              fontWeight: 500,
              border: "1px solid rgba(255,255,255,0.15)",
            }}
            title={title}
          >
            {title}
          </Box>
        )}

        {(type === "image" || type === "pdf" || type === "video") && (
          <IconButton
            onClick={toggleFullscreen}
            sx={{
              bgcolor: "rgba(0,0,0,0.65)",
              color: "white",
              "&:hover": {
                bgcolor: "black",
              },
              boxShadow: "0 2px 8px rgba(0,0,0,0.5)",
            }}
            title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
          >
            {isFullscreen ? <FullscreenExitIcon /> : <FullscreenIcon />}
          </IconButton>
        )}

        <IconButton
          onClick={onClose}
          sx={{
            bgcolor: "rgba(0,0,0,0.65)",
            color: "white",
            "&:hover": {
              bgcolor: "black",
            },
            boxShadow: "0 2px 8px rgba(0,0,0,0.5)",
          }}
          title="Close"
        >
          <CloseIcon />
        </IconButton>
      </Stack>

      <DialogContent
        sx={{
          p: 0,
          height: isFullscreen ? "100vh" : { xs: 450, sm: 550 },
          width: "100%",
          overflow:
            isPdf
              ? "hidden"
              : isFullscreen && type === "image"
              ? "auto"
              : "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* 🎥 VIDEO */}
        {type === "video" && (
          <video
            ref={videoRef}
            src={src}
            autoPlay
            controls
            controlsList="nodownload noplaybackrate"
            disablePictureInPicture
            style={{
              width: "100%",
              height: "100%",
              objectFit: "contain", // ✅ handles all aspect ratios
            }}
          />
        )}

        {/* 🖼 IMAGE */}
        {type === "image" && (
          <Box
            component="img"
            src={src}
            alt="Preview"
            sx={{
              width: "100%",
              height: isFullscreen ? "auto" : "100%",
              maxHeight: "100%",
              objectFit: "contain",
            }}
          />
        )}

        {/* 📄 PDF */}
        {type === "pdf" && (
          <SecurePdfViewer
            src={src}
            isFullscreen={isFullscreen}
            onClose={onClose}
          />
        )}
      </DialogContent>
    </Dialog>
  );
};

export default MediaPreviewModal;
