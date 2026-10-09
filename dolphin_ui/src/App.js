import { useEffect, useState } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import Members from "./pages/admin/Members.jsx";
import Login from "./pages/LoginSignup";
import Chatpage from "./pages/chatpage/Chatpage.jsx";
import ChatHistoryAdmin from "./pages/ChatHistoryAdmin.jsx";
import AdminPage from "./pages/admin/AdminPage.jsx";
import FeedbackPage from "./pages/feedback/FeedbackPage.jsx";
import './App.css'
import { clearChatHistoryCache } from "./api/chatHistoryCache";
import { logout } from "./api/apiAuth.js";
import { isFeedbackAuthorized, getCurrentUserEmail } from "./utils/feedbackAuth.js";
import { isTokenExpired } from "./utils/tokenUtils.js";

function App() {
  const [userId, setUserId] = useState(null);

  const [authLoading, setAuthLoading] = useState(true);
  const [userRole, setUserRole] = useState(null);
  const [userEmail, setUserEmail] = useState("");

  useEffect(() => {
    const storedUserId = localStorage.getItem("userId");
    const storedUserData = localStorage.getItem("userData");

    let parsedData = null;
    if (storedUserData) {
      try {
        parsedData = JSON.parse(storedUserData);
      } catch (e) {
        console.error("Error parsing user data");
      }
    }

    const token = parsedData?.access_token;
    // If no access token, or access token has expired, purge stale session
    if (!token || isTokenExpired(token)) {
      if (storedUserId || storedUserData) {
        clearChatHistoryCache();
        localStorage.removeItem("userId");
        localStorage.removeItem("user_id");
        localStorage.removeItem("userData");
        localStorage.removeItem("active_session_id");
      }
      setUserId(null);
      setUserRole(null);
      setUserEmail("");
      setAuthLoading(false);
      return;
    }

    if (storedUserId) {
      setUserId(storedUserId);
    }

    if (parsedData) {
      setUserRole(parsedData.user_role);
      const email = (parsedData.email || parsedData.user_profile?.email || parsedData.user_email || parsedData.user_name || "").trim().toLowerCase();
      setUserEmail(email);
    }

    setAuthLoading(false);
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => {
      handleLogout();
    };

    window.addEventListener("dolphin:auth_unauthorized", handleUnauthorized);
    return () => {
      window.removeEventListener("dolphin:auth_unauthorized", handleUnauthorized);
    };
  }, []);

  const handleLoginSuccess = (id) => {
    setUserId(id);
    const storedUserData = localStorage.getItem("userData");
    if (storedUserData) {
      try {
        const parsedData = JSON.parse(storedUserData);
        setUserRole(parsedData.user_role);
        const email = (parsedData.email || parsedData.user_profile?.email || parsedData.user_email || parsedData.user_name || "").trim().toLowerCase();
        setUserEmail(email);
      } catch (e) {
        console.error("Error parsing user data");
      }
    }
  };

  const handleLogout = async () => {
    clearChatHistoryCache();
    await logout();
    localStorage.removeItem("userId");
    localStorage.removeItem("user_id");
    localStorage.removeItem("userData");
    localStorage.removeItem("active_session_id");
    setUserId(null);
    setUserRole(null);
    setUserEmail("");
    window.history.replaceState(null, "", process.env.PUBLIC_URL || "/");
  };

  if (authLoading) {
    return null;
  }

  const isFeedbackAllowed = isFeedbackAuthorized(userEmail || getCurrentUserEmail(), userRole);

  return userId ? (
    <Router basename={process.env.PUBLIC_URL || "/"}>
      <Routes>
        <Route path="/" element={<Chatpage userId={userId} setUserId={setUserId} onLogout={handleLogout} />} />
        <Route path="/admin" element={
          userRole === "ADMIN" || userRole === "SUPER_ADMIN" ?
            <AdminPage onLogout={handleLogout} />
            : <Navigate to="/" replace />
        }>
          <Route index element={
            isFeedbackAllowed ? <Navigate to="feedback" replace /> : <Navigate to="chat-history" replace />
          } />
          <Route path="feedback/*" element={
            isFeedbackAllowed ? <FeedbackPage onLogout={handleLogout} /> : <Navigate to="/admin/chat-history" replace />
          } />
          <Route path="chat-history" element={<ChatHistoryAdmin />} />
          <Route path="members" element={<Members />} />
        </Route>
        <Route path="/feedback" element={
          isFeedbackAllowed ? <AdminPage onLogout={handleLogout} feedbackOnly /> : <Navigate to="/" replace />
        }>
          <Route path="*" element={<FeedbackPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  ) : (
    <Login onLoginSuccess={handleLoginSuccess} />
  );
}

export default App;
