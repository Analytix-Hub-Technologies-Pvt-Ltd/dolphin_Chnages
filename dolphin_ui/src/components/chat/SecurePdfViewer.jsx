import { Box } from "@mui/material";
import { useEffect, useRef } from "react";

const SecurePdfViewer = ({ src, isFullscreen }) => {
  const containerRef = useRef(null);
  const pdfUrl = `${src}#toolbar=0&navpanes=0&scrollbar=0`;

  // Handle fullscreen properly
  useEffect(() => {
    if (isFullscreen && containerRef.current) {
      containerRef.current.requestFullscreen?.();
    } else {
      document.fullscreenElement && document.exitFullscreen?.();
    }
  }, [isFullscreen]);

  return (
    <Box
      ref={containerRef}
      sx={{
        width: "100%",
        height: isFullscreen ? "100vh" : 500,
        backgroundColor: "black",
      }}
    >
      <iframe
        src={pdfUrl}
        title="PDF Viewer"
        width="100%"
        height="100%"
        allow="fullscreen"
        style={{ border: "none" }}
      />
    </Box>
  );
};

export default SecurePdfViewer;
