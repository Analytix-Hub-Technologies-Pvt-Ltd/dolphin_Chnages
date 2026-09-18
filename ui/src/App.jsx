import { useEffect, useState, lazy, Suspense } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import Chatpage from "./pages/chatpage/Chatpage.jsx";
import './App.css';
import { logout, fetchUserProfile } from "./api/apiAuth.js";

const Login = lazy(() => import("./pages/LoginSignup"));
const AdminPage = lazy(() => import("./pages/admin/AdminPage.jsx"));
const ChatHistoryAdmin = lazy(() => import("./pages/ChatHistoryAdmin.jsx"));
const Members = lazy(() => import("./pages/admin/Members.jsx"));
const FeedbackPage = lazy(() => import("./pages/feedback/FeedbackPage.jsx"));

function App() {
  const [userId, setUserId] = useState(null);
  const [userProfile, setUserProfile] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [userRole, setUserRole] = useState(null);

  useEffect(() => {
    const storedUserId = localStorage.getItem("userId") || localStorage.getItem("user_id");
    const storedUserData = localStorage.getItem("userData");

    if (storedUserId) {
      setUserId(storedUserId);
      fetchUserProfile(storedUserId)
        .then((profile) => {
          if (profile) {
            setUserProfile(profile);
            if (profile.user_role || profile.role) {
              setUserRole(profile.user_role || profile.role);
            }
          }
        })
        .catch((err) => console.error("Error fetching user profile:", err));
    }

    if (storedUserData) {
      try {
        const parsedData = JSON.parse(storedUserData);
        setUserRole(parsedData.user_role || parsedData.role);
      } catch (e) {
        console.error("Error parsing user data");
      }
    }

    setAuthLoading(false);
  }, []);

  const handleLoginSuccess = (id) => {
    setUserId(id);
    const storedUserData = localStorage.getItem("userData");
    if (storedUserData) {
      try {
        const parsedData = JSON.parse(storedUserData);
        setUserRole(parsedData.user_role || parsedData.role);
      } catch (e) {
        console.error("Error parsing user data");
      }
    }
    fetchUserProfile(id)
      .then((profile) => {
        if (profile) {
          setUserProfile(profile);
          if (profile.user_role || profile.role) {
            setUserRole(profile.user_role || profile.role);
          }
        }
      })
      .catch((err) => console.error("Error fetching user profile:", err));
  };

  const handleLogout = async () => {
    await logout();
    localStorage.removeItem("userId");
    localStorage.removeItem("user_id");
    localStorage.removeItem("userData");
    localStorage.removeItem("active_session_id");
    setUserId(null);
    setUserRole(null);
    setUserProfile(null);

    const hasBase = window.location.pathname.startsWith("/dolphin-rb/ui");
    window.history.replaceState(null, "", hasBase ? "/dolphin-rb/ui" : "/");
  };

  if (authLoading) {
    return null;
  }

  const basename = window.location.pathname.startsWith("/dolphin-rb/ui")
    ? "/dolphin-rb/ui"
    : "";

  const isAdmin = (() => {
    const storedUserData = (() => {
      try {
        return JSON.parse(localStorage.getItem("userData") || "{}");
      } catch {
        return {};
      }
    })();
    const rawRole = String(
      userRole ||
      storedUserData?.user_role ||
      localStorage.getItem("userRole") ||
      ""
    ).trim().toUpperCase();

    return rawRole === "SUPER_ADMIN" || rawRole === "ADMIN" || rawRole.includes("ADMIN");
  })();

  return (
    <Suspense
      fallback={
        <div className="flex h-screen w-screen items-center justify-center bg-bg-app text-primary">
          <div className="w-8 h-8 border-3 border-primary/20 border-t-primary rounded-full animate-spin" />
        </div>
      }
    >
      {userId ? (
        <Router basename={basename}>
          <Routes>
            <Route
              path="/"
              element={
                <Chatpage
                  userId={userId}
                  userRole={userRole}
                  userProfile={userProfile}
                  setUserId={setUserId}
                  onLogout={handleLogout}
                />
              }
            />
            <Route
              path="/session/:sessionId"
              element={
                <Chatpage
                  userId={userId}
                  userRole={userRole}
                  userProfile={userProfile}
                  setUserId={setUserId}
                  onLogout={handleLogout}
                />
              }
            />
            <Route
              path="/feedback/*"
              element={
                <FeedbackPage
                  userId={userId}
                  userProfile={userProfile}
                  onLogout={handleLogout}
                />
              }
            />
            <Route
              path="/feedback"
              element={
                <FeedbackPage
                  userId={userId}
                  userProfile={userProfile}
                  onLogout={handleLogout}
                />
              }
            />
            <Route
              path="/admin"
              element={
                isAdmin ? (
                  <AdminPage onLogout={handleLogout} />
                ) : (
                  <Navigate to="/" replace />
                )
              }
            >
              <Route index element={<Navigate to="chat-history" replace />} />
              <Route path="chat-history" element={<ChatHistoryAdmin />} />
              <Route path="members" element={<Members />} />
            </Route>
            <Route
              path="/:sessionSlug"
              element={
                <Chatpage
                  userId={userId}
                  userRole={userRole}
                  userProfile={userProfile}
                  setUserId={setUserId}
                  onLogout={handleLogout}
                />
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Router>
      ) : (
        <Login onLoginSuccess={handleLoginSuccess} />
      )}
    </Suspense>
  );
}

export default App;

