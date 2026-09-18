import React, { useState, useMemo, useEffect } from "react";
import { ChevronDown, ChevronUp, Download, Play, User as UserIcon } from "lucide-react";
import QuizDisplay from "./QuizDisplay";
import { sanitizeMarkdown } from "./ChatWindow";
import DolphinIconW from "../../assets/images/dolphin_w.png";
import DolphinIconB from "../../assets/images/dolphin_b.png";
import { useThemeMode } from "../../context/ThemeModeContext";
import { VideoIcon } from "../../assets/svgIcons/VideoIcon";
import { ImageIcon } from "../../assets/svgIcons/ImageIcon";
import { DocumentIcon } from "../../assets/svgIcons/DocumentIcon";
import FeedbackRatingButtons from "../feedback/FeedbackRatingButtons";
const MediaPreviewModal = React.lazy(() => import("./MediaPreviewModal"));

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
  question = "",
  userProfile = null,
  videos_suggestions,
  images_suggestions,
  pdf_suggestions,
  sessionId,
  setSearchQuery,
  handleSend,
  onTopicClick,
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

  const rawTargetContent = useMemo(() => {
    return (
      msg.content ||
      msg.company_answer ||
      (Array.isArray(msg.sections)
        ? msg.sections
            .map((s) => s.content)
            .filter(Boolean)
            .join("\n\n")
        : "") ||
      ""
    );
  }, [msg.content, msg.company_answer, msg.sections]);

  // Direct content rendering without typewriter delays
  const displayedContent = rawTargetContent;
  const isTyping = Boolean(!isUser && msg.isStreaming && msg.isThinking !== false);

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
      const directUrl = img.url || img.Url || img.thumbnail || img.Thumbnail || img.src || img.image_url || img.imageUrl || "";
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
    setSearchQuery?.(query);
    await handleSend?.(query);
  };

  const isGapAnalysis = msg.metadata?.category === "GAP_ANALYSIS" || (msg.sections && msg.sections[0] && msg.sections[0].topic_code === "GAP_ANALYSIS");
  const showDownloadButton = isGapAnalysis && !msg.isThinking;
  const isOutOfScope =
    msg.metadata?.category === "OUT_OF_SCOPE" ||
    msg.metadata?.routing_reason === "out_of_scope" ||
    (typeof msg.content === "string" && (
      msg.content.includes("not covered in the available course material") ||
      msg.content.includes("falls outside the available course material") ||
      msg.content.includes("not included in the current course content") ||
      msg.content.includes("This is not part of the available course material")
    ));

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
    <div
      data-testid="chat-message"
      data-role={msg.role}
      className={`flex items-start gap-2 sm:gap-2.5 ${isUser ? "flex-row-reverse" : "flex-row w-full"}`}
    >
      {/* Avatar */}
      {isUser ? (
        <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-primary text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-xs">
          <UserIcon className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
        </div>
      ) : (
        <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-primary flex items-center justify-center p-1 shrink-0 shadow-xs">
          <img
            src={DolphinIconW}
            alt="Dolphin"
            className="w-4.5 h-4.5 sm:w-5 sm:h-5 object-contain"
          />
        </div>
      )}

      {/* Message Content Container */}
      <div
        className={`flex flex-col gap-0.5 ${
          isUser
            ? "w-auto max-w-[92%] sm:max-w-[85%] items-end"
            : "flex-1 min-w-0 w-full items-start"
        }`}
      >
        {/* Name and Timestamp Header */}
        <div className="flex items-center gap-1.5 px-0.5 mb-0.5">
          <span className="text-[11.5px] sm:text-xs font-semibold text-text-primary">
            {isUser ? "You" : "Dolphin AI"}
          </span>
          <span className="text-[10px] sm:text-[11px] text-text-caption opacity-70">
            {msg?.timestamp &&
              new Date(msg.timestamp).toLocaleTimeString("en-US", {
                hour: "numeric",
                minute: "2-digit",
                hour12: true,
              })}
          </span>
        </div>

        {/* Bubble */}
        <div
          className={`text-[13px] sm:text-[13.5px] leading-snug overflow-x-auto shadow-xs ${
            isUser
              ? "w-fit max-w-full px-2 py-1 sm:px-2.5 sm:py-1 rounded-xl rounded-tr-xs bg-bg-paper text-text-primary border border-black/[0.04] dark:border-white/[0.06] whitespace-pre-wrap"
              : "w-full px-3 py-2 sm:px-3.5 sm:py-2.5 rounded-xl rounded-tl-xs bg-bg-chatbackground text-text-primary border border-black/[0.04] dark:border-white/[0.06]"
          }`}
        >
          {isUser ? (
            <p className="m-0 text-text-primary font-normal leading-snug">{msg.content}</p>
          ) : msg.category !== "QUIZ" ? (
            <div className="flex flex-col gap-1">
              <div
                className="leading-snug break-words [&>p]:my-0.5 [&>ul]:my-0.5 [&>ol]:my-0.5 [&>table]:my-1 [&>h1]:my-1 [&>h2]:my-0.5 [&>h3]:my-0.5 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
                onClick={(e) => {
                  const target = e.target.closest(".topic-citation");
                  if (target) {
                    const index =
                      parseInt(target.getAttribute("data-topic-index")) - 1;
                    const topicCode =
                      Array.isArray(msg.topics) && msg.topics[index]
                        ? msg.topics[index]
                        : (Array.isArray(msg.topics) && msg.topics[0]) || "";
                    onTopicClick?.(topicCode, msg.topics || []);
                  }
                }}
                dangerouslySetInnerHTML={{
                  __html: sanitizeMarkdown(displayedContent).replace(
                    /(?:@@SOURCE_REF_|\[\[\s*Ref:?\s*)(\d+)\s*(?:@@|\]\])/gi,
                    '<span class="topic-citation" data-topic-index="$1" title="Click to see related topic notes">$1</span>',
                  ),
                }}
              />
              {isTyping && (
                <span className="inline-flex items-center ml-1.5 align-middle select-none">
                  <img
                    src={mode === "dark" ? DolphinIconW : DolphinIconB}
                    alt="Dolphin"
                    className="w-4 h-4 sm:w-4.5 sm:h-4.5 object-contain animate-dolphin-wave drop-shadow-xs"
                  />
                </span>
              )}

              {!isTyping && showDownloadButton && (
                <div className="flex flex-col items-end mt-4 pt-2 border-t border-border-theme animate-fade-in">
                  <button
                    type="button"
                    onClick={handleDownloadWordDoc}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-primary text-primary font-semibold text-xs hover:bg-primary/10 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download Word Doc</span>
                  </button>
                  {docError && (
                    <span className="text-xs text-rose-500 mt-1">{docError}</span>
                  )}
                </div>
              )}
            </div>
          ) : (
            <QuizDisplay quizContet={msg.content} />
          )}

          {/* Bottom attachments rendered with fade-in after streaming completes */}
          {!isTyping && (
            <div className="animate-fade-in flex flex-col">
              {/* Video Suggestions */}
              {videos_suggestions?.length > 0 && !isOutOfScope && (
            <div className="mt-4 pt-2">
              <div className="flex items-center gap-1.5 mb-2.5">
                <VideoIcon
                  size={24}
                  color={mode === "dark" ? "#e8f1fb" : "#0f1c2e"}
                />
                <h4 className="text-base font-bold text-text-primary m-0">
                  Video Suggestions
                </h4>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 py-1">
                {(showAllVideos ? videos_suggestions : videos_suggestions.slice(0, 4)).map((video, i) => {
                  const videoUrl = video.url || video.Url || "";
                  const videoThumb =
                    video.thumbnail || video.Thumbnail || video.thumbnail_url || "";
                  const videoTitle =
                    video.title || video.Title || video.About || "Video";

                  return (
                    <div
                      key={i}
                      onClick={() => openPreview("video", videoUrl)}
                      className="group relative w-full h-36 sm:h-44 rounded-xl bg-bg-paper border border-border-theme p-1.5 flex flex-col justify-between hover:border-primary hover:-translate-y-0.5 transition-all cursor-pointer shadow-xs"
                    >
                      <div className="relative w-full h-24 sm:h-32 rounded-lg overflow-hidden bg-black/5">
                        <img
                          src={videoThumb}
                          alt={videoTitle}
                          className="w-full h-full object-cover"
                        />
                        <div className="absolute inset-0 flex items-center justify-center bg-black/20 group-hover:bg-black/30 transition-colors">
                          <div className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center shadow-md group-hover:scale-110 transition-transform">
                            <Play className="w-4 h-4 fill-white ml-0.5" />
                          </div>
                        </div>
                      </div>
                      <span className="text-[0.72rem] font-medium text-primary text-center truncate block mt-1">
                        {videoTitle}
                      </span>
                    </div>
                  );
                })}
              </div>

              {videos_suggestions.length > 4 && (
                <button
                  type="button"
                  onClick={() => setShowAllVideos((prev) => !prev)}
                  className="mt-1.5 text-xs font-semibold text-text-primary hover:text-primary flex items-center justify-center gap-1 w-full py-1 transition-colors cursor-pointer"
                >
                  <span>{showAllVideos ? "Show less" : "Show more"}</span>
                  {showAllVideos ? (
                    <ChevronUp className="w-4 h-4" />
                  ) : (
                    <ChevronDown className="w-4 h-4" />
                  )}
                </button>
              )}
            </div>
          )}

          {/* Reference Images */}
          {validImages?.length > 0 && !isOutOfScope && (
            <div className="mt-4 pt-2">
              <div className="flex items-center gap-1.5 mb-2.5">
                <ImageIcon
                  size={20}
                  color={mode === "dark" ? "#e8f1fb" : "#0f1c2e"}
                />
                <h4 className="text-base font-bold text-text-primary m-0">
                  Reference Images
                </h4>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 py-1">
                {(showAllImages ? validImages : validImages.slice(0, 4)).map((img, i) => (
                  <div
                    key={img.id || i}
                    onClick={() => openPreview("image", img.imgSrc)}
                    className="w-full h-36 sm:h-44 rounded-xl bg-bg-paper border border-border-theme p-1.5 flex flex-col justify-between hover:border-primary hover:-translate-y-0.5 transition-all cursor-pointer shadow-xs"
                  >
                    <img
                      src={img.imgSrc}
                      alt={img.imgTitle}
                      className="w-full h-24 sm:h-32 object-cover rounded-lg"
                      onError={(e) => {
                        if (img.b64 && e.target.src !== img.b64) {
                          e.target.src = img.b64;
                        } else {
                          e.currentTarget.parentElement.style.display = "none";
                        }
                      }}
                    />
                    <span className="text-[0.72rem] font-medium text-primary text-center truncate block mt-1">
                      {img.imgTitle}
                    </span>
                  </div>
                ))}
              </div>

              {validImages.length > 4 && (
                <button
                  type="button"
                  onClick={() => setShowAllImages((prev) => !prev)}
                  className="mt-1.5 text-xs font-semibold text-text-primary hover:text-primary flex items-center justify-center gap-1 w-full py-1 transition-colors cursor-pointer"
                >
                  <span>{showAllImages ? "Show less" : "Show more"}</span>
                  {showAllImages ? (
                    <ChevronUp className="w-4 h-4" />
                  ) : (
                    <ChevronDown className="w-4 h-4" />
                  )}
                </button>
              )}
            </div>
          )}

          {/* Reference PDFs */}
          {pdf_suggestions?.length > 0 && !isOutOfScope && (
            <div className="mt-4 pt-2">
              <div className="flex items-center gap-1.5 mb-2.5">
                <DocumentIcon
                  size={20}
                  color={mode === "dark" ? "#e8f1fb" : "#0f1c2e"}
                />
                <h4 className="text-base font-bold text-text-primary m-0">
                  Reference PDFs
                </h4>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 py-1">
                {(showAllPdfs ? pdf_suggestions : pdf_suggestions.slice(0, 4)).map((pdf, i) => {
                  const pdfUrl =
                    pdf.url || pdf.Url || pdf.link || pdf.Link || pdf.file_url || "";
                  const pdfTitle =
                    pdf.title || pdf.Title || pdf.name || pdf.Name || "Reference PDF";
                  return (
                    <div
                      key={i}
                      onClick={() => openPreview("pdf", pdfUrl)}
                      className="w-full h-36 sm:h-44 rounded-xl bg-bg-paper border border-border-theme p-1.5 flex flex-col justify-between hover:border-primary hover:-translate-y-0.5 transition-all cursor-pointer shadow-xs"
                    >
                      <div className="w-full h-24 sm:h-32 rounded-lg bg-bg-default flex items-center justify-center text-3xl">
                        📄
                      </div>
                      <span className="text-[0.72rem] font-medium text-primary text-center truncate block mt-1">
                        {pdfTitle}
                      </span>
                    </div>
                  );
                })}
              </div>

              {pdf_suggestions.length > 4 && (
                <button
                  type="button"
                  onClick={() => setShowAllPdfs((prev) => !prev)}
                  className="mt-1.5 text-xs font-semibold text-text-primary hover:text-primary flex items-center justify-center gap-1 w-full py-1 transition-colors cursor-pointer"
                >
                  <span>{showAllPdfs ? "Show less" : "Show more"}</span>
                  {showAllPdfs ? (
                    <ChevronUp className="w-4 h-4" />
                  ) : (
                    <ChevronDown className="w-4 h-4" />
                  )}
                </button>
              )}
            </div>
          )}

          {/* Related / Licensed Courses */}
          {(() => {
            const rawCourses = msg.checkLicCoursesData || msg.courses || msg.related_courses;
            if (
              !rawCourses ||
              !Array.isArray(rawCourses) ||
              rawCourses.length === 0
            )
              return null;

            const flatList = rawCourses.flat(Infinity).filter(Boolean);
            if (flatList.length === 0) return null;

            const userType =
              flatList[0]?.user_type?.toLowerCase() ||
              flatList[0]?.role?.toLowerCase() ||
              "";
            const isStudent = userType === "student";

            const coursesToShow = flatList.filter((item) => {
              if (isStudent) return item?.matched;
              return true;
            });

            const uniqueCoursesMap = new Map();
            coursesToShow.forEach((item) => {
              const rawCourse =
                item?.data?.course ||
                item?.course ||
                item?.data?.courses ||
                item?.courses ||
                (item?.CourseName || item?.courseName ? item : null);

              const courseList = Array.isArray(rawCourse) ? rawCourse : [rawCourse];

              courseList.forEach((c) => {
                if (!c) return;
                let code = "";
                let name = "";
                if (typeof c === "string") {
                  code = c;
                  name = c;
                } else if (typeof c === "object") {
                  code =
                    c.CourseCode ||
                    c.courseCode ||
                    c.code ||
                    c.id ||
                    c.CourseName ||
                    c.courseName ||
                    c.title ||
                    "";
                  name =
                    c.CourseName ||
                    c.courseName ||
                    c.title ||
                    c.name ||
                    code ||
                    "Unknown Course";
                }

                if (code && !uniqueCoursesMap.has(code)) {
                  uniqueCoursesMap.set(code, {
                    CourseName: name,
                    CourseCode: code,
                    matched: Boolean(item.matched),
                    topicName:
                      item.data?.topic_name ||
                      item.topic_name ||
                      item.data?.topicName ||
                      item.topicName ||
                      "",
                  });
                }
              });
            });

            const uniqueCourses = Array.from(uniqueCoursesMap.values());
            if (uniqueCourses.length === 0) return null;

            return (
              <div className="mt-4 pt-2 border-t border-border-theme">
                <span className="block text-xs font-bold uppercase tracking-wider text-text-secondary mb-2">
                  Related Courses
                </span>
                <div className="space-y-2">
                  {uniqueCourses.map((course, i) => (
                    <div
                      key={i}
                      className={`flex items-center justify-between p-3 rounded-xl border text-xs ${
                        course.matched
                          ? "bg-emerald-500/10 border-emerald-500/30 dark:bg-emerald-500/15"
                          : "bg-bg-paper border-border-theme"
                      }`}
                    >
                      <div>
                        <p className="font-semibold text-text-primary text-sm m-0">
                          {course.CourseName || course.courseName || "Unknown Course"}
                        </p>
                        {course.topicName && (
                          <span className="text-xs text-text-secondary block mt-0.5">
                            Topic: {course.topicName}
                          </span>
                        )}
                      </div>
                      {course.matched && (
                        <span className="px-2 py-0.5 rounded-md bg-emerald-600 text-white font-bold text-[0.65rem] tracking-wider uppercase">
                          LICENSED
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* Question Suggestions */}
          {msg.question_suggestions?.length > 0 && (
            <div className="mt-4 pt-2 flex flex-col gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-text-primary">
                Try asking...
              </span>
              <div className="flex flex-wrap gap-2">
                {msg.question_suggestions.map((q, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => handleFollowUpQuestion(q)}
                    className="py-1.5 px-3 rounded-xl bg-bg-paper border border-border-theme text-text-primary text-xs font-medium hover:border-primary hover:text-primary transition-all cursor-pointer shadow-xs text-left"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Feedback Rating Buttons */}
          {!isUser && !isTyping && (msg.content || msg.company_answer || (Array.isArray(msg.sections) && msg.sections.length > 0)) && (
            <div className="mt-3 pt-2 border-t border-border-theme/60 flex items-center justify-between">
              <FeedbackRatingButtons
                question={question || msg.question || msg.user_query || msg.query || "Maritime query"}
                userProfile={userProfile}
                originalResponse={
                  (typeof msg.content === "string" && msg.content)
                    ? msg.content
                    : (typeof msg.company_answer === "string" && msg.company_answer)
                    ? msg.company_answer
                    : (Array.isArray(msg.sections) ? msg.sections.map((s) => s.content).filter(Boolean).join("\n\n") : "") ||
                      "Maritime response"
                }
                sessionId={sessionId}
                messageId={msg.id || msg.message_id}
              />
            </div>
          )}
            </div>
          )}
        </div>
      </div>

      {previewMedia.open && (
        <React.Suspense fallback={null}>
          <MediaPreviewModal
            open={previewMedia.open}
            type={previewMedia.type}
            src={previewMedia.src}
            onClose={closePreview}
          />
        </React.Suspense>
      )}
    </div>
  );
};

export default React.memo(ChatMessage);
