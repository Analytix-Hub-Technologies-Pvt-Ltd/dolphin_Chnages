import { useEffect, useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/LoginSignup";
import Chatpage from "./pages/chatpage/Chatpage.jsx";
import AdminPage from "./pages/admin/AdminPage.jsx";
import './App.css'
import { logout } from "./api/apiAuth.js";

function App() {
  const [userId, setUserId] = useState(null);

  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    const storedUserId = localStorage.getItem("userId");

    if (storedUserId) {
      setUserId(storedUserId);
    }

    setAuthLoading(false);
  }, []);

  const handleLoginSuccess = (id) => {
    setUserId(id);
  };

  const handleLogout = async() => {
    await logout()
    localStorage.removeItem("userId");
    setUserId(null);
  };

  if (authLoading) {
    return null;
  }

  return (
    <Routes>
      <Route 
        path="/" 
        element={
          userId ? (
            <Chatpage userId={userId} onLogout={handleLogout} />
          ) : (
            <Login onLoginSuccess={handleLoginSuccess} />
          )
        } 
      />
      <Route 
        path="/admin" 
        element={
          userId ? (
            <AdminPage />
          ) : (
            <Navigate to="/" replace />
          )
        } 
      />
    </Routes>
  );
}

export default App;
