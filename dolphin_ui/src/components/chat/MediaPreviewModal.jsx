import { Dialog, DialogContent, IconButton, Box, Stack } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import FullscreenIcon from "@mui/icons-material/Fullscreen";
import FullscreenExitIcon from "@mui/icons-material/FullscreenExit";
import { useEffect, useRef, useState } from "react";
import SecurePdfViewer from "./SecurePdfViewer";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

import { pdfjs } from "react-pdf";

pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

const BLOCKED_KEYS = ["Escape", "F12", "PrintScreen"];

const MediaPreviewModal = ({ open, onClose, type, src }) => {
  const videoRef = useRef(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

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

  /* ⏹ Stop video on close */
  useEffect(() => {
    if (!open && videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = 0;
    }
  }, [open]);

  const toggleFullscreen = () => setIsFullscreen((p) => !p);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullScreen={isFullscreen}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          backgroundColor: "black",
          userSelect: "none",
          overflow: "hidden", // 🚫 no scroll in modal
        },
      }}
    >
      {/* Top Right Controls */}
      <Stack
        direction="row"
        spacing={1}
        sx={{
          position: "absolute",
          top: 8,
          right: 8,
          zIndex: 10,
        }}
      >
        {(type === "image" || type === "pdf") && (
          <IconButton
            onClick={toggleFullscreen}
            sx={{
              bgcolor: "black",
              color: "white",
              "&:hover": {
                bgcolor: "black",
              },
            }}
          >
            {isFullscreen ? <FullscreenExitIcon /> : <FullscreenIcon />}
          </IconButton>
        )}

        <IconButton
          onClick={onClose}
          sx={{
            bgcolor: "black",
            color: "white",
            "&:hover": {
              bgcolor: "black",
            },
          }}
        >
          <CloseIcon />
        </IconButton>
      </Stack>

      <DialogContent
        sx={{
          p: 0,
          height: isFullscreen ? "100vh" : 500,
          overflow:
            isFullscreen && (type === "pdf" || type === "image")
              ? "auto"
              : "hidden",
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
