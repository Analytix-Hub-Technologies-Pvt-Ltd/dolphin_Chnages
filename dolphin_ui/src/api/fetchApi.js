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

export const sendMessage = async (sessionId, messageText, userId) => {
  try {
    const resolvedUserId = userId || localStorage.getItem("userId") || "guest";
    const response = await axios.post(
      `${APP_URL}/chat`,
      {
        content: messageText,
        session_id: sessionId,
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
