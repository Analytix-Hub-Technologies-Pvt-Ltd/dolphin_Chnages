import React from "react";
import { ArrowLeft, Moon, Sun, MessageSquareCheck } from "lucide-react";
import DolphinIconW from "../../assets/images/dolphin_w.png";
import { useThemeMode } from "../../context/ThemeModeContext";

const FeedbackHeader = ({ onNavigateToChat, userProfile }) => {
  const { mode, toggleMode } = useThemeMode();

  return (
    <header className="w-full h-16 flex items-center justify-between px-4 sm:px-6 bg-bg-header border-b border-border-theme shadow-xs shrink-0">
      {/* Brand & Title */}
      <div className="flex items-center gap-3">
        <img
          src={DolphinIconW}
          alt="Dolphin AI Logo"
          className="w-9 h-9 sm:w-10 sm:h-10 rounded-full bg-primary p-1 shrink-0 shadow-xs"
        />
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <h1 className="text-base sm:text-lg font-bold text-text-primary tracking-tight m-0">
              Dolphin AI
            </h1>
            <div className="inline-flex items-center gap-1 bg-primary/15 text-primary px-2 py-0.5 rounded-md text-[11px] font-semibold">
              <MessageSquareCheck className="w-3.5 h-3.5" />
              <span>Feedback & Quality Review</span>
            </div>
          </div>
          <span className="text-[11px] text-text-secondary hidden sm:inline-block leading-tight">
            Human-in-the-loop validation, Vector Memory & DPO Training
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 sm:gap-3">
        <button
          type="button"
          onClick={onNavigateToChat}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl border border-primary text-primary bg-bg-paper hover:bg-primary/10 transition-colors cursor-pointer shadow-xs"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Chat</span>
        </button>

        {/* Theme Toggle */}
        <button
          type="button"
          onClick={toggleMode}
          title={mode === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
          className="p-2 rounded-xl border border-border-theme bg-bg-paper text-text-primary hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer"
        >
          {mode === "dark" ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-primary" />
          )}
        </button>

        {/* Profile Avatar */}
        <div className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-xs select-none">
          {userProfile?.name?.charAt(0)?.toUpperCase() || "A"}
        </div>
      </div>
    </header>
  );
};

export default React.memo(FeedbackHeader);
