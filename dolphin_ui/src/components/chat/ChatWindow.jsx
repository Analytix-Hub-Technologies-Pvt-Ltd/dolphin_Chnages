import {
  Box,
  Typography,
  IconButton,
  TextareaAutosize,
} from "@mui/material";
import React, { useEffect, useRef, useState } from "react";
import { SendIcon } from "../../assets/svgIcons/sendIcon";
import { marked } from "marked";
import DOMPurify from "dompurify";
import WelcomeChatScreen from "./WelcomeChatScreen";
import { ensureSession, sendMessage, checkDocumentGaps, sendMessageStream, checkDocumentGapsStream } from "../../api/fetchApi";
import ChatMessage from "./ChatMessage";
import { useThemeMode } from "../../context/ThemeModeContext";
import { Message } from "../../assets/svgIcons/message";
import { Saveoutlined } from "../../assets/svgIcons/SaveIconOutlined";
import DolphinIconW from "../../assets/images/dolphin_w.png";
import { getContentWidth } from "../../theme/layoutScale";
import { StopIcon } from "../../assets/svgIcons/StopIcon";
import axios from "axios";

export const sanitizeMarkdown = (markdownText) => {
  if (!markdownText) return "";

  // Pre-process tab-separated tables if any into standard markdown tables
  const lines = markdownText.split("\n");
  let inTabTable = false;
  let maxCols = 0;
  let processedLines = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.includes("\t")) {
      const rawCells = line.split("\t").map((c) => c.trim());
      if (!inTabTable) {
        inTabTable = true;
        maxCols = Math.max(rawCells.length, 2);
        // Pad header if needed
        while (rawCells.length < maxCols) rawCells.push("");
        const mdHeader = `| ${rawCells.join(" | ")} |`;
        const mdSep = `| ${rawCells.map(() => "---").join(" | ")} |`;
        processedLines.push(mdHeader);
        processedLines.push(mdSep);
      } else {
        while (rawCells.length < maxCols) rawCells.push("");
        const mdRow = `| ${rawCells.slice(0, maxCols).join(" | ")} |`;
        processedLines.push(mdRow);
      }
    } else {
      inTabTable = false;
      maxCols = 0;
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

  return DOMPurify.sanitize(rawHtml, { USE_PROFILES: { html: true } });
};

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
  const { mode } = useThemeMode();

  const bottomRef = useRef(null);
  const abortControllerRef = useRef(null);

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

  const ThinkingBubble = () => (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1,
        // p: 2,
        borderRadius: 5,
        width: "fit-content",
      }}
    >
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          width: 50,
          height: 50,
          borderRadius: 60,
          backgroundColor: "primary.main",
        }}
      >
        <Box
          component="img"
          src={DolphinIconW}
          alt="Dolphin"
          sx={{ width: 30, height: 30 }}
        />
      </Box>

      <Typography
        variant="body1"
        sx={{
          fontWeight: 700,
          backgroundColor: "background.chatbackground",
          p: 1.5,
          borderRadius: 5,
          color: "primary.main",
          "& span": {
            fontSize: 20,
            animation: "blink 1.4s infinite both",
          },
          "& span:nth-of-type(2)": {
            animationDelay: "0.2s",
          },
          "& span:nth-of-type(3)": {
            animationDelay: "0.4s",
          },
          "@keyframes blink": {
            "0%": { opacity: 0 },
            "20%": { opacity: 1 },
            "100%": { opacity: 0 },
          },
        }}
      >
        Dolphin is thinking
        <span>.</span>
        <span>.</span>
        <span>.</span>
      </Typography>

      <div ref={bottomRef} />
    </Box>
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages]);

  useEffect(() => {
    setmessages(
      Array.isArray(currentSessionData?.messages)
        ? currentSessionData.messages
        : []
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSessionData]);

  const handleSend = async (queryOverride) => {
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
          if (chunk.type === "content") {
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

    const resolvedUserId = userId || localStorage.getItem("userId") || "guest";
    const sessionId = currentSessionId
      ? await ensureSession(currentSessionId, resolvedUserId)
      : await ensureSession(null, resolvedUserId);

    setCurrentSessionId(sessionId);

    // Otherwise, text-only normal chat message
    if (messageText.trim()) {
      const userMessage = {
        role: "user",
        content: messageText.trim(),
        timestamp: new Date().toISOString(),
      };

      setmessages((prev = []) => [...prev, userMessage]);
      setSearchQuery("");

      let assistantMsg = {
        role: "assistant",
        content: "",
        isThinking: true,
        timestamp: new Date().toISOString(),
        videos: [],
        images: [],
        pdfs: [],
        question_suggestions: [],
        company_answer: "",
        metadata: {},
      };

      setmessages((prev = []) => [...prev, assistantMsg]);
      setDisableNewChat(true);
      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        await sendMessageStream(
          sessionId,
          messageText.trim(),
          resolvedUserId,
          controller.signal,
          (chunk) => {
            if (chunk.type === "content") {
              assistantMsg.isThinking = false;
              assistantMsg.content += chunk.token;
            } else if (chunk.type === "suggestions") {
              assistantMsg.question_suggestions = chunk.question_suggestions || [];
            } else if (chunk.type === "media") {
              assistantMsg.videos = chunk.videos || [];
              assistantMsg.images = chunk.images || [];
              assistantMsg.pdfs = chunk.pdfs || [];
            } else if (chunk.type === "company_content") {
              assistantMsg.company_answer = chunk.content;
            }

            setmessages((prev = []) => {
              const nextMsgs = [...prev];
              const idx = nextMsgs.findLastIndex((m) => m.role === "assistant");
              if (idx !== -1) {
                nextMsgs[idx] = { ...assistantMsg };
              }
              return nextMsgs;
            });
          }
        );

        if (typeof fetchSessions === "function") {
          fetchSessions();
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
    (currentSessionData && currentSessionData.messages?.length === 0) ||
    messages?.length === 0 ||
    (activeIndex === null && !currentSessionId);

  const { fontLevel } = useThemeMode();
  return (
    <Box
      sx={{
        width: { xs: "100vw", md: getContentWidth(fontLevel) },
        backgroundColor: "background.light1",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          px: { xs: 1.5, sm:4, md: 7 },
          py: { xs: 1, md: 2 },
        }}
      >
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
            width: { xs: "50%", md: "80%" },
          }}
        >
          <Message size={22} color={mode === "dark" ? "#1cb0f6" : "#106BA3"} />

          <Typography
            variant="h4"
            sx={{
              color: "text.primary",
              width: "80%",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              fontWeight: 700,
            }}
          >
            {currentSessionData
              ? currentSessionData?.title?.charAt(0)?.toUpperCase() +
                currentSessionData?.title?.slice(1)
              : "New Chat"}
          </Typography>
        </Box>
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
            cursor: "pointer",
          }}
        >
          <Saveoutlined
            size={22}
            color={mode === "dark" ? "#1cb0f6" : "#106BA3"}
          />
          {/* <SaveIcon size={22} color={mode === "dark" ? "#1cb0f6" : "#106BA3"} /> */}
          <Typography
            variant="body1"
            sx={{
              color: "text.primary",
            }}
          >
            {"Save Chat"}
          </Typography>
        </Box>
      </Box>

      {showWelcome ? (
        <WelcomeChatScreen />
      ) : (
        <Box
          sx={{
            flex: 1,
            overflowY: "auto",
            pt: 1,
            pb: 2,
            px: {xs:1,md:5},
            display: "flex",
            flexDirection: "column",
            gap: 2,
          }}
        >
          {messages?.map((msg, index) => {
            const raw_videos =
              msg?.videos ||
              msg?.video_suggestions ||
              msg?.metadata?.videos ||
              [];
            const seenVideoKeys = new Set();
            const videos_suggestions = raw_videos.filter((v) => {
              const key = v?.url || v?.Url || v?.videourl || v?.id || v?.Id || v?.title || v?.Title;
              if (!key || seenVideoKeys.has(key)) return false;
              seenVideoKeys.add(key);
              return true;
            });

            const raw_images = msg?.images || msg?.metadata?.images || [];
            const seenImageKeys = new Set();
            const images_suggestions = raw_images.filter((img) => {
              const key = img?.url || img?.Url || img?.id || img?.Id || img?.base64;
              if (!key || seenImageKeys.has(key)) return false;
              seenImageKeys.add(key);
              return true;
            });

            const raw_pdfs = msg?.pdfs || msg?.metadata?.pdfs || [];
            const seenPdfKeys = new Set();
            const pdf_suggestions = raw_pdfs.filter((pdf) => {
              const key = pdf?.url || pdf?.Url || pdf?.id || pdf?.Id || pdf?.title || pdf?.Title;
              if (!key || seenPdfKeys.has(key)) return false;
              seenPdfKeys.add(key);
              return true;
            });

            return msg.isThinking ? (
              <ThinkingBubble key="thinking" />
            ) : (
              <ChatMessage
                handleSend={handleSend}
                setSearchQuery={setSearchQuery}
                sessionId={currentSessionId}
                msg={msg}
                videos_suggestions={videos_suggestions}
                images_suggestions={images_suggestions}
                pdf_suggestions={pdf_suggestions}
              />
            );
          })}
        </Box>
      )}

      <Box
        sx={{
          px:{ xs:1,sm:4,md:7},
          py: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-end",
        }}
      >
        {selectedFile && (
          <Box
            sx={{
              alignSelf: "flex-start",
              display: "flex",
              alignItems: "center",
              gap: 1.5,
              mb: 1.5,
              p: "6px 12px",
              borderRadius: "8px",
              backgroundColor: mode === "dark" ? "rgba(28, 176, 246, 0.12)" : "rgba(16, 107, 163, 0.08)",
              border: "1px solid",
              borderColor: mode === "dark" ? "rgba(28, 176, 246, 0.3)" : "rgba(16, 107, 163, 0.2)",
              width: "fit-content",
            }}
          >
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                color: mode === "dark" ? "#1cb0f6" : "#106BA3",
                fontSize: "0.85rem",
              }}
            >
              📄 {selectedFile.name}
            </Typography>
            <IconButton
              size="small"
              onClick={() => setSelectedFile(null)}
              sx={{
                p: 0.25,
                color: mode === "dark" ? "#1cb0f6" : "#106BA3",
                "&:hover": {
                  backgroundColor: mode === "dark" ? "rgba(28, 176, 246, 0.2)" : "rgba(16, 107, 163, 0.15)",
                },
              }}
            >
              <span style={{ fontSize: 16, fontWeight: "bold", lineHeight: 1 }}>×</span>
            </IconButton>
          </Box>
        )}
        <Box
          sx={{
            position: "relative",
            width: "100%",
            display: "flex",
            alignItems: "center",

            "& textarea": {
              width: "100%",
              resize: "none",
              borderRadius: 2,
              padding: "20px 56px 20px 82px",
              fontSize: 14,
              fontFamily: "inherit",
              maxHeight: 120,
              overflowY: "auto",
              boxSizing: "border-box",

              // ✅ theme background
              backgroundColor: "background.paper",
              color: "text.primary",

              border: "1px solid",
              borderColor: "divider",
              outline: "none",

              scrollbarWidth: "thin",
              scrollbarColor: "primary.main transparent",

              "&::placeholder": {
                color: "text.placeholder1",
                opacity: 1,
              },

              "&::-webkit-scrollbar": {
                width: 6,
              },
              "&::-webkit-scrollbar-thumb": {
                backgroundColor: "primary.main",
                borderRadius: 2,
              },
              "&::-webkit-scrollbar-button": {
                display: "none",
              },
            },
          }}
        >
          <TextareaAutosize
            minRows={1}
            maxRows={6}
            placeholder="Message Dolphin AI"
            sx={{ color: "text.placeholder1" }}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />

          <IconButton
            component="label"
            sx={{
              position: "absolute",
              left: 12,
              top: "50%",
              transform: "translateY(-50%)",
              color: mode === "dark" ? "#1cb0f6" : "#106BA3",
              zIndex: 10,
              width: 32,
              height: 32,
              "&:hover": {
                backgroundColor: mode === "dark" ? "rgba(28, 176, 246, 0.15)" : "rgba(16, 107, 163, 0.15)",
              }
            }}
          >
            <input
              type="file"
              hidden
              accept=".pdf,.docx,.txt,.xlsx,.csv"
              onChange={handleFileUpload}
            />
            <span style={{ fontSize: 24, fontWeight: 300, lineHeight: 1, position: "relative", top: -1 }}>+</span>
          </IconButton>

          <Box
            sx={{
              display: "flex",
              position: "absolute",
              transform: "translateY(-50%)",
              left: 48,
              top: "50%",
            }}
          >
            <Message
              size={22}
              color={mode === "dark" ? "#1cb0f6" : "#106BA3"}
            />
          </Box>

          {disableNewChat ? (
            <IconButton
              onClick={handleStop}
              sx={{
                position: "absolute",
                right: 16,
                top: "50%",
                transform: "translateY(-50%)",
                height: 32,
                width: 32,
                borderRadius: "50%",
                backgroundColor: mode === "dark" ? "#1cb0f6" : "#106BA3",
                color: "#ffffff",
                "&:hover": {
                  backgroundColor: mode === "dark" ? "#1577b8" : "#0d5683",
                },
                zIndex: 10,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <StopIcon
                size={16}
                color="#ffffff"
              />
            </IconButton>
          ) : (
            <IconButton
              onClick={() => {
                handleSend();
              }}
              sx={{
                position: "absolute",
                right: 16,
                top: "50%",
                transform: "translateY(-50%)",
                height: 36,
                width: 36,
                borderRadius: 2,
              }}
            >
              <SendIcon
                size={20}
                color={mode === "dark" ? "#1989D0" : "#106BA3"}
              />
            </IconButton>
          )}
        </Box>
        <Typography
          variant="caption"
          sx={{
            fontWeight: 500,
            textAlign: "center",
            p: 1,
            color: "text.caption",
          }}
        >
          This AI-generated content is for educational purposes only and may not
          reflect the most current regulations or company policies. Always
          verify with official sources and your organization’s safety management
          system (SMS) before applying in practice.
        </Typography>
      </Box>
    </Box>
  );
};

export default ChatWindow;
