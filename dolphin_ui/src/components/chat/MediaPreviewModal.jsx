import { useEffect, useRef, useState } from "react";
import { X, Maximize, Minimize } from "lucide-react";
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

  if (!open) return null;

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs transition-opacity duration-200 ${
        isFullscreen ? "p-0" : "p-4"
      }`}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={`relative bg-black select-none overflow-hidden transition-all duration-200 ${
          isFullscreen
            ? "w-screen h-screen max-w-none rounded-none"
            : "w-full max-w-3xl rounded-xl shadow-2xl"
        }`}
      >
        {/* Top Right Controls */}
        <div className="absolute top-2.5 right-2.5 z-20 flex items-center gap-1.5">
          {(type === "image" || type === "pdf") && (
            <button
              type="button"
              onClick={toggleFullscreen}
              aria-label={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
              className="p-1.5 rounded-full bg-black/70 hover:bg-black/95 text-white/85 hover:text-white transition-colors cursor-pointer"
            >
              {isFullscreen ? <Minimize className="w-5 h-5" /> : <Maximize className="w-5 h-5" />}
            </button>
          )}

          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="p-1.5 rounded-full bg-black/70 hover:bg-black/95 text-white/85 hover:text-white transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Area */}
        <div
          className={`p-0 w-full ${
            isFullscreen ? "h-screen" : "h-[500px]"
          } ${
            isFullscreen && (type === "pdf" || type === "image")
              ? "overflow-auto"
              : "overflow-hidden"
          }`}
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
              className="w-full h-full object-contain"
            />
          )}

          {/* 🖼 IMAGE */}
          {type === "image" && (
            <img
              src={src}
              alt="Preview"
              className={`w-full ${
                isFullscreen ? "h-auto" : "h-full"
              } max-h-full object-contain`}
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
        </div>
      </div>
    </div>
  );
};

export default MediaPreviewModal;
