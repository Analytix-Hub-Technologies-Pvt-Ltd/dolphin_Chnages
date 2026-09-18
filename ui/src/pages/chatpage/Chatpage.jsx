import React, { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useNavigate, useLocation, useParams } from "react-router-dom";
import ChatSideBar from "../../components/chat/ChatSideBar";
import ChatWindow from "../../components/chat/ChatWindow";
import { fetchHealth } from "../../api/fetchApi";
import axios from "axios";
import Header from "../../components/header/Header";
import APP_URL from "../../config/apiConfig";

const Chatpage = ({ userId, userRole, setUserId, onLogout }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { sessionId: routeSessionId, sessionSlug } = useParams();

  // Extract session ID from URL:
  // Handles /session=${sessionId} via :sessionSlug,
  // /session/${sessionId} via :sessionId,
  // or ?session=${sessionId} via query string
  const resolvedRouteSessionId = useMemo(() => {
    if (routeSessionId) return routeSessionId;
    if (sessionSlug) {
      if (sessionSlug.startsWith("session=")) {
        return sessionSlug.slice("session=".length);
      }
      return sessionSlug;
    }
    const searchParams = new URLSearchParams(location.search);
    return searchParams.get("session") || searchParams.get("sessionId") || null;
  }, [routeSessionId, sessionSlug, location.search]);

  const [sessionData, setSessionData] = useState(null);
  const [activeIndex, setActiveIndex] = useState(null);

  const [currentSessionData, setCurrentSessionData] = useState(null);
  const [currentSessionId, setCurrentSessionId] = useState(resolvedRouteSessionId || null);

  const currentSessionIdRef = useRef(currentSessionId);
  currentSessionIdRef.current = currentSessionId;

  const currentSessionDataRef = useRef(currentSessionData);
  currentSessionDataRef.current = currentSessionData;

  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionDetailsLoading, setSessionDetailsLoading] = useState(false);

  const [messages, setmessages] = useState([]);
  const [disableNewChat, setDisableNewChat] = useState(false);

  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [isDesktop, setIsDesktop] = useState(
    typeof window !== "undefined" ? window.innerWidth >= 768 : true
  );

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(window.innerWidth >= 768);
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Redirect unknown single-segment paths that are not session=...
  useEffect(() => {
    if (sessionSlug && !sessionSlug.startsWith("session=") && !routeSessionId) {
      navigate("/", { replace: true });
    }
  }, [sessionSlug, routeSessionId, navigate]);

  const fetchSessions = async (searchTerm = "", silent = false) => {
    try {
      if (!silent) {
        setSessionsLoading(true);
      }
      const currentUserId =
        userId ||
        localStorage.getItem("userId") ||
        localStorage.getItem("user_id") ||
        "guest";
      const response = await axios.get(`${APP_URL}/sessions`, {
        params: {
          user_id: String(currentUserId),
          ...(searchTerm ? { search: searchTerm } : {}),
        },
        withCredentials: true,
        timeout: 10000,
      });

      if (response.status === 200) {
        if (Array.isArray(response.data)) {
          setSessionData(response.data);
        } else if (response.data && Array.isArray(response.data.data)) {
          setSessionData(
            response.data.data.map((item) => ({
              session_id: item.session_id,
              title: item.title || item.chat_title || "New Chat",
              created_at: item.created_at || item.time,
              updated_at: item.updated_at || item.time,
              is_saved: Boolean(item.is_saved),
              message_count: item.message_count || 0,
            }))
          );
        } else {
          setSessionData([]);
        }
      }
    } catch (error) {
      console.error("Unable to fetch sessions", error);
      setSessionData((prev) => prev || []);
    } finally {
      if (!silent) {
        setSessionsLoading(false);
      }
    }
  };

  const selectSession = useCallback(
    (sessionId) => {
      if (!sessionId) {
        navigate("/");
        return;
      }
      if (resolvedRouteSessionId !== sessionId) {
        navigate(`/session=${sessionId}`);
      }
    },
    [navigate, resolvedRouteSessionId]
  );

  // Synchronize route with session selection on load, direct URL, or navigation
  useEffect(() => {
    // 1. Root path "/" (New Chat)
    if (!resolvedRouteSessionId) {
      currentSessionIdRef.current = null;
      currentSessionDataRef.current = null;
      setCurrentSessionId(null);
      setCurrentSessionData(null);
      setActiveIndex(null);
      setmessages([]);
      setSessionDetailsLoading(false);
      return;
    }

    // 2. If the active session in state is already matching this route and has data loaded, nothing to do!
    if (
      currentSessionIdRef.current === resolvedRouteSessionId &&
      currentSessionDataRef.current?.session_id === resolvedRouteSessionId
    ) {
      return;
    }

    // 3. Load the session for this route
    let isCancelled = false;
    currentSessionIdRef.current = resolvedRouteSessionId;
    setCurrentSessionId(resolvedRouteSessionId);
    currentSessionDataRef.current = null;
    setCurrentSessionData(null);
    setmessages([]);
    setSessionDetailsLoading(true);

    const loadSession = async () => {
      try {
        const currentUserId =
          userId ||
          localStorage.getItem("userId") ||
          localStorage.getItem("user_id") ||
          "guest";
        const response = await axios.get(`${APP_URL}/sessions/${resolvedRouteSessionId}`, {
          params: {
            user_id: String(currentUserId),
          },
          withCredentials: true,
        });

        if (isCancelled) return;

        const data = response.data;
        currentSessionIdRef.current = data.session_id;
        currentSessionDataRef.current = data;
        setCurrentSessionId(data.session_id);
        setCurrentSessionData(data);
        if (Array.isArray(data?.messages)) {
          setmessages((prev) => {
            const isSameSession = String(data.session_id) === String(currentSessionIdRef.current);
            if (!isSameSession || !Array.isArray(prev) || prev.length === 0) {
              return data.messages;
            }
            return data.messages.map((newMsg, idx) => {
              const oldMsg = prev[idx];
              if (!oldMsg || oldMsg.role !== newMsg.role) return newMsg;
              return {
                ...newMsg,
                checkLicCoursesData:
                  (newMsg.checkLicCoursesData && newMsg.checkLicCoursesData.length > 0)
                    ? newMsg.checkLicCoursesData
                    : (oldMsg.checkLicCoursesData || []),
                courses:
                  (newMsg.courses && newMsg.courses.length > 0)
                    ? newMsg.courses
                    : (oldMsg.courses || oldMsg.checkLicCoursesData || []),
                videos:
                  (newMsg.videos && newMsg.videos.length > 0)
                    ? newMsg.videos
                    : (oldMsg.videos || []),
                images:
                  (newMsg.images && newMsg.images.length > 0)
                    ? newMsg.images
                    : (oldMsg.images || []),
                pdfs:
                  (newMsg.pdfs && newMsg.pdfs.length > 0)
                    ? newMsg.pdfs
                    : (oldMsg.pdfs || []),
              };
            });
          });
        }
      } catch (error) {
        if (isCancelled) return;
        console.error("Unable to load session", error);
        if (error.response?.status === 404) {
          navigate("/", { replace: true });
        }
      } finally {
        if (!isCancelled) {
          setSessionDetailsLoading(false);
        }
      }
    };

    loadSession();

    return () => {
      isCancelled = true;
    };
  }, [resolvedRouteSessionId, userId, navigate]);

  // Keep active index in sync with currentSessionId whenever sessionData loads/updates
  useEffect(() => {
    if (currentSessionId && Array.isArray(sessionData)) {
      const idx = sessionData.findIndex(
        (s) => String(s.session_id) === String(currentSessionId)
      );
      if (idx !== -1 && idx !== activeIndex) {
        setActiveIndex(idx);
      }
    } else if (!currentSessionId) {
      setActiveIndex(null);
    }
  }, [currentSessionId, sessionData, activeIndex]);

  // Callback for ChatWindow when a new session is generated on the fly during chat (called AFTER streaming response completes)
  const handleSessionIdUpdate = useCallback(
    (newSessionId) => {
      if (!newSessionId) return;
      currentSessionIdRef.current = newSessionId;
      setCurrentSessionId(newSessionId);
      setCurrentSessionData((prev) => {
        const nextData = {
          ...(prev || {}),
          session_id: newSessionId,
          title: prev?.session_id === newSessionId ? prev.title : (prev?.title || "New Chat"),
        };
        currentSessionDataRef.current = nextData;
        return nextData;
      });
      if (resolvedRouteSessionId !== newSessionId) {
        navigate(`/session=${newSessionId}`, { replace: true });
      }
    },
    [resolvedRouteSessionId, navigate]
  );

  useEffect(() => {
    fetchSessions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  return (
    <div className="h-screen w-full flex flex-col overflow-hidden bg-bg-default text-text-primary">
      <div className="h-[10vh] min-h-[56px] max-h-[68px] w-full shrink-0">
        <Header
          userId={userId}
          userRole={userRole}
          onLogout={onLogout}
          setSessionData={setSessionData}
          setCurrentSessionData={setCurrentSessionData}
          setActiveIndex={setActiveIndex}
          setCurrentSessionId={handleSessionIdUpdate}
          setmessages={setmessages}
          disableNewChat={disableNewChat}
          sessionData={sessionData}
          loading={sessionsLoading}
          activeIndex={activeIndex}
          selectSession={selectSession}
          sidebarOpen={sidebarOpen}
          setSidebarOpen={setSidebarOpen}
          fetchSessions={fetchSessions}
          currentSessionId={currentSessionId}
        />
      </div>

      <div className="flex-1 min-h-0 w-full flex overflow-hidden">
        {isDesktop && (
          <ChatSideBar
            sessionData={sessionData}
            loading={sessionsLoading}
            activeIndex={activeIndex}
            setActiveIndex={setActiveIndex}
            selectSession={selectSession}
            sidebarOpen={sidebarOpen}
            setSidebarOpen={setSidebarOpen}
            fetchSessions={fetchSessions}
            currentSessionId={currentSessionId}
          />
        )}

        <ChatWindow
          userId={userId}
          currentSessionData={currentSessionData}
          currentSessionId={currentSessionId}
          setCurrentSessionId={handleSessionIdUpdate}
          activeIndex={activeIndex}
          loading={sessionDetailsLoading}
          fetchSessions={fetchSessions}
          messages={messages}
          setmessages={setmessages}
          setDisableNewChat={setDisableNewChat}
          disableNewChat={disableNewChat}
        />
      </div>
    </div>
  );
};

export default Chatpage;
