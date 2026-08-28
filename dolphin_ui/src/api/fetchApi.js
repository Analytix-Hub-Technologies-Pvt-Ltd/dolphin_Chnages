import axios from "axios";

const APP_URL = process.env.REACT_APP_BASE_URL || "http://localhost:8000";

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
    const resolvedUserId = userId || localStorage.getItem("userId") || "guest";
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
    const resolvedUserId = userId || localStorage.getItem("userId") || "guest";
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
    const resolvedUserId = userId || localStorage.getItem("userId") || "guest";
    const response = await fetch(`${APP_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify({
        content: messageText,
        session_id: sessionId,
        user_id: String(resolvedUserId),
        role: role || "",
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

