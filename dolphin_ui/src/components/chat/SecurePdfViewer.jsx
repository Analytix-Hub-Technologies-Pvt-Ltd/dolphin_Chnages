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
    <div
      ref={containerRef}
      className={`w-full bg-black ${isFullscreen ? "h-screen" : "h-[500px]"}`}
    >
      <iframe
        src={pdfUrl}
        title="PDF Viewer"
        width="100%"
        height="100%"
        allow="fullscreen"
        className="w-full h-full border-none"
      />
    </div>
  );
};

export default SecurePdfViewer;
