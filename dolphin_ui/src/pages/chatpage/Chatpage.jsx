import { useMediaQuery, useTheme } from "@mui/material";
import React, { useEffect, useState, useCallback, useMemo, useRef } from "react";
import ChatSideBar from "../../components/chat/ChatSideBar";
import ChatWindow from "../../components/chat/ChatWindow";
import { fetchHealth } from "../../api/fetchApi";
import { apiGet } from "../../api/client";
import Header from "../../components/header/Header";
import MainLayout from "../../layouts/MainLayout";
import { APP_URL } from "../../api/config";

const Chatpage = ({ userId, setUserId, onLogout }) => {
  const [sessionData, setSessionData] = useState([]);
  const [activeIndex, setActiveIndex] = useState(null);
  const [currentSessionData, setCurrentSessionData] = useState(null);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionDetailsLoading, setSessionDetailsLoading] = useState(false);
  const [messages, setmessages] = useState([]);
  const [disableNewChat, setDisableNewChat] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);

  const fetchInProgressRef = useRef(false);
  const initialLoadRef = useRef(false);

  const fetchSessions = useCallback(async (searchTerm = "", isBackground = false) => {
    if (fetchInProgressRef.current) return;

    try {
      fetchInProgressRef.current = true;
      if (!isBackground) setSessionsLoading(true);

      const userId = localStorage.getItem("user_id");

      const data = await apiGet(`${APP_URL}/sessions`, {
        query: {
          user_id: userId,
          ...(searchTerm && { search: searchTerm }),
        },
      });

      if (Array.isArray(data)) {
        setSessionData((prevData) => {
          const prevMap = new Map(prevData.map(s => [s.session_id, s]));
          const newData = data.map(s => {
            const existing = prevMap.get(s.session_id);
            return existing && existing.title !== s.title ? { ...s, title: s.title } : (existing || s);
          });
          if (prevData.length === newData.length && prevData.every((item, i) => item.session_id === newData[i].session_id && item.title === newData[i].title)) {
            return prevData;
          }
          return newData;
        });
      }
    } catch (error) {
      console.error("Unable to fetch sessions", error);
      if (error?.status === 401 && onLogout) {
        onLogout();
      }
    } finally {
      if (!isBackground) setSessionsLoading(false);
      fetchInProgressRef.current = false;
    }
  }, [onLogout]);

  const selectSession = useCallback(async (sessionId) => {
    if (!sessionId) return;

    try {
      setSessionDetailsLoading(true);

      const userId = localStorage.getItem("user_id");

      const data = await apiGet(`${APP_URL}/sessions/${sessionId}`, {
        query: { user_id: userId },
      });


      setCurrentSessionId(data.session_id);
      setCurrentSessionData(data);
      setmessages(data.messages || []);

      // Persist session ID for refresh
      localStorage.setItem("active_session_id", data.session_id);
    } catch (error) {
      console.error("Unable to load session", error);
      if (error?.status === 401 && onLogout) {
        onLogout();
      }
    } finally {
      setSessionDetailsLoading(false);
    }
  }, [onLogout]);

  useEffect(() => {
    if (initialLoadRef.current) return;
    initialLoadRef.current = true;

    const loadHealth = async () => {
      try {
        const health = await fetchHealth();
        if (health) {
          await fetchSessions();

          // Auto-load last active session
          const lastSessionId = localStorage.getItem("active_session_id");
          if (lastSessionId) {
            await selectSession(lastSessionId);
          }
        } else {
          if (onLogout) {
            onLogout();
          } else if (typeof setUserId === "function") {
            setUserId(null);
          }
        }
      } catch (err) {
        console.error("Failed to check health / load sessions:", err);
      } finally {
        setIsInitializing(false);
      }
    };

    loadHealth();
  }, [fetchSessions, setUserId, selectSession, onLogout]);

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const isTab = useMediaQuery(theme.breakpoints.down("md"));

  // Memoize sidebar props with stable references
  const sidebarProps = useMemo(() => ({
    sessionData,
    loading: sessionsLoading,
    activeIndex,
    setActiveIndex,
    selectSession,
    sidebarOpen,
    setSidebarOpen,
    fetchSessions,
    currentSessionId,
  }), [sessionData, sessionsLoading, activeIndex, selectSession, sidebarOpen, fetchSessions, currentSessionId]);

  // Memoize chat window props
  const chatWindowProps = useMemo(() => ({
    currentSessionData,
    currentSessionId,
    setCurrentSessionId,
    activeIndex,
    loading: sessionDetailsLoading || isInitializing,
    fetchSessions,
    messages,
    setmessages,
    setDisableNewChat,
    setActiveIndex,
    selectSession,
  }), [currentSessionData, currentSessionId, activeIndex, sessionDetailsLoading, isInitializing, fetchSessions, messages, setmessages, setActiveIndex, selectSession]);

  return (
    <MainLayout
      header={
        <Header
          onLogout={onLogout}
          setSessionData={setSessionData}
          setCurrentSessionData={setCurrentSessionData}
          setActiveIndex={setActiveIndex}
          setCurrentSessionId={setCurrentSessionId}
          setmessages={setmessages}
          disableNewChat={disableNewChat}
          sessionData={sessionData}
          loading={sessionsLoading}
          activeIndex={activeIndex}
          selectSession={selectSession}
          sidebarOpen={sidebarOpen}
          setSidebarOpen={setSidebarOpen}
          fetchSessions={fetchSessions}
        />
      }
      leftPanel={<ChatSideBar {...sidebarProps} />}
      contentPanel={<ChatWindow {...chatWindowProps} />}
    />
  );
};

export default Chatpage;