import { Box } from "@mui/material";
import { useRef } from "react";
import { resolveImageUrl } from "../../api/config";

const SecurePdfViewer = ({ src }) => {
  const containerRef = useRef(null);

  // Resolve full valid URL and append parameters to hide toolbar, download button, and navpanes
  const resolved = resolveImageUrl(src) || src || "";
  const [baseAndQuery] = resolved.split("#");
  const pdfUrl = `${baseAndQuery}#toolbar=0&navpanes=0&scrollbar=0`;

  return (
    <Box
      ref={containerRef}
      sx={{
        width: "100%",
        height: "100%",
        backgroundColor: "black",
        overflow: "hidden",
        position: "relative",
      }}
      onContextMenu={(e) => e.preventDefault()}
    >
      <iframe
        src={pdfUrl}
        title="PDF Viewer"
        width="100%"
        height="100%"
        allow="fullscreen"
        style={{
          border: "none",
          width: "100%",
          height: "100%",
          display: "block",
        }}
      />
    </Box>
  );
};

export default SecurePdfViewer;
