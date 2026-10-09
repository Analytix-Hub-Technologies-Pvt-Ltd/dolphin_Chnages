import React from "react";
import { ArrowLeft, Moon, Sun, MessageSquareCheck } from "lucide-react";
import DolphinIconW from "../../assets/images/dolphin_w.png";
import { useThemeMode } from "../../context/ThemeModeContext";

const FeedbackHeader = ({ onNavigateToChat, userProfile }) => {
  const { mode, toggleMode } = useThemeMode();

  return (
    <header className="fb-header" style={{ height: 60, minHeight: 60, maxHeight: 60 }}>
      {/* Brand & Title */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <img
          src={DolphinIconW}
          alt="Dolphin AI Logo"
          className="fb-header-logo"
          style={{ width: 36, height: 36, maxWidth: 36, maxHeight: 36, objectFit: "contain", borderRadius: "50%", background: "#106BA3", padding: 4 }}
        />
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: mode === "dark" ? "#f1f5f9" : "#0f1c2e", letterSpacing: "-0.02em" }}>
              Dolphin AI
            </h1>
            <div style={{ display: "inline-flex", alignItems: "center", gap: 4, background: "rgba(16, 107, 163, 0.15)", color: "#106BA3", padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600 }}>
              <MessageSquareCheck style={{ width: 14, height: 14 }} />
              <span>Feedback & Quality Review</span>
            </div>
          </div>
          <span style={{ fontSize: 11, color: mode === "dark" ? "#94a3b8" : "#475569", lineHeight: 1.2 }}>
            Human-in-the-loop validation, Vector Memory & DPO Training
          </span>
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <button
          type="button"
          onClick={onNavigateToChat}
          style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 14px", fontSize: 12, fontWeight: 600, borderRadius: 12, border: "1px solid #106BA3", color: "#106BA3", background: mode === "dark" ? "#0f2537" : "#ffffff", cursor: "pointer" }}
        >
          <ArrowLeft style={{ width: 14, height: 14 }} />
          <span>Back to Chat</span>
        </button>

        {/* Theme Toggle */}
        <button
          type="button"
          onClick={toggleMode}
          title={mode === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
          style={{ display: "flex", alignItems: "center", justifyContent: "center", width: 34, height: 34, borderRadius: 10, border: "1px solid #e2e8f0", background: mode === "dark" ? "#0f2537" : "#ffffff", cursor: "pointer" }}
        >
          {mode === "dark" ? (
            <Sun style={{ width: 16, height: 16, color: "#f59e0b" }} />
          ) : (
            <Moon style={{ width: 16, height: 16, color: "#106BA3" }} />
          )}
        </button>

        {/* Profile Avatar */}
        <div style={{ width: 34, height: 34, borderRadius: "50%", background: "#106BA3", color: "#ffffff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 13, userSelect: "none" }}>
          {userProfile?.name?.charAt(0)?.toUpperCase() || "D"}
        </div>
      </div>
    </header>
  );
};

export default React.memo(FeedbackHeader);
