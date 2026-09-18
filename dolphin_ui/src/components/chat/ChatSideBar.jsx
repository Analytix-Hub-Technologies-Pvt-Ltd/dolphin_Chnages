import React, { useEffect, useState, useRef } from "react";
import { ChatItem } from "./ChatItem";
import { useThemeMode } from "../../context/ThemeModeContext";
import { Message } from "../../assets/svgIcons/message";
import { SaveIcon } from "../../assets/svgIcons/Saveicon";
import { Search } from "../../assets/svgIcons/Search";
import { FilterIcon } from "../../assets/svgIcons/FilterIcon";
import { Check, X } from "lucide-react";
import { getSidebarWidth } from "../../theme/layoutScale";
import { saveSession } from "../../api/fetchApi";

const ChatSideBar = ({
  sessionData,
  activeIndex,
  setActiveIndex,
  selectSession,
  loading,
  sidebarOpen,
  setSidebarOpen,
  fetchSessions,
  currentSessionId,
}) => {
  const { mode, fontLevel } = useThemeMode();
  const [valueTab, setValueTab] = useState(0); // 0 = My Chats, 1 = Saved Chats
  const [openFilter, setOpenFilter] = useState(false);
  const [filterValue, setFilterValue] = useState("pinned");
  const [searchTerm, setSearchTerm] = useState("");

  const isInitialMount = useRef(true);
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    const delayDebounce = setTimeout(() => {
      fetchSessions(searchTerm);
    }, 400);

    return () => clearTimeout(delayDebounce);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchTerm]);

  const primaryColor = mode === "dark" ? "#1cb0f6" : "#106BA3";

  return (
    <aside
      style={{
        width:
          typeof window !== "undefined" && window.innerWidth >= 768
            ? getSidebarWidth(fontLevel)
            : "100%",
      }}
      className="p-4 flex flex-col box-border bg-bg-sidebar h-full min-w-[240px] max-w-[340px] border-r border-border-theme select-none shrink-0"
    >
      {/* Tab Switcher Pills */}
      <div className="w-full bg-bg-lightblue1 p-1 rounded-xl mb-3 flex items-center justify-between gap-1">
        <button
          type="button"
          onClick={() => setValueTab(0)}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg text-xs font-semibold transition-all ${
            valueTab === 0
              ? "bg-primary text-white shadow-xs"
              : "text-text-primary hover:bg-white/40 dark:hover:bg-white/10"
          }`}
        >
          <Message size={16} color={valueTab === 0 ? "#ffffff" : primaryColor} />
          <span>My Chats</span>
        </button>

        <button
          type="button"
          onClick={() => setValueTab(1)}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg text-xs font-semibold transition-all ${
            valueTab === 1
              ? "bg-primary text-white shadow-xs"
              : "text-text-primary hover:bg-white/40 dark:hover:bg-white/10"
          }`}
        >
          <SaveIcon size={16} color={valueTab === 1 ? "#ffffff" : primaryColor} />
          <span>Saved Chats</span>
        </button>
      </div>

      {/* Search and Filter Row */}
      <div className="flex items-center gap-2 mb-3">
        <div className="relative flex-1 flex items-center">
          <div className="absolute left-2.5 pointer-events-none">
            <Search size={16} color="#0f1c2e" />
          </div>
          <input
            type="text"
            placeholder="Search here..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 rounded-xl bg-bg-grey text-text-placeholder text-xs border-none focus:outline-hidden focus:ring-1 focus:ring-primary transition-all"
          />
        </div>

        <button
          type="button"
          onClick={() => {
            setSidebarOpen?.(false);
            setOpenFilter(true);
          }}
          className="w-8 h-8 rounded-xl bg-bg-grey flex items-center justify-center text-primary hover:opacity-80 transition-opacity shrink-0"
          aria-label="Filter chats"
        >
          <FilterIcon size={18} color={primaryColor} />
        </button>
      </div>

      {/* Section Header */}
      <span className="block text-xs font-semibold text-text-smallheading mb-2">
        Your Chats
      </span>

      {/* Chat List Scroll Area */}
      <div className="flex-1 overflow-y-auto space-y-1 pr-1">
        {loading ? (
          <div className="space-y-2">
            {[...Array(6)].map((_, i) => (
              <div
                key={i}
                className="w-full h-9 rounded-xl bg-bg-grey/70 animate-pulse"
              />
            ))}
          </div>
        ) : (() => {
          const displayedChats = (sessionData || []).filter((chat) => {
            if (valueTab === 1) return chat.is_saved;
            return true;
          });

          return displayedChats.length ? (
            displayedChats.map((chat, index) => (
              <ChatItem
                key={chat.session_id || index}
                sessionId={chat.session_id}
                title={chat.title}
                isSaved={Boolean(chat.is_saved)}
                active={
                  currentSessionId
                    ? String(chat.session_id) === String(currentSessionId)
                    : index === activeIndex
                }
                onClick={() => {
                  setActiveIndex(index);
                  selectSession(chat.session_id);
                  setSidebarOpen?.(false);
                }}
                onDelete={() => {
                  if (currentSessionId && String(chat.session_id) === String(currentSessionId)) {
                    selectSession?.(null);
                  }
                  fetchSessions?.("", true);
                }}
                onToggleSave={async (id) => {
                  await saveSession(id);
                  await fetchSessions?.("", true);
                }}
              />
            ))
          ) : (
            <p className="text-xs text-text-secondary py-4 text-center m-0">
              {valueTab === 1
                ? "No saved chats found."
                : "Your chat history is empty."}
            </p>
          );
        })()}
      </div>

      {/* Filter Modal Dialog */}
      {openFilter && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="w-full max-w-sm rounded-3xl bg-bg-paper border-2 border-primary p-6 shadow-2xl animate-in zoom-in-95 duration-150 relative">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-base font-bold text-text-primary m-0">Filter</h3>
              <button
                type="button"
                onClick={() => setOpenFilter(false)}
                className="p-1 rounded-full text-text-secondary hover:text-text-primary transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 mb-6">
              <label className="flex items-center gap-2.5 text-sm text-text-primary cursor-pointer select-none">
                <input
                  type="radio"
                  name="chatFilter"
                  value="pinned"
                  checked={filterValue === "pinned"}
                  onChange={(e) => setFilterValue(e.target.value)}
                  className="w-4 h-4 text-primary accent-primary"
                />
                <span>Pinned Chat</span>
              </label>
            </div>

            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => setOpenFilter(false)}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-primary text-white font-semibold text-xs shadow hover:bg-primary-hover transition-colors"
              >
                <Check className="w-4 h-4" />
                Apply
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
};

export default ChatSideBar;
