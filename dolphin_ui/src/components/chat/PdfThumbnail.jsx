import React, { useState, useEffect } from "react";
import { Box, Typography, CircularProgress } from "@mui/material";
import { DocumentIcon } from "../../assets/svgIcons/DocumentIcon";
import { resolveImageUrl } from "../../api/config";

const PdfThumbnail = ({ pdf, mediaThumbnailSx }) => {
  const [imgLoaded, setImgLoaded] = useState(false);
  const [imgError, setImgError] = useState(false);

  const rawLink = pdf?.link || pdf?.url || "";
  const rawThumbnail =
    pdf?.thumbnail ||
    (rawLink ? `/api/pdf_thumbnail?url=${encodeURIComponent(rawLink)}` : "");
  const resolvedThumbnailUrl = resolveImageUrl(rawThumbnail);

  useEffect(() => {
    setImgLoaded(false);
    setImgError(false);
  }, [resolvedThumbnailUrl]);

  return (
    <Box
      sx={{
        ...mediaThumbnailSx,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "background.paper",
        overflow: "hidden",
        position: "relative",
      }}
    >
      {!imgError && resolvedThumbnailUrl ? (
        <>
          {!imgLoaded && (
            <Box
              sx={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                backgroundColor: "grey.100",
              }}
            >
              <CircularProgress size={22} thickness={4} sx={{ color: "primary.main" }} />
            </Box>
          )}
          <img
            src={resolvedThumbnailUrl}
            alt={pdf?.title || "PDF Document"}
            loading="lazy"
            onLoad={() => setImgLoaded(true)}
            onError={() => {
              console.warn("PDF thumbnail failed to load from:", resolvedThumbnailUrl);
              setImgError(true);
            }}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: "top center",
              display: "block",
              borderRadius: "inherit",
              opacity: imgLoaded ? 1 : 0,
              transition: "opacity 0.25s ease-in-out",
            }}
          />
          {imgLoaded && (
            <Box
              sx={{
                position: "absolute",
                bottom: 4,
                right: 4,
                backgroundColor: "rgba(220, 38, 38, 0.9)",
                color: "#ffffff",
                fontSize: "0.6rem",
                fontWeight: 700,
                px: 0.6,
                py: 0.2,
                borderRadius: 0.5,
                lineHeight: 1,
                pointerEvents: "none",
                boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
              }}
            >
              PDF
            </Box>
          )}
        </>
      ) : (
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            gap: 0.5,
          }}
        >
          <DocumentIcon size={36} color="#0288d1" />
          <Typography
            variant="caption"
            sx={{ fontSize: "0.65rem", color: "text.secondary" }}
          >
            PDF Document
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default PdfThumbnail;

