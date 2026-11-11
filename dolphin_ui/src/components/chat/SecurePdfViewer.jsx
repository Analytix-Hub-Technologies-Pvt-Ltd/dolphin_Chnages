import { Box, Typography, CircularProgress, Button } from "@mui/material";
import { useRef, useState, useEffect } from "react";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import { resolveImageUrl } from "../../api/config";

const SecurePdfViewer = ({ src, title = "PDF Document" }) => {
  const containerRef = useRef(null);
  const [loading, setLoading] = useState(Boolean(src));
  const [loadTimeout, setLoadTimeout] = useState(false);

  // Resolve full valid URL and append parameters to hide toolbar, download button, and navpanes
  const resolved = resolveImageUrl(src) || src || "";
  const [baseAndQuery, hash] = resolved.split("#");
  const hashAnchor = hash ? `#${hash}&` : "#";
  const pdfUrl = baseAndQuery ? `${baseAndQuery}${hashAnchor}toolbar=0&navpanes=0&scrollbar=0` : "";

  useEffect(() => {
    setLoading(Boolean(pdfUrl));
    setLoadTimeout(false);

    if (!pdfUrl) return;

    // After 15 seconds of buffering, show helper control so user is never stuck
    const timer = setTimeout(() => {
      setLoadTimeout(true);
    }, 15000);

    return () => clearTimeout(timer);
  }, [pdfUrl]);

  const handleIframeLoad = () => {
    setLoading(false);
  };

  const handleOpenExternal = () => {
    if (resolved) {
      window.open(resolved, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <Box
      ref={containerRef}
      sx={{
        width: "100%",
        height: "100%",
        backgroundColor: "#0f172a",
        overflow: "hidden",
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
      onContextMenu={(e) => e.preventDefault()}
    >
      {/* Loading Overlay */}
      {loading && pdfUrl && (
        <Box
          sx={{
            position: "absolute",
            inset: 0,
            zIndex: 10,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "#0f172a",
            px: 3,
            textAlign: "center",
          }}
        >
          <CircularProgress size={42} thickness={4} sx={{ color: "#38bdf8", mb: 2.5 }} />
          <Typography variant="body1" sx={{ color: "#f8fafc", fontWeight: 600, mb: 0.5 }}>
            Loading PDF Document
          </Typography>
          <Typography variant="caption" sx={{ color: "#94a3b8", maxWidth: 380, mb: 2 }}>
            Large technical manuals and high-resolution diagrams may take a few moments to buffer.
          </Typography>

          {loadTimeout && resolved && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<OpenInNewIcon sx={{ fontSize: 16 }} />}
              onClick={handleOpenExternal}
              sx={{
                color: "#38bdf8",
                borderColor: "rgba(56, 189, 248, 0.4)",
                textTransform: "none",
                fontSize: "0.8rem",
                "&:hover": { borderColor: "#38bdf8", backgroundColor: "rgba(56, 189, 248, 0.08)" },
              }}
            >
              Open in New Window
            </Button>
          )}
        </Box>
      )}

      {/* No URL Fallback */}
      {!pdfUrl && (
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            color: "#94a3b8",
            p: 3,
            textAlign: "center",
          }}
        >
          <Typography variant="h6" sx={{ color: "#f8fafc", mb: 1 }}>
            Preview Not Available
          </Typography>
          <Typography variant="body2" sx={{ maxWidth: 400 }}>
            This reference document does not have a direct online URL attached in the knowledge base.
          </Typography>
        </Box>
      )}

      {/* Embedded PDF Iframe */}
      {pdfUrl && (
        <iframe
          src={pdfUrl}
          title={title || "PDF Viewer"}
          width="100%"
          height="100%"
          allow="fullscreen"
          onLoad={handleIframeLoad}
          style={{
            border: "none",
            width: "100%",
            height: "100%",
            display: "block",
            opacity: loading ? 0 : 1,
            transition: "opacity 0.25s ease-in-out",
          }}
        />
      )}
    </Box>
  );
};

export default SecurePdfViewer;
