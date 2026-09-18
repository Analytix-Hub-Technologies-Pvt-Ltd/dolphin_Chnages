import React, { useState, useRef, useEffect } from "react";
import { Message } from "../../assets/svgIcons/message";
import { Threedot } from "../../assets/svgIcons/ThreeDots";
import { DeleteIcon } from "../../assets/svgIcons/DeleteIcon";
import { SaveIcon } from "../../assets/svgIcons/Saveicon";
import { Saveoutlined } from "../../assets/svgIcons/SaveIconOutlined";
import ActionDialog from "./ActionDialog";
import { deleteSession, saveSession } from "../../api/fetchApi";
import { useThemeMode } from "../../context/ThemeModeContext";

export const ChatItem = ({
  title,
  active,
  onClick,
  sessionId,
  onDelete,
  tabType,
  isSaved,
  onToggleSave,
}) => {
  const { mode } = useThemeMode();
  const [openMenu, setOpenMenu] = useState(false);
  const menuRef = useRef(null);
  const menuButtonRef = useRef(null);

  // Close menu on click outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(e.target) &&
        menuButtonRef.current &&
        !menuButtonRef.current.contains(e.target)
      ) {
        setOpenMenu(false);
      }
    };
    if (openMenu) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [openMenu]);

  const [dialog, setDialog] = useState({
    open: false,
    mode: "confirm",
    message: "",
  });

  const handleDeleteClick = (e) => {
    e.stopPropagation();
    setOpenMenu(false);
    setDialog({
      open: true,
      mode: "confirm",
      message: "Are you sure you want to permanently delete this session?",
    });
  };

  const handleConfirmDelete = async () => {
    try {
      await deleteSession(sessionId);
      onDelete?.(sessionId);
      setDialog({
        open: true,
        mode: "success",
        message: "Session deleted successfully!",
      });
    } catch (error) {
      setDialog({
        open: true,
        mode: "error",
        message: error.message || "Failed to delete session",
      });
    }
  };

  const handleToggleSave = async (e) => {
    e.stopPropagation();
    setOpenMenu(false);
    try {
      if (onToggleSave) {
        await onToggleSave(sessionId);
      } else {
        await saveSession(sessionId);
      }
    } catch (error) {
      setDialog({
        open: true,
        mode: "error",
        message: error.message || "Failed to update saved chat",
      });
    }
  };

  const primaryColor = mode === "dark" ? "#1cb0f6" : "#106BA3";
  const textColor = mode === "dark" ? "#e8f1fb" : "#0f1c2e";
  const menuColor = mode === "dark" ? "#ffffff" : "#464646";

  return (
    <>
      <div
        className={`group flex items-center justify-between gap-2 py-2 px-2.5 rounded-xl transition-colors select-none ${
          active
            ? "bg-bg-lightblue1 text-primary font-semibold"
            : "hover:bg-bg-lightblue1/60 text-text-primary font-medium"
        }`}
      >
        {/* Chat Title & Icon */}
        <div
          className="flex items-center gap-2 w-[70%] cursor-pointer min-w-0"
          onClick={onClick}
        >
          <div className="shrink-0">
            <Message size={20} color={active ? primaryColor : primaryColor} />
          </div>
          <span
            className={`truncate text-sm ${
              active ? "text-primary font-semibold" : "text-text-primary"
            }`}
          >
            {title ? title : "Untitled session"}
          </span>
        </div>

        {/* Actions (Save & Three-Dots) */}
        <div className="flex items-center gap-1.5 shrink-0 relative">
          {isSaved && (
            <div className="w-5 h-5 flex items-center justify-center" title="Saved chat">
              <SaveIcon size={14} color={primaryColor} />
            </div>
          )}

          <button
            ref={menuButtonRef}
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setOpenMenu(!openMenu);
            }}
            className="w-6 h-6 rounded-full flex items-center justify-center hover:bg-black/10 dark:hover:bg-white/10 transition-colors focus:outline-hidden"
            aria-label="Chat options"
          >
            <Threedot size={18} color={menuColor} />
          </button>

          {/* Context Dropdown Menu */}
          {openMenu && (
            <div
              ref={menuRef}
              className="absolute right-0 top-7 w-36 py-1.5 rounded-xl bg-bg-paper border border-primary shadow-xl z-50 animate-in fade-in zoom-in-95 duration-100"
            >
              {/* Save / Unsave Option */}
              <button
                type="button"
                onClick={handleToggleSave}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-text-primary hover:bg-bg-default transition-colors text-left"
              >
                {isSaved ? (
                  <SaveIcon size={16} color={primaryColor} />
                ) : (
                  <Saveoutlined size={16} color={primaryColor} />
                )}
                <span>{isSaved ? "Unsave Chat" : "Save Chat"}</span>
              </button>

              {/* Delete Option */}
              <button
                type="button"
                onClick={handleDeleteClick}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-500/10 transition-colors text-left"
              >
                <DeleteIcon size={16} color="#e11d48" />
                <span>Delete</span>
              </button>
            </div>
          )}
        </div>
      </div>

      <ActionDialog
        open={dialog.open}
        mode={dialog.mode}
        message={dialog.message}
        onClose={() => setDialog({ ...dialog, open: false })}
        onConfirm={handleConfirmDelete}
      />
    </>
  );
};

export default ChatItem;
