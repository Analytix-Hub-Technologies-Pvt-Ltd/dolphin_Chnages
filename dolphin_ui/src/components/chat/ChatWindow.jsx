import React, { useEffect, useRef, useState, useCallback } from "react";
import { SendIcon } from "../../assets/svgIcons/sendIcon";
import { marked } from "marked";
import DOMPurify from "dompurify";
import WelcomeChatScreen from "./WelcomeChatScreen";
import { ensureSession, sendMessageStream, checkDocumentGapsStream, checkLicCourses, fetchTopicDetails } from "../../api/fetchApi";
import ChatMessage from "./ChatMessage";
import { useThemeMode } from "../../context/ThemeModeContext";
import { Message } from "../../assets/svgIcons/message";
import DolphinIconW from "../../assets/images/dolphin_w.png";
import { StopIcon } from "../../assets/svgIcons/StopIcon";
import axios from "axios";
import { fetchUserProfile } from "../../api/apiAuth";
import { X, ChevronLeft } from "lucide-react";

export const sanitizeMarkdown = (markdownText) => {
  if (!markdownText) return "";

  try {
    // Remove all checkbox brackets [ ], [x], [X], [  ]
    const cleanedMarkdown = String(markdownText).replace(/\[\s*[xX]?\s*\]/g, "");

    // Pre-process tables (pipe rows or tab-separated tables)
    const lines = cleanedMarkdown.split(/\r?\n/);
    let inTable = false;
    let tableCols = 0;
    let processedLines = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();

      if (!trimmed) {
        inTable = false;
        tableCols = 0;
        processedLines.push("");
        continue;
      }

      const isPipeRow = trimmed.startsWith("|") && trimmed.endsWith("|") && trimmed.length > 2;
      const isPipeSeparator = isPipeRow && /^\|(?:\s*:?-+:?\s*\|)+$/.test(trimmed);
      const isMarkdownElement = trimmed.startsWith("#") || trimmed.startsWith("-") || trimmed.startsWith("*") || trimmed.startsWith(">") || /^\d+\./.test(trimmed);

      let cells = [];
      if (isPipeRow) {
        if (isPipeSeparator) {
          processedLines.push(trimmed);
          continue;
        }
        cells = trimmed.slice(1, -1).split("|").map((c) => c.trim());
      } else if (!isMarkdownElement) {
        if (line.includes("\t")) {
          cells = line.split("\t").map((c) => c.trim());
        } else if (inTable) {
          cells = [trimmed];
        }
      }

      if (cells.length >= 2 || (inTable && cells.length === 1)) {
        if (!inTable) {
          inTable = true;
          tableCols = Math.max(cells.length, 2);

          while (cells.length < tableCols) cells.push("");
          const mdHeader = `| ${cells.join(" | ")} |`;

          const nextLine = lines[i + 1] ? lines[i + 1].trim() : "";
          const nextIsSep = nextLine.startsWith("|") && /^\|(?:\s*:?-+:?\s*\|)+$/.test(nextLine);

          processedLines.push(mdHeader);
          if (!nextIsSep) {
            const mdSep = `| ${Array(tableCols).fill("---").join(" | ")} |`;
            processedLines.push(mdSep);
          }
        } else {
          while (cells.length < tableCols) cells.push("");
          const mdRow = `| ${cells.slice(0, tableCols).join(" | ")} |`;
          processedLines.push(mdRow);
        }
      } else {
        inTable = false;
        tableCols = 0;
        processedLines.push(line);
      }
    }

    const cleanMarkdown = processedLines.join("\n");

    marked.setOptions({
      gfm: true,
      breaks: true,
    });

    let rawHtml = marked.parse(cleanMarkdown);
    if (typeof rawHtml === "string") {
      rawHtml = rawHtml
        .replace(/<table>/g, '<div class="table-wrapper"><table>')
        .replace(/<\/table>/g, '</table></div>');
    }

    if (DOMPurify && typeof DOMPurify.sanitize === "function") {
      return DOMPurify.sanitize(rawHtml);
    }
    return rawHtml;
  } catch (err) {
    console.error("Markdown sanitization error:", err);
    return String(markdownText)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\n/g, "<br/>");
  }
};

const OUT_OF_SCOPE_MARKERS = [
  "not covered in the available course material",
  "falls outside the available course material",
  "not included in the current course content",
  "This is not part of the available course material",
];

const isOutOfScopeAnswer = (msg) =>
  msg?.metadata?.category === "OUT_OF_SCOPE" ||
  (typeof msg?.content === "string" &&
    OUT_OF_SCOPE_MARKERS.some((marker) => msg.content.includes(marker)));

const ChatWindow = ({
  userId,
  currentSessionData,
  currentSessionId,
  setCurrentSessionId,
  activeIndex,
  loading,
  fetchSessions,
  messages,
  setmessages,
  setDisableNewChat,
  disableNewChat,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [isCaptainMode, setIsCaptainMode] = useState(false);
  const { mode } = useThemeMode();

  const [sourcesData, setSourcesData] = useState({
    open: false,
    loading: false,
    topics: [],
    selectedTopicCode: null,
    detailTopic: null,
    totalSources: 0,
  });

  useEffect(() => {
    setSourcesData((prev) => ({ ...prev, open: false, detailTopic: null }));
  }, [currentSessionId]);

  const handleTopicClick = useCallback(
    async (rawTopic, allMessageTopics = []) => {
      const topicCode =
        typeof rawTopic === "string"
          ? rawTopic
          : rawTopic?.code || rawTopic?.topic_code || "";

      if (!topicCode) return;

      const clickedIndex = allMessageTopics.findIndex(
        (t) => (typeof t === "string" ? t : t?.code || t?.topic_code) === topicCode
      );
      const displayIndex = clickedIndex >= 0 ? clickedIndex + 1 : 1;

      setSourcesData({
        open: true,
        loading: true,
        topics: [],
        totalSources: 1,
        selectedTopicCode: topicCode,
        detailTopic: null,
      });

      try {
        const data = await fetchTopicDetails(topicCode);

        const resolvedTopic = {
          code: topicCode,
          index: displayIndex,
          topicName: data?.topic_name || data?.title || topicCode,
          courseName: data?.course_name || "",
          content:
            data?.topic_content ||
            data?.content ||
            data?.text ||
            "No content found.",
          _fetched: true,
        };

        setSourcesData({
          open: true,
          loading: false,
          topics: [resolvedTopic],
          totalSources: 1,
          selectedTopicCode: topicCode,
          detailTopic: null,
        });
      } catch (err) {
        console.error("Failed to fetch topic details:", err);
        setSourcesData((prev) => ({
          ...prev,
          loading: false,
        }));
      }
    },
    []
  );

  const [userProfile, setUserProfile] = useState(() => {
    try {
      const stored = localStorage.getItem("userData");
      return stored ? JSON.parse(stored) : null;
    } catch (e) {
      return null;
    }
  });

  useEffect(() => {
    const loadProfile = async () => {
      const currentUserId =
        userId ||
        localStorage.getItem("userId") ||
        localStorage.getItem("user_id");
      if (currentUserId) {
        const profile = await fetchUserProfile(currentUserId);
        if (profile) {
          setUserProfile(profile);
        }
      }
    };
    loadProfile();
  }, [userId]);

  const isCaptainOrMaster = Boolean(
    userProfile &&
    ((userProfile.role &&
      (userProfile.role.toLowerCase().includes("captain") ||
        userProfile.role.toLowerCase().includes("master"))) ||
      (userProfile.user_type &&
        (userProfile.user_type.toLowerCase().includes("captain") ||
          userProfile.user_type.toLowerCase().includes("master"))) ||
      (userProfile.rank &&
        (userProfile.rank.toLowerCase().includes("captain") ||
          userProfile.rank.toLowerCase().includes("master"))) ||
      (userProfile.designation &&
        (userProfile.designation.toLowerCase().includes("captain") ||
          userProfile.designation.toLowerCase().includes("master"))))
  );

  const bottomRef = useRef(null);
  const abortControllerRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    if (!searchQuery && textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [searchQuery]);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  };

  const ThinkingBubble = ({ statusText }) => {
    const rawText = statusText || "Dolphin is thinking...";
    const cleanText = rawText.replace(/\.+$/, "").trim();

    return (
      <div className="flex items-center gap-2 w-fit">
        <div className="flex justify-center items-center w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-primary shrink-0 shadow-xs p-1">
          <img
            src={DolphinIconW}
            alt="Dolphin"
            className="w-4.5 h-4.5 sm:w-5 sm:h-5 object-contain"
          />
        </div>

        <div className="font-semibold bg-bg-chatbackground px-2 py-1 rounded-xl rounded-tl-xs border border-black/[0.04] dark:border-white/[0.06] text-primary text-xs flex items-center gap-1 shadow-xs">
          <span>{cleanText}</span>
          <span className="animate-pulse">.</span>
          <span className="animate-pulse delay-150">.</span>
          <span className="animate-pulse delay-300">.</span>
        </div>
      </div>
    );
  };

  const scrollToBottom = (smooth = true) => {
    if (bottomRef.current && typeof bottomRef.current.scrollIntoView === "function") {
      bottomRef.current.scrollIntoView({
        behavior: smooth ? "smooth" : "auto",
        block: "end",
      });
    }
  };

  const prevSessionIdRef = useRef(currentSessionId);

  useEffect(() => {
    const isSessionSwitch = prevSessionIdRef.current !== currentSessionId;
    prevSessionIdRef.current = currentSessionId;
    scrollToBottom(!isSessionSwitch);
  }, [messages, currentSessionId]);

  // Backfill related courses for loaded historical messages if missing
  useEffect(() => {
    if (!Array.isArray(messages) || messages.length === 0) return;

    messages.forEach((msg, idx) => {
      if (
        msg.role !== "assistant" ||
        (Array.isArray(msg.checkLicCoursesData) && msg.checkLicCoursesData.length > 0) ||
        (Array.isArray(msg.courses) && msg.courses.length > 0)
      ) {
        return;
      }

      const topicItems = [];
      if (Array.isArray(msg.sections)) {
        msg.sections.forEach((s) => {
          if (s?.topic_code) {
            topicItems.push({
              code: s.topic_code,
              name: s.topic_name || "",
              source_code: s.source_code || s.course_code || "",
            });
          }
        });
      }
      if (Array.isArray(msg.topic_codes)) {
        msg.topic_codes.forEach((tc) => {
          if (tc) topicItems.push({ code: tc, name: "", source_code: "" });
        });
      }

      if (topicItems.length === 0) return;

      const currentUid =
        userId ||
        localStorage.getItem("userId") ||
        localStorage.getItem("user_id") ||
        userProfile?.id ||
        userProfile?.user_id;

      const isPseudoTopicCode = (c) => {
        const upper = String(c || "").trim().toUpperCase();
        return (
          !upper ||
          upper === "COMPANY_SMS" ||
          upper === "GAP_ANALYSIS" ||
          upper === "NONE" ||
          upper === "MARITIME_QUERY" ||
          upper === "SMS_GAP_ANALYSIS"
        );
      };

      const checked = new Set();
      topicItems.forEach(({ code, name, source_code }) => {
        const cClean = String(code || "").trim();
        if (!cClean || isPseudoTopicCode(cClean) || checked.has(cClean)) return;
        checked.add(cClean);

        const sClean = String(source_code || "").trim();

        try {
          const res = checkLicCourses({
            topic_code: cClean,
            ...(sClean && sClean !== cClean ? { source_code: sClean } : {}),
            user_id: currentUid,
          });
          if (res && typeof res.then === "function") {
            res
              .then((data) => {
                if (!data) return;
                const newItems = (Array.isArray(data) ? data : [data])
                  .filter((item) => Boolean(item && item.data && item.data.course))
                  .map((item) => {
                    if (item && name && item.data && !item.data.topic_name) {
                      return { ...item, data: { ...item.data, topic_name: name } };
                    }
                    return item;
                  });
                if (newItems.length === 0) return;

                setmessages((prev = []) => {
                  const next = [...prev];
                  if (!next[idx] || next[idx].role !== "assistant") return prev;
                  const currentList = Array.isArray(next[idx].checkLicCoursesData)
                    ? [...next[idx].checkLicCoursesData]
                    : [];
                  const existingCodes = new Set(
                    currentList
                      .map((c) =>
                        String(
                          c?.data?.course?.CourseCode ||
                            c?.data?.course?.courseCode ||
                            c?.CourseCode ||
                            c?.courseCode ||
                            ""
                        ).toLowerCase()
                      )
                      .filter(Boolean)
                  );
                  newItems.forEach((it) => {
                    const cd = String(
                      it?.data?.course?.CourseCode ||
                        it?.data?.course?.courseCode ||
                        it?.CourseCode ||
                        it?.courseCode ||
                        ""
                    ).toLowerCase();
                    if (!cd || !existingCodes.has(cd)) {
                      if (cd) existingCodes.add(cd);
                      currentList.push(it);
                    }
                  });
                  next[idx] = {
                    ...next[idx],
                    checkLicCoursesData: currentList,
                    courses: currentList,
                  };
                  return next;
                });
              })
              .catch(() => {});
          }
        } catch {
          // ignore
        }
      });
    });
  }, [messages, userId, userProfile]);

  const handleSend = async (queryOverride) => {
    if (disableNewChat) return;
    const messageText = queryOverride ?? searchQuery;

    // If there's no text and no selected file, do nothing
    if (!messageText.trim() && !selectedFile) return;

    // If a file is selected, handle its upload
    if (selectedFile) {
      const file = selectedFile;
      const userMessageContent = messageText.trim()
        ? `${messageText.trim()}\n\n*(Attachment: ${file.name})*`
        : `Uploaded document **${file.name}** for industry standards gap analysis.`;

      const userMessage = {
        role: "user",
        content: userMessageContent,
        timestamp: new Date().toISOString(),
      };

      setmessages((prev = []) => [...prev, userMessage]);
      setSearchQuery("");
      setSelectedFile(null); // Clear file selection immediately so UI updates

      setmessages((prev = []) => [
        ...prev,
        { role: "assistant", isThinking: true },
      ]);

      setDisableNewChat(true);
      const controller = new AbortController();
      abortControllerRef.current = controller;

      let assistantMsg = {
        role: "assistant",
        content: "",
        isThinking: true,
        status: "analyzing",
        statusText: "Dolphin is analyzing the document...",
        timestamp: new Date().toISOString(),
        sections: [
          {
            topic_code: "GAP_ANALYSIS",
            topic_name: `Gap Analysis - ${file.name}`,
            content: "",
          }
        ],
        metadata: {
          source_layer: "Industry Standards Check",
          category: "GAP_ANALYSIS",
        },
      };

      setmessages((prev = []) => [
        ...prev.filter((m) => !m.isThinking),
        assistantMsg,
      ]);

      try {
        await checkDocumentGapsStream(file, controller.signal, (chunk) => {
          if (chunk.type === "status") {
            if (chunk.status === "completed") {
              if (assistantMsg.content) {
                assistantMsg.isThinking = false;
              }
            } else {
              assistantMsg.status = chunk.status;
              assistantMsg.statusText = chunk.message || "Dolphin is thinking...";
              if (!assistantMsg.content) {
                assistantMsg.isThinking = true;
              }
            }
          } else if (chunk.type === "content") {
            assistantMsg.isThinking = false;
            assistantMsg.content += chunk.token;
            assistantMsg.sections[0].content = assistantMsg.content;
          }

          setmessages((prev = []) => {
            const nextMsgs = [...prev];
            const idx = nextMsgs.findLastIndex((m) => m.role === "assistant");
            if (idx !== -1) {
              nextMsgs[idx] = { ...assistantMsg };
            }
            return nextMsgs;
          });
        });
      } catch (error) {
        if (axios.isCancel(error) || error.name === "CanceledError" || error.message === "canceled" || error.name === "AbortError") {
          setmessages((prev = []) => prev.filter((m) => !m.isThinking && m.content !== ""));
        } else {
          setmessages((prev = []) => {
            const clean = prev.filter((m) => !m.isThinking);
            return clean.concat({
              role: "assistant",
              content: `Error performing gap analysis: ${error.message}`,
              timestamp: new Date().toISOString(),
            });
          });
        }
      } finally {
        setDisableNewChat(false);
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
      }
      return;

    }

    const trimmedText = messageText.trim();
    if (trimmedText) {
      // 1. Immediately render user bubble and thinking bubble, and clear input
      const userMessage = {
        role: "user",
        content: trimmedText,
        timestamp: new Date().toISOString(),
      };

      let assistantMsg = {
        role: "assistant",
        content: "",
        isThinking: true,
        isStreaming: false,
        status: "understanding",
        statusText: "Dolphin is thinking...",
        timestamp: new Date().toISOString(),
        videos: [],
        images: [],
        pdfs: [],
        question_suggestions: [],
        company_answer: "",
        metadata: {},
        sections: [],
        topics: [],
        checkLicCoursesData: [],
      };

      setmessages((prev = []) => [...prev, userMessage, assistantMsg]);
      setSearchQuery("");
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
      setDisableNewChat(true);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      // Tracks the citation that should be appended once the current section's
      // content tokens finish streaming. Flushed when the next source_topic
      // arrives or when the stream ends.
      let pendingCitation = null; // { code, refIndex }

      const flushCitationBadge = (citation) => {
        if (!citation || !citation.refIndex) return;
        const marker = ` @@SOURCE_REF_${citation.refIndex}@@ `;
        let content = assistantMsg.content || "";
        if (content.includes(`@@SOURCE_REF_${citation.refIndex}@@`)) return;

        const mocRegex = /(\n+\s*[*_]*\(?\s*[*_]*AI Advisory Observation only[\s\S]*?(?:Management of Change|\bMoC\b)[\s\S]*?\)?\s*[*_]*\s*)$/i;
        if (mocRegex.test(content)) {
          assistantMsg.content = content.replace(mocRegex, `${marker}\n\n$1`);
        } else {
          assistantMsg.content = content.trimEnd() + marker;
        }
      };

      const finalizeCitations = () => {
        let content = assistantMsg.content || "";
        const sec3HeadingRegex = /(\n+\s*(?:#{1,6}\s*)?(?:[^\w\n]*\s*)?3\.\s*(?:Comparative\s*Gap|Comparison))/i;
        const obsHeadingRegex = /(\n+\s*(?:[-*•]\s*)?(?:\*{1,3}|#{1,6}\s*)?(?:[^\w\n]*\s*)?AI Advisory Observation(?:\(s\))?:?(?:\*{1,3})?)/i;
        const mocNoticeRegex = /(\n+\s*[*_]*\(?\s*[*_]*AI Advisory Observation only[\s\S]*?(?:Management of Change|\bMoC\b)[\s\S]*?\)?\s*[*_]*\s*)$/i;

        const topicCount = Array.isArray(assistantMsg.topics) ? assistantMsg.topics.length : 0;

        if (topicCount > 0) {
          if (!content.includes("@@SOURCE_REF_")) {
            if (sec3HeadingRegex.test(content) && topicCount >= 3) {
              content = content.replace(sec3HeadingRegex, ` @@SOURCE_REF_1@@\n\n$1`);
              if (obsHeadingRegex.test(content)) {
                content = content.replace(obsHeadingRegex, ` @@SOURCE_REF_2@@\n\n$1`);
              }
              if (mocNoticeRegex.test(content)) {
                content = content.replace(mocNoticeRegex, ` @@SOURCE_REF_3@@\n\n$1`);
              }
            } else if (obsHeadingRegex.test(content)) {
              content = content.replace(obsHeadingRegex, ` @@SOURCE_REF_1@@\n\n$1`);
              if (topicCount >= 2 && mocNoticeRegex.test(content)) {
                content = content.replace(mocNoticeRegex, ` @@SOURCE_REF_2@@\n\n$1`);
              }
            } else if (mocNoticeRegex.test(content)) {
              content = content.replace(mocNoticeRegex, ` @@SOURCE_REF_1@@\n\n$1`);
            } else {
              content = content.trimEnd() + ` @@SOURCE_REF_1@@ `;
            }
            assistantMsg.content = content;
          } else if (pendingCitation) {
            flushCitationBadge(pendingCitation);
          }
        } else if (pendingCitation) {
          flushCitationBadge(pendingCitation);
        }
        pendingCitation = null;
      };

      const checkedTopicCodes = new Set();
      const checkCoursesForTopic = (rawTopicCode, rawTopicName = "", rawSourceCode = "") => {
        const code = String(rawTopicCode || "").trim();
        const upper = code.toUpperCase();
        if (
          !code ||
          upper === "COMPANY_SMS" ||
          upper === "GAP_ANALYSIS" ||
          upper === "NONE" ||
          upper === "MARITIME_QUERY" ||
          upper === "SMS_GAP_ANALYSIS" ||
          checkedTopicCodes.has(code)
        ) {
          return;
        }
        checkedTopicCodes.add(code);

        const source = String(rawSourceCode || "").trim();

        const currentUid =
          userId ||
          resolvedUserId ||
          localStorage.getItem("userId") ||
          localStorage.getItem("user_id") ||
          userProfile?.id ||
          userProfile?.user_id;

        try {
          const res = checkLicCourses({
            topic_code: code,
            ...(source && source !== code ? { source_code: source } : {}),
            user_id: currentUid,
          });

          if (res && typeof res.then === "function") {
            res
              .then((data) => {
                if (!data) return;
                const newItems = (Array.isArray(data) ? data : [data])
                  .filter((item) => Boolean(item && item.data && item.data.course))
                  .map((item) => {
                    if (item && rawTopicName && item.data && !item.data.topic_name) {
                      return { ...item, data: { ...item.data, topic_name: rawTopicName } };
                    }
                    return item;
                  });

                if (newItems.length === 0) return;

                if (!Array.isArray(assistantMsg.checkLicCoursesData)) {
                  assistantMsg.checkLicCoursesData = [];
                }
                assistantMsg.checkLicCoursesData.push(...newItems);
                assistantMsg.courses = [...assistantMsg.checkLicCoursesData];

                setmessages((prev = []) => {
                  const nextMsgs = [...prev];
                  const idx = nextMsgs.findLastIndex((m) => m.role === "assistant");
                  if (idx !== -1) {
                    nextMsgs[idx] = {
                      ...nextMsgs[idx],
                      ...assistantMsg,
                      checkLicCoursesData: [...assistantMsg.checkLicCoursesData],
                      courses: [...assistantMsg.checkLicCoursesData],
                    };
                  }
                  return nextMsgs;
                });
              })
              .catch((err) => {
                console.error("Error checking licensed courses:", err);
              });
          }
        } catch (err) {
          console.error("Error invoking checkLicCourses:", err);
        }
      };

      const resolvedUserId =
        userId ||
        localStorage.getItem("userId") ||
        localStorage.getItem("user_id") ||
        "guest";

      let activeSessionId = currentSessionId;
      try {
        // 2. Resolve session in background without blocking bubble rendering
        activeSessionId = currentSessionId
          ? await ensureSession(currentSessionId, resolvedUserId)
          : await ensureSession(null, resolvedUserId);

        await sendMessageStream(
          activeSessionId,
          trimmedText,
          resolvedUserId,
          controller.signal,
          async (chunk) => {
            if (chunk.type === "status") {
              if (chunk.status === "completed") {
                if (assistantMsg.content) {
                  assistantMsg.isThinking = false;
                }
              } else {
                assistantMsg.status = chunk.status;
                assistantMsg.statusText = chunk.message || "Dolphin is thinking...";
                if (!assistantMsg.content) {
                  assistantMsg.isThinking = true;
                }
              }
            } else if (
              chunk.type === "content" ||
              chunk.type === "message" ||
              chunk.type === "answer" ||
              chunk.type === "response" ||
              chunk.type === "greeting" ||
              chunk.type === "query" ||
              chunk.type === "qa" ||
              chunk.type === "node_response" ||
              // "company_content" also carries .content, but belongs in its own
              // branch below - it must not overwrite the assistant answer.
              (chunk.content !== undefined && chunk.type !== "company_content")
            ) {
              assistantMsg.isThinking = false;
              assistantMsg.isStreaming = true;
              if (chunk.token !== undefined) {
                assistantMsg.content += chunk.token;
              } else if (chunk.content !== undefined) {
                assistantMsg.content = chunk.content;
              } else if (chunk.text !== undefined) {
                assistantMsg.content = chunk.text;
              }

              if (Array.isArray(chunk.sections) && chunk.sections.length > 0) {
                assistantMsg.sections = chunk.sections;
              }
              // Media is suppressed for out-of-scope answers, matching the
              // "media" and "transcript_result" branches below.
              if (isOutOfScopeAnswer(assistantMsg)) {
                assistantMsg.videos = [];
                assistantMsg.images = [];
                assistantMsg.pdfs = [];
              } else {
                const incomingVideos =
                  (Array.isArray(chunk.videos) && chunk.videos.length > 0
                    ? chunk.videos
                    : chunk.video_suggestions) || [];
                if (incomingVideos.length > 0) {
                  assistantMsg.videos = incomingVideos;
                }
                if (Array.isArray(chunk.images) && chunk.images.length > 0) {
                  assistantMsg.images = chunk.images;
                }
                if (Array.isArray(chunk.pdfs) && chunk.pdfs.length > 0) {
                  assistantMsg.pdfs = chunk.pdfs;
                }
              }
              if (Array.isArray(chunk.question_suggestions) && chunk.question_suggestions.length > 0) {
                assistantMsg.question_suggestions = chunk.question_suggestions;
              }
              if (chunk.metadata) {
                assistantMsg.metadata = { ...assistantMsg.metadata, ...chunk.metadata };
              }
            } else if (chunk.type === "error") {
              assistantMsg.isThinking = false;
              assistantMsg.isStreaming = false;
              assistantMsg.content = chunk.message || "Failed to generate response.";
            } else if (chunk.type === "source_topic" || chunk.type === "topic" || chunk.type === "source") {
              const code = chunk.topic_code || chunk.code || chunk.topicCode || "";
              const sourceCode =
                (chunk.source_code && chunk.source_code !== code ? chunk.source_code : "") ||
                (chunk.course_code && chunk.course_code !== code ? chunk.course_code : "") ||
                "";
              const name = chunk.topic_name || chunk.source_name || chunk.name || chunk.topicName || "";

              // The arrival of a new source_topic signals the previous section
              // just finished streaming — flush its citation badge now.
              if (pendingCitation) {
                flushCitationBadge(pendingCitation);
                pendingCitation = null;
              }

              if (!assistantMsg.sections) assistantMsg.sections = [];
              assistantMsg.sections.push({
                topic_code: code,
                source_code: sourceCode,
                course_code: sourceCode,
                topic_name: name,
                content: "",
              });
              if (!assistantMsg.topics) assistantMsg.topics = [];
              if (!assistantMsg.topics.includes(code)) {
                assistantMsg.topics.push(code);
                // Queue the badge — will be placed after this section's tokens arrive
                pendingCitation = { code, refIndex: assistantMsg.topics.length };
              }

              if (code) {
                checkCoursesForTopic(code, name, sourceCode);
              }
            } else if (chunk.type === "suggestions") {
              assistantMsg.question_suggestions = chunk.question_suggestions || [];
            } else if (chunk.type === "media") {
              const isOutOfScope =
                assistantMsg.metadata?.category === "OUT_OF_SCOPE" ||
                (typeof assistantMsg.content === "string" && (
                  assistantMsg.content.includes("not covered in the available course material") ||
                  assistantMsg.content.includes("falls outside the available course material") ||
                  assistantMsg.content.includes("not included in the current course content") ||
                  assistantMsg.content.includes("This is not part of the available course material")
                ));
              if (isOutOfScope) {
                assistantMsg.videos = [];
                assistantMsg.images = [];
                assistantMsg.pdfs = [];
              } else {
                const currentVideos = assistantMsg.videos || [];
                const incomingVideos = chunk.videos || [];
                const seenKeys = new Set();
                const mergedVideos = [];

                const addVid = (v) => {
                  const url = v?.url || v?.Url || v?.videourl || "";
                  const id = v?.id || v?.Id || v?.video_id || "";
                  const title = (v?.title || v?.Title || "").trim().toLowerCase();
                  const uuidMatch = (url + " " + id).match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
                  const uuid = uuidMatch ? uuidMatch[0].toLowerCase() : "";
                  const key = uuid || id || title || url;
                  if (!key || seenKeys.has(key)) return;
                  seenKeys.add(key);
                  if (title && title.length > 3) {
                    if (seenKeys.has(`title:${title}`)) return;
                    seenKeys.add(`title:${title}`);
                  }
                  mergedVideos.push(v);
                };

                for (const v of currentVideos) addVid(v);
                for (const v of incomingVideos) addVid(v);

                assistantMsg.videos = mergedVideos;
                assistantMsg.images = chunk.images || assistantMsg.images || [];
                assistantMsg.pdfs = chunk.pdfs || assistantMsg.pdfs || [];

                if (Array.isArray(chunk.topic_codes)) {
                  const isUuid = (c) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(c).trim());
                  const validCodes = chunk.topic_codes.map((c) => String(c || "").trim()).filter((c) => isUuid(c));

                  // If assistantMsg.topics was already populated by source_topic events,
                  // keep only those cited topics. Do NOT dump all 10 un-cited vector search chunks.
                  if (!assistantMsg.topics || assistantMsg.topics.length === 0) {
                    assistantMsg.topics = validCodes.slice(0, 2);
                    assistantMsg.topics.forEach((tCode) => {
                      checkCoursesForTopic(tCode);
                    });
                  }
                }
              }
            } else if (chunk.type === "company_content") {
              assistantMsg.company_answer = chunk.content;
            } else if (chunk.type === "transcript_result") {
              const isOutOfScope =
                assistantMsg.metadata?.category === "OUT_OF_SCOPE" ||
                (typeof assistantMsg.content === "string" && (
                  assistantMsg.content.includes("not covered in the available course material") ||
                  assistantMsg.content.includes("falls outside the available course material") ||
                  assistantMsg.content.includes("not included in the current course content") ||
                  assistantMsg.content.includes("This is not part of the available course material")
                ));
              if (isOutOfScope) {
                assistantMsg.videos = [];
              } else {
                const currentVideos = assistantMsg.videos || [];
                const incomingChunks = chunk.chunks || [];
                const seenKeys = new Set();
                const mergedVideos = [];

                const addVid = (v) => {
                  const url = v?.url || v?.Url || v?.videourl || "";
                  const id = v?.id || v?.Id || v?.video_id || "";
                  const title = (v?.title || v?.Title || "").trim().toLowerCase();
                  const uuidMatch = (url + " " + id).match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
                  const uuid = uuidMatch ? uuidMatch[0].toLowerCase() : "";
                  const key = uuid || id || title || url;
                  if (!key || seenKeys.has(key)) return;
                  seenKeys.add(key);
                  if (title && title.length > 3) {
                    if (seenKeys.has(`title:${title}`)) return;
                    seenKeys.add(`title:${title}`);
                  }
                  mergedVideos.push(v);
                };

                for (const v of currentVideos) addVid(v);
                for (const c of incomingChunks) {
                  const v = {
                    id: c.video_id || c.id,
                    title: c.video_title || c.title || "Video",
                    thumbnail: c.video_thumbnail || c.thumbnail || "",
                    url: c.video_url || c.url || (c.video_id ? `/storage/videos/${c.video_id}.mp4` : ""),
                    duration: c.video_duration || c.duration || "",
                  };
                  addVid(v);
                }
                assistantMsg.videos = mergedVideos;
              }
            } else if (chunk.type === "courses") {
              if (Array.isArray(chunk.courses) && chunk.courses.length > 0) {
                if (!Array.isArray(assistantMsg.checkLicCoursesData)) {
                  assistantMsg.checkLicCoursesData = [];
                }
                const existingCodes = new Set(
                  assistantMsg.checkLicCoursesData
                    .map((c) =>
                      String(
                        c?.data?.course?.CourseCode ||
                          c?.data?.course?.courseCode ||
                          c?.CourseCode ||
                          c?.courseCode ||
                          ""
                      ).toLowerCase()
                    )
                    .filter(Boolean)
                );
                chunk.courses.forEach((item) => {
                  const code = String(
                    item?.data?.course?.CourseCode ||
                      item?.data?.course?.courseCode ||
                      item?.CourseCode ||
                      item?.courseCode ||
                      ""
                  ).toLowerCase();
                  if (!code || !existingCodes.has(code)) {
                    if (code) existingCodes.add(code);
                    assistantMsg.checkLicCoursesData.push(item);
                  }
                });
                assistantMsg.courses = assistantMsg.checkLicCoursesData;
              }
            }

            setmessages((prev = []) => {
              const nextMsgs = [...prev];
              const idx = nextMsgs.findLastIndex((m) => m.role === "assistant");
              if (idx !== -1) {
                const finalCourses =
                  assistantMsg.checkLicCoursesData?.length > 0
                    ? assistantMsg.checkLicCoursesData
                    : nextMsgs[idx]?.checkLicCoursesData || [];
                nextMsgs[idx] = {
                  ...nextMsgs[idx],
                  ...assistantMsg,
                  checkLicCoursesData: finalCourses,
                  courses: finalCourses,
                };
              }
              return nextMsgs;
            });
          },
          isCaptainMode && isCaptainOrMaster ? "Captain" : ""
        );

        // Finalize citations appropriately in sections
        finalizeCitations();

        assistantMsg.isThinking = false;
        assistantMsg.isStreaming = false;
        setmessages((prev = []) => {
          const nextMsgs = [...prev];
          const idx = nextMsgs.findLastIndex((m) => m.role === "assistant");
          if (idx !== -1) {
            const finalCourses =
              assistantMsg.checkLicCoursesData?.length > 0
                ? assistantMsg.checkLicCoursesData
                : nextMsgs[idx]?.checkLicCoursesData || [];
            nextMsgs[idx] = {
              ...nextMsgs[idx],
              ...assistantMsg,
              checkLicCoursesData: finalCourses,
              courses: finalCourses,
            };
          }
          return nextMsgs;
        });

        if (typeof fetchSessions === "function") {
          fetchSessions("", true);
        }

        // Navigate and sync session ID bit later AFTER getting the full response
        if (activeSessionId) {
          setCurrentSessionId?.(activeSessionId);
        }
      } catch (error) {
        if (axios.isCancel(error) || error.name === "CanceledError" || error.message === "canceled" || error.name === "AbortError") {
          setmessages((prev = []) => prev.filter((m) => !m.isThinking && m.content !== ""));
        } else {
          setmessages((prev = []) => {
            const clean = prev.filter((m) => !m.isThinking);
            return clean.concat({
              role: "assistant",
              content: `Error: ${error.message}`,
              timestamp: new Date().toISOString(),
            });
          });
        }
      } finally {
        setDisableNewChat(false);
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
      }
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Reset target value so the same file can be uploaded again
    event.target.value = null;

    // Store the selected file for later sending when user clicks send
    setSelectedFile(file);
  };

  const showWelcome =
    !currentSessionId && (!messages || messages.length === 0);

  return (
    <div className="bg-bg-light1 flex-1 min-w-0 w-full flex flex-col h-full overflow-hidden pt-2">
      {/* Messages Feed, Loading State, or Welcome Screen */}
      {loading && (!messages || messages.length === 0) ? (
        <div className="flex-1 flex items-center justify-center select-none">
          <div className="flex flex-col items-center gap-2.5 text-primary">
            <div className="w-7 h-7 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <span className="text-xs font-medium text-text-secondary">Loading chat...</span>
          </div>
        </div>
      ) : showWelcome ? (
        <WelcomeChatScreen />
      ) : (
        <div className="flex-1 min-h-0 flex overflow-hidden relative">
          <div
            key={currentSessionId || "new-chat"}
            className="flex-1 overflow-y-auto pt-2 pb-4 px-3 sm:px-6 md:px-10 lg:px-12 flex flex-col gap-3 sm:gap-3.5 w-full max-w-4xl mx-auto"
          >
            {messages?.map((msg, index) => {
              const raw_videos =
                msg?.videos ||
                msg?.video_suggestions ||
                msg?.videos_suggestions ||
                msg?.metadata?.videos ||
                [];
              const seenVideoKeys = new Set();
              const videos_suggestions = raw_videos.filter((v) => {
                const url = v?.url || v?.Url || v?.videourl || v?.video_url || "";
                const id = v?.id || v?.Id || v?.video_id || "";
                const title = (v?.title || v?.Title || "").trim().toLowerCase();
                const uuidMatch = (url + " " + id).match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
                const uuid = uuidMatch ? uuidMatch[0].toLowerCase() : "";
                const key = uuid || id || title || url;
                if (!key || seenVideoKeys.has(key)) return false;
                seenVideoKeys.add(key);
                if (title && title.length > 3) {
                  if (seenVideoKeys.has(`title:${title}`)) return false;
                  seenVideoKeys.add(`title:${title}`);
                }
                return true;
              });

              const raw_images =
                msg?.images ||
                msg?.images_suggestions ||
                msg?.image_suggestions ||
                msg?.metadata?.images ||
                [];
              const seenImageKeys = new Set();
              const images_suggestions = raw_images.filter((img) => {
                if (!img) return false;
                const url = img?.url || img?.Url || img?.thumbnail || img?.Thumbnail || img?.src || img?.image_url || img?.imageUrl || "";
                const id = img?.id || img?.Id || "";
                const b64 = img?.base64 && typeof img?.base64 === "string" && img.base64.startsWith("data:image/") ? img.base64 : "";
                if (!b64 && !url) return false;

                const title = (img?.title || img?.Title || img?.name || img?.Name || "").trim().toLowerCase();
                const cleanTitle = title.replace(/[^a-z0-9]+/g, " ").trim();
                const uuidMatch = (url + " " + id).match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
                const uuid = uuidMatch ? uuidMatch[0].toLowerCase() : (id ? id.toLowerCase() : "");
                const key = uuid || cleanTitle || url;
                if (!key || seenImageKeys.has(key)) return false;
                seenImageKeys.add(key);
                if (cleanTitle && cleanTitle.length > 3) {
                  if (seenImageKeys.has(`title:${cleanTitle}`)) return false;
                  seenImageKeys.add(`title:${cleanTitle}`);
                }
                return true;
              });

              const raw_pdfs =
                msg?.pdfs ||
                msg?.pdf_suggestions ||
                msg?.pdfs_suggestions ||
                msg?.metadata?.pdfs ||
                [];
              const seenPdfKeys = new Set();
              const pdf_suggestions = raw_pdfs.filter((pdf) => {
                const key = pdf?.url || pdf?.Url || pdf?.link || pdf?.Link || pdf?.file_url || pdf?.id || pdf?.Id || pdf?.title || pdf?.Title;
                if (!key || seenPdfKeys.has(key)) return false;
                seenPdfKeys.add(key);
                return true;
              });

              // Extract the exact user question associated with this assistant message
              let userQuestion = msg.question || msg.user_query || msg.query || "";
              if (!userQuestion && msg.role === "assistant") {
                for (let i = index - 1; i >= 0; i--) {
                  if (messages[i]?.role === "user" && messages[i]?.content) {
                    userQuestion = messages[i].content;
                    break;
                  }
                }
              }

              return msg.isThinking ? (
                <ThinkingBubble key={`thinking-${index}`} statusText={msg.statusText} />
              ) : (
                <ChatMessage
                  key={msg.id ? msg.id : `${currentSessionId || "chat"}-${index}-${msg.role || "msg"}`}
                  handleSend={handleSend}
                  setSearchQuery={setSearchQuery}
                  sessionId={currentSessionId}
                  msg={msg}
                  question={userQuestion}
                  userProfile={userProfile}
                  videos_suggestions={videos_suggestions}
                  images_suggestions={images_suggestions}
                  pdf_suggestions={pdf_suggestions}
                  onTopicClick={(topicCode, allTopics) => {
                    handleTopicClick(topicCode, allTopics || msg.topics);
                  }}
                />
              );
            })}
            <div ref={bottomRef} className="h-2 shrink-0" />
          </div>

          {/* Sources Drawer Side Panel */}
          {sourcesData.open && (
            <aside className="w-full sm:w-80 md:w-96 border-l border-border bg-bg-light1 dark:bg-bg-default flex flex-col h-full shrink-0 shadow-lg z-20 animate-slide-in">
              {/* Header */}
              <div className="p-3.5 sm:p-4 flex items-center justify-between border-b border-border/60 bg-bg-light2 dark:bg-bg-paper">
                <h3 className="text-sm font-bold text-primary flex items-center gap-1.5">
                  <span>
                    {sourcesData.topics.length === 1 && sourcesData.topics[0]?.index
                      ? `Source ${sourcesData.topics[0].index}`
                      : `${sourcesData.topics.length} Source${sourcesData.topics.length === 1 ? "" : "s"}`}
                  </span>
                </h3>
                <button
                  type="button"
                  onClick={() => setSourcesData((p) => ({ ...p, open: false, detailTopic: null }))}
                  className="p-1 rounded-lg text-text-secondary hover:text-text-primary hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer"
                  title="Close Sources"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Content */}
              <div className="flex-1 overflow-y-auto p-3 sm:p-4 flex flex-col gap-3">
                {sourcesData.loading ? (
                  <div className="py-12 flex flex-col items-center justify-center gap-2 text-primary">
                    <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                    <span className="text-xs text-text-secondary">Loading source details...</span>
                  </div>
                ) : sourcesData.detailTopic ? (
                  /* Detail View */
                  <div className="flex flex-col gap-2.5">
                    <button
                      type="button"
                      onClick={() => setSourcesData((p) => ({ ...p, detailTopic: null }))}
                      className="self-start flex items-center gap-1 text-xs font-semibold text-primary hover:underline cursor-pointer"
                    >
                      <ChevronLeft className="w-3.5 h-3.5" />
                      <span>Back to Sources</span>
                    </button>

                    <div className="bg-bg-light2 dark:bg-bg-paper rounded-xl border border-border/80 shadow-xs overflow-hidden flex flex-col">
                      <div className="p-3.5 flex flex-col gap-2.5">
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 rounded-full bg-primary text-white flex items-center justify-center text-xs font-bold shrink-0">
                            {sourcesData.detailTopic.index}
                          </div>
                          <h4 className="text-sm font-bold text-text-primary leading-snug">
                            {sourcesData.detailTopic.topicName}
                          </h4>
                        </div>

                        <div
                          className="text-xs text-text-primary leading-relaxed break-words [&>p]:my-1.5 [&>ul]:my-1.5 [&>ol]:my-1.5 [&>table]:my-2"
                          dangerouslySetInnerHTML={{
                            __html: sanitizeMarkdown(sourcesData.detailTopic.content),
                          }}
                        />
                      </div>

                      {sourcesData.detailTopic.courseName && (
                        <div className="px-3.5 py-2 bg-primary/5 dark:bg-primary/10 border-t border-border/50 text-[11px] font-semibold text-primary truncate">
                          Course: {sourcesData.detailTopic.courseName}
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  /* List View */
                  sourcesData.topics.map((topic) => (
                    <div
                      key={topic.code || topic.index}
                      className={`bg-bg-light2 dark:bg-bg-paper rounded-xl shadow-xs transition-all flex flex-col border ${
                        sourcesData.selectedTopicCode === topic.code
                          ? "border-primary shadow-sm"
                          : "border-border/80 hover:border-primary/50"
                      }`}
                    >
                      <div className="p-3 pb-1 flex items-start gap-2">
                        <div className="w-5 h-5 rounded-full bg-primary text-white flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">
                          {topic.index}
                        </div>
                        <h4 className="text-xs font-bold text-text-primary leading-snug">
                          {topic.topicName}
                        </h4>
                      </div>

                      <div className="px-3 pt-1 pb-1">
                        <p className="text-[11px] text-text-secondary line-clamp-3 leading-relaxed">
                          {String(topic.content || "").replace(/[#*`]/g, "")}
                        </p>
                      </div>

                      <div className="px-3 pb-2 pt-0.5">
                        <button
                          type="button"
                          onClick={() => setSourcesData((p) => ({ ...p, detailTopic: topic }))}
                          className="text-xs font-semibold text-primary hover:underline cursor-pointer"
                        >
                          Read More...
                        </button>
                      </div>

                      {topic.courseName && (
                        <div className="px-3 py-1.5 bg-primary/5 dark:bg-primary/10 border-t border-border/50 text-[10px] font-medium text-primary rounded-b-xl truncate">
                          Course: {topic.courseName}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </aside>
          )}
        </div>
      )}

      {/* Input Tray */}
      <div className="px-3 sm:px-6 md:px-10 lg:px-12 py-2 flex flex-col items-end shrink-0 w-full max-w-4xl mx-auto">
        {(selectedFile || isCaptainOrMaster) && (
          <div className="w-full flex items-center justify-between gap-2 mb-2">
            {selectedFile ? (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary/10 border border-primary/20 text-primary text-xs font-semibold">
                <span>📄 {selectedFile.name}</span>
                <button
                  type="button"
                  onClick={() => setSelectedFile(null)}
                  className="p-0.5 rounded hover:bg-primary/20 text-primary transition-colors leading-none cursor-pointer"
                >
                  ×
                </button>
              </div>
            ) : (
              <div />
            )}

            {isCaptainOrMaster && (
              <button
                type="button"
                onClick={() => setIsCaptainMode(!isCaptainMode)}
                className={`inline-flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1 rounded-full text-xs font-semibold cursor-pointer select-none transition-all border ${
                  isCaptainMode
                    ? "bg-primary/15 border-primary text-primary shadow-xs"
                    : "bg-black/5 dark:bg-white/5 border-border-theme text-text-secondary hover:text-text-primary"
                }`}
              >
                <span>⚓</span>
                <span className="hidden sm:inline">Captain Mode</span>
                <span className="sm:hidden">Captain</span>
                <span
                  className={`w-1.5 h-1.5 rounded-full ml-0.5 ${
                    isCaptainMode ? "bg-emerald-500 shadow-[0_0_5px_#22c55e]" : "bg-slate-400"
                  }`}
                />
              </button>
            )}
          </div>
        )}

        <div className="relative w-full flex items-center">
          <textarea
            ref={textareaRef}
            rows={1}
            disabled={disableNewChat}
            placeholder="Message Dolphin AI"
            value={searchQuery}
            onChange={(e) => {
              if (disableNewChat) return;
              setSearchQuery(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
            }}
            onKeyDown={(e) => {
              if (disableNewChat) {
                e.preventDefault();
                return;
              }
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                e.target.style.height = "auto";
                handleSend();
              }
            }}
            className={`w-full resize-none rounded-2xl py-3.5 sm:py-4 pl-16 sm:pl-20 pr-12 sm:pr-14 text-sm font-inherit bg-bg-paper text-text-primary border border-border-theme focus:outline-hidden focus:border-primary focus:ring-1 focus:ring-primary placeholder:text-text-placeholder1 transition-all max-h-32 ${
              disableNewChat ? "opacity-60 cursor-not-allowed bg-bg-default/60" : ""
            }`}
          />

          {/* File Upload Button */}
          <label className={`absolute left-2.5 sm:left-3 top-1/2 -translate-y-1/2 w-7 h-7 sm:w-8 sm:h-8 rounded-full flex items-center justify-center text-primary hover:bg-primary/10 transition-colors z-10 text-2xl font-light leading-none ${
            disableNewChat ? "opacity-40 cursor-not-allowed pointer-events-none" : "cursor-pointer"
          }`}>
            <input
              type="file"
              hidden
              disabled={disableNewChat}
              accept=".pdf,.docx,.txt,.xlsx,.csv"
              onChange={handleFileUpload}
            />
            <span>+</span>
          </label>

          {/* Message Indicator Icon */}
          <div className="absolute left-9 sm:left-11 top-1/2 -translate-y-1/2 pointer-events-none">
            <Message size={18} color={mode === "dark" ? "#1cb0f6" : "#106BA3"} />
          </div>

          {/* Stop / Send Button */}
          {disableNewChat ? (
            <button
              type="button"
              onClick={handleStop}
              className="absolute right-2.5 sm:right-3.5 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center hover:bg-primary-hover transition-colors z-10"
              aria-label="Stop response"
            >
              <StopIcon size={14} color="#ffffff" />
            </button>
          ) : (
            <button
              type="button"
              onClick={() => handleSend()}
              className="absolute right-2.5 sm:right-3.5 top-1/2 -translate-y-1/2 w-8 h-8 rounded-lg flex items-center justify-center text-primary hover:bg-primary/10 transition-colors z-10"
              aria-label="Send message"
            >
              <SendIcon size={18} color={mode === "dark" ? "#1989D0" : "#106BA3"} />
            </button>
          )}
        </div>

        <p className="text-[0.65rem] sm:text-[0.68rem] font-normal text-center px-2 py-1.5 text-text-caption leading-relaxed m-0 w-full">
          This AI-generated content is for educational purposes only and may not
          reflect the most current regulations or company policies. Always
          verify with official sources and your organization’s safety management
          system (SMS) before applying in practice.
        </p>
      </div>
    </div>
  );
};

export default ChatWindow;
