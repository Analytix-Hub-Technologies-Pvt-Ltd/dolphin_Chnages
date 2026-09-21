import axios from "axios";
import APP_URL from "../config/apiConfig";

export const fetchHealth = async () => {
  try {
    const resp = await axios.get(`${APP_URL}/api/v1/health`, {
      withCredentials: true,
    });
    return resp.status === 200;
  } catch (error) {
    return false;
  }
};

export const createSession = async (userId) => {
  try {
    const resolvedUserId =
      userId ||
      localStorage.getItem("userId") ||
      localStorage.getItem("user_id") ||
      "guest";
    const response = await axios.post(
      `${APP_URL}/sessions`,
      {
        user_id: String(resolvedUserId),
      },
      {
        headers: {
          "Content-Type": "application/json",
        },
        withCredentials: true,
      }
    );

    return response.data;
  } catch (error) {
    console.error("[Session] Error creating session:", error.response?.data || error.message);
    const detail = error.response?.data?.detail || error.response?.data?.message || "Unable to create a new session";
    throw new Error(detail);
  }
};

export const ensureSession = async (currentSessionId, userId) => {
  if (currentSessionId) return currentSessionId;
  const session = await createSession(userId);
  return session.session_id;
};

export const sendMessage = async (sessionId, messageText, userId, signal, role = "") => {
  try {
    const resolvedUserId =
      userId ||
      localStorage.getItem("userId") ||
      localStorage.getItem("user_id") ||
      "guest";
    const response = await axios.post(
      `${APP_URL}/chat`,
      {
        content: messageText,
        session_id: sessionId,
        user_id: String(resolvedUserId),
        role: role || "",
      },
      {
        headers: {
          "Content-Type": "application/json",
        },
        withCredentials: true,
        signal,
      }
    );

    return response.data;
  } catch (error) {
    console.error("[Chat] Failed to send message", error);
    const errMsg =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.response?.data ||
      error.message ||
      "Something went wrong. Please try again.";
    throw new Error(errMsg);
  }
};

export const sendMessageStream = async (sessionId, messageText, userId, signal, onChunk, role = "") => {
  try {
    const resolvedUserId =
      userId ||
      localStorage.getItem("userId") ||
      localStorage.getItem("user_id") ||
      "guest";
    const response = await fetch(`${APP_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "text/event-stream, application/json",
      },
      credentials: "include",
      body: JSON.stringify({
        content: messageText,
        session_id: sessionId,
        user_id: String(resolvedUserId),
        role: role || "",
        stream: true,
      }),
      signal,
    });

    if (!response.ok) {
      const errText = await response.text();
      let errMsg = "Failed to send message";
      try {
        const parsed = JSON.parse(errText);
        errMsg = parsed.detail || parsed.message || errMsg;
      } catch (e) {
        errMsg = errText || errMsg;
      }
      throw new Error(errMsg);
    }

    const contentType = response.headers.get("content-type") || "";

    // 1. Direct JSON response (Non-streaming backend)
    if (contentType.includes("application/json")) {
      const data = await response.json();
      onChunk(data);
      return;
    }

    // 2. Stream processing (SSE or raw chunked stream)
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let fullText = "";
    let receivedSse = false;

    const handleLine = (line) => {
      const cleanLine = line.trim();
      if (!cleanLine) return;

      const match = cleanLine.match(/^data:\s*(.*)$/);
      if (!match) return;

      receivedSse = true;
      const jsonStr = match[1];
      if (!jsonStr) return;

      try {
        const parsed = JSON.parse(jsonStr);
        onChunk(parsed);
      } catch (e) {
        if (jsonStr !== "[DONE]") {
          onChunk({ type: "content", token: jsonStr });
        }
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      const chunkText = decoder.decode(value, { stream: true });
      fullText += chunkText;
      buffer += chunkText;
      const lines = buffer.split("\n");
      buffer = lines.pop(); // keep last incomplete line

      for (const line of lines) handleLine(line);
    }

    // Flush what is left after the final newline, otherwise a stream whose last
    // "data:" event arrives without a trailing newline loses that event.
    if (buffer) handleLine(buffer);

    // Fallback: If no SSE "data: " headers were found but body contains JSON
    if (!receivedSse && fullText.trim()) {
      try {
        const parsed = JSON.parse(fullText.trim());
        onChunk(parsed);
      } catch (e) {
        // Fallback plain text
        onChunk({ type: "content", token: fullText.trim() });
      }
    }
  } catch (error) {
    console.error("[Chat] Failed to stream message", error);
    throw error;
  }
};


export const checkDocumentGaps = async (file, signal) => {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await axios.post(
      `${APP_URL}/companies/check-gaps`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        withCredentials: true,
        signal,
      }
    );
    return response.data;
  } catch (error) {
    console.error("[Gaps] Failed to perform gap analysis", error);
    const errMsg =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.response?.data ||
      error.message ||
      "Failed to analyze the document. Please try again.";
    throw new Error(errMsg);
  }
};

export const checkDocumentGapsStream = async (file, signal, onChunk) => {
  try {
    const formData = new FormData();
    formData.append("file", file);
    
    const response = await fetch(`${APP_URL}/companies/check-gaps?stream=true`, {
      method: "POST",
      body: formData,
      signal,
    });

    if (!response.ok) {
      const errText = await response.text();
      let errMsg = "Failed to analyze document";
      try {
        const parsed = JSON.parse(errText);
        errMsg = parsed.detail || parsed.message || errMsg;
      } catch (e) {
        errMsg = errText || errMsg;
      }
      throw new Error(errMsg);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // keep last incomplete line

      for (const line of lines) {
        const cleanLine = line.trim();
        if (!cleanLine.startsWith("data: ")) continue;

        const jsonStr = cleanLine.slice(6);
        try {
          const parsed = JSON.parse(jsonStr);
          onChunk(parsed);
        } catch (e) {
          console.error("Error parsing stream chunk:", e);
        }
      }
    }
  } catch (error) {
    console.error("[Gaps] Failed to stream gap analysis", error);
    throw error;
  }
};


export const deleteSession = async (sessionId) => {
  try {
    const response = await axios.delete(`${APP_URL}/sessions/${sessionId}`, {
      withCredentials: true,
    });
    return response.data;
  } catch (error) {
    console.error("[Session] Error deleting session:", error.response?.data || error.message);
    const detail = error.response?.data?.detail || error.response?.data?.message || "Unable to delete session";
    throw new Error(detail);
  }
};

export const submitMessageFeedback = async (feedbackData) => {
  try {
    const response = await fetch(`${APP_URL}/sessions/message-feedback`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify(feedbackData),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || "Failed to submit feedback");
    }

    return await response.json();
  } catch (error) {
    console.error("Error submitting feedback:", error);
    throw error;
  }
};

export const fetchTopicDetails = async (topicCode) => {
  try {
    const response = await fetch(`${APP_URL}/sessions/topic/${topicCode}`, {
      method: "GET",
      credentials: "include",
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error("Error fetching topic details:", error);
    throw error;
  }
};

export const saveSession = async (sessionId) => {
  const response = await fetch(`${APP_URL}/sessions/save/${sessionId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify({
      session_id: sessionId,
    }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.message || "Save failed");
  }

  return data;
};

export const getSavedSessions = async () => {
  const userId = localStorage.getItem("user_id") || localStorage.getItem("userId");

  if (!userId) {
    throw new Error("User ID not found");
  }

  const response = await fetch(`${APP_URL}/sessions/saved/${userId}`, {
    method: "GET",
    credentials: "include",
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.message || "Failed to fetch saved sessions");
  }

  return data;
};

export const checkLicCourses = async (param) => {
  try {
    const topicCode = param?.topic_code || "";
    const sourceCode =
      param?.source_code && param?.source_code !== topicCode
        ? param.source_code
        : (param?.course_code && param?.course_code !== topicCode ? param.course_code : undefined);

    const resolvedTopicCode = topicCode || param?.source_code || "";
    if (!resolvedTopicCode) return null;

    const payload = {
      topic_code: resolvedTopicCode,
      user_id: param?.user_id,
    };

    if (sourceCode) {
      payload.source_code = sourceCode;
    }

    const response = await fetch(`${APP_URL}/course/check-topic-course`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      return null;
    }

    return await response.json();
  } catch (error) {
    console.error("[Course] Error checking licensed courses:", error);
    return null;
  }
};
