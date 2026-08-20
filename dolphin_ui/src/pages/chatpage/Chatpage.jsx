import { Grid, useMediaQuery, useTheme } from "@mui/material";
import React, { useEffect, useState } from "react";
import ChatSideBar from "../../components/chat/ChatSideBar";
import ChatWindow from "../../components/chat/ChatWindow";
import { fetchHealth } from "../../api/fetchApi";
import axios from "axios";
import Header from "../../components/header/Header";

const APP_URL = process.env.REACT_APP_BASE_URL || "http://localhost:8000";

const Chatpage = ({ userId, setUserId, onLogout }) => {
  const [sessionData, setSessionData] = useState(null);
  const [activeIndex, setActiveIndex] = useState(null);

  const [currentSessionData, setCurrentSessionData] = useState(null);
  const [currentSessionId, setCurrentSessionId] = useState(null);

  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionDetailsLoading, setSessionDetailsLoading] = useState(false);

  const [messages, setmessages] = useState([]);
  const [disableNewChat, setDisableNewChat] = useState(false);

  const [sidebarOpen, setSidebarOpen] = useState(false);

  const fetchSessions = async (searchTerm = "") => {
    try {
      setSessionsLoading(true);
      const currentUserId = userId || localStorage.getItem("userId") || "guest";
      const response = await axios.get(`${APP_URL}/sessions`, {
        params: {
          user_id: String(currentUserId),
          ...(searchTerm ? { search: searchTerm } : {}),
        },
        withCredentials: true,
      });

      if (response.status === 200) {
        setSessionData(response.data);
      }
    } catch (error) {
      console.error("Unable to fetch sessions", error);
    } finally {
      setSessionsLoading(false);
    }
  };

  const selectSession = async (sessionId) => {
    try {
      setSessionDetailsLoading(true);
      const currentUserId = userId || localStorage.getItem("userId") || "guest";
      const response = await axios.get(`${APP_URL}/sessions/${sessionId}`, {
        params: {
          user_id: String(currentUserId),
        },
        withCredentials: true,
      });

      const data = response.data;

      setCurrentSessionId(data.session_id);
      setCurrentSessionData(data);
    } catch (error) {
      console.error("Unable to load session", error);
    } finally {
      setSessionDetailsLoading(false);
    }
  };

  useEffect(() => {
    const health = fetchHealth();
    if (health) {
      fetchSessions();
    } else {
      setUserId(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const isTab = useMediaQuery(theme.breakpoints.down("md"));
  return (
    <Grid container height="100vh" width="100vw" flexDirection="column">
      <Grid item xs={12} sx={{ height: "10vh" }}>
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
      </Grid>

      <Grid item xs={12} sx={{ height: "90vh", display: "flex" }}>
        {!isMobile && !isTab && (
          <ChatSideBar
            sessionData={sessionData}
            loading={sessionsLoading}
            activeIndex={activeIndex}
            setActiveIndex={setActiveIndex}
            selectSession={selectSession}
            sidebarOpen={sidebarOpen}
            setSidebarOpen={setSidebarOpen}
            fetchSessions={fetchSessions}
          />
        )}

        <ChatWindow
          userId={userId}
          currentSessionData={currentSessionData}
          currentSessionId={currentSessionId}
          setCurrentSessionId={setCurrentSessionId}
          activeIndex={activeIndex}
          loading={sessionDetailsLoading}
          fetchSessions={fetchSessions}
          messages={messages}
          setmessages={setmessages}
          setDisableNewChat={setDisableNewChat}
        />
      </Grid>
    </Grid>
  );
};

export default Chatpage;
