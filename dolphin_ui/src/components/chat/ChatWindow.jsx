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
import { ensureSession, sendMessage } from "../../api/fetchApi";
import ChatMessage from "./ChatMessage";
import { useThemeMode } from "../../context/ThemeModeContext";
import { Message } from "../../assets/svgIcons/message";
import { Saveoutlined } from "../../assets/svgIcons/SaveIconOutlined";
import DolphinIconW from "../../assets/images/dolphin_w.png";
import { getContentWidth } from "../../theme/layoutScale";

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
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const { mode } = useThemeMode();

  const bottomRef = useRef(null);

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

    if (!messageText.trim()) return;

    const userMessage = {
      role: "user",
      content: messageText.trim(),
      timestamp: new Date().toISOString(),
    };

    setmessages((prev = []) => [...prev, userMessage]);
    setSearchQuery("");

    setmessages((prev = []) => [
      ...prev,
      { role: "assistant", isThinking: true },
    ]);

    const resolvedUserId = userId || localStorage.getItem("userId") || "guest";
    const sessionId = currentSessionId
      ? await ensureSession(currentSessionId, resolvedUserId)
      : await ensureSession(null, resolvedUserId);

    setCurrentSessionId(sessionId);

    setDisableNewChat(true);
    const response = await sendMessage(sessionId, userMessage.content, resolvedUserId);
    setDisableNewChat(false);
    if (typeof fetchSessions === "function") {
      fetchSessions();
    }
    setmessages((prev = []) =>
      prev
        .filter((m) => !m.isThinking)
        .concat({
          ...response,
          category: response?.metadata?.category,
          role: "assistant",
        })
    );

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
              padding: "20px 56px 20px 50px",
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

          <Box
            sx={{
              display: "flex",
              position: "absolute",
              transform: "translateY(-50%)",
              left: 16,
              top: "50%",
            }}
          >
            <Message
              size={22}
              color={mode === "dark" ? "#1cb0f6" : "#106BA3"}
            />
          </Box>

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
