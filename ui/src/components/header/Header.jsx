import React, { useState, useEffect, useRef } from "react";
import {
  Menu,
  Plus,
  User,
  LogOut,
  Settings,
  ChevronLeft,
  Sun,
  Moon,
  Shield,
  ArrowLeft,
  ThumbsUp,
} from "lucide-react";
import DolphinIconB from "../../assets/images/dolphin_b.png";
import DolphinIconW from "../../assets/images/dolphin_w.png";
import ShipIconB from "../../assets/images/ship.png";
import ShipIconW from "../../assets/images/ship_w.png";
import { useThemeMode } from "../../context/ThemeModeContext";
import { useNavigate, useLocation } from "react-router-dom";
import ChatSidebar from "../chat/ChatSideBar";
import { fetchUserProfile } from "../../api/apiAuth";

const Header = ({
  userId,
  userRole,
  onLogout,
  setActiveIndex,
  setCurrentSessionId,
  setCurrentSessionData,
  setmessages,
  disableNewChat,
  sessionData,
  activeIndex,
  selectSession,
  loading,
  sidebarOpen,
  setSidebarOpen,
  fetchSessions,
  drawerContent,
  currentSessionId,
}) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { mode, toggleMode, fontLevel, setFontLevel } = useThemeMode();

  const isAdminRoute = location?.pathname?.includes("/admin");
  const isFeedbackRoute = location?.pathname?.includes("/feedback");

  const [openUserMenu, setOpenUserMenu] = useState(false);
  const [popoverView, setPopoverView] = useState("profile"); // "profile" | "settings"
  const popoverRef = useRef(null);
  const userButtonRef = useRef(null);

  const [userProfile, setUserProfile] = useState(() => {
    try {
      const stored = localStorage.getItem("userData");
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });

  // Close popover when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(event.target) &&
        userButtonRef.current &&
        !userButtonRef.current.contains(event.target)
      ) {
        setOpenUserMenu(false);
        setPopoverView("profile");
      }
    };

    if (openUserMenu) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [openUserMenu]);

  useEffect(() => {
    const loadProfile = async () => {
      const currentUserId =
        userId || localStorage.getItem("userId") || localStorage.getItem("user_id");
      if (currentUserId) {
        const profile = await fetchUserProfile(currentUserId);
        if (profile) {
          setUserProfile((prev) => {
            const stored = (() => {
              try {
                return JSON.parse(localStorage.getItem("userData") || "{}");
              } catch {
                return {};
              }
            })();
            return {
              ...stored,
              ...prev,
              ...profile,
              user_role:
                profile.user_role ||
                prev?.user_role ||
                stored?.user_role ||
                localStorage.getItem("userRole"),
            };
          });
        }
      }
    };
    loadProfile();
  }, [userId, userRole]);

  const isAdmin = (() => {
    const stored = (() => {
      try {
        return JSON.parse(localStorage.getItem("userData") || "{}");
      } catch {
        return {};
      }
    })();

    const rawRole = String(
      userProfile?.user_role ||
        stored?.user_role ||
        localStorage.getItem("userRole") ||
        userRole ||
        ""
    )
      .trim()
      .toUpperCase();

    return rawRole === "SUPER_ADMIN" || rawRole === "ADMIN" || rawRole.includes("ADMIN");
  })();

  const getUserInitial = () => {
    if (userProfile?.name && userProfile.name.trim()) {
      return userProfile.name.trim().charAt(0).toUpperCase();
    }
    if (userProfile?.user_name && userProfile.user_name.trim()) {
      return userProfile.user_name.trim().charAt(0).toUpperCase();
    }
    if (userProfile?.email && userProfile.email.trim()) {
      return userProfile.email.trim().charAt(0).toUpperCase();
    }
    return "U";
  };

  const handleCreateNewSession = () => {
    setCurrentSessionData?.(null);
    setActiveIndex?.(null);
    setCurrentSessionId?.(null);
    setmessages?.([]);
    navigate("/");
  };

  return (
    <>
      {/* ================= HEADER ================= */}
      <header className="h-full w-full bg-bg-header flex items-center justify-between px-3 sm:px-6 md:px-8 border-b border-border-theme select-none">
        {/* ================= LEFT ================= */}
        <div className="flex items-center gap-3 md:gap-5">
          {/* Mobile menu toggle */}
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="md:hidden p-1.5 rounded-lg text-text-primary hover:bg-bg-paper/40 transition-colors"
            aria-label="Open navigation menu"
          >
            <Menu className="w-6 h-6" />
          </button>

          {/* Logo Brand */}
          <div
            onClick={() => {
              if (isAdminRoute) navigate("/");
            }}
            className={`flex items-center gap-2 sm:gap-3 ${isAdminRoute ? "cursor-pointer" : "cursor-default"}`}
          >
            <img
              src={mode === "dark" ? DolphinIconW : DolphinIconB}
              alt="Dolphin"
              className="w-10 h-10 sm:w-12 sm:h-12 md:w-14 md:h-14 object-contain"
            />
            <img
              src={mode === "dark" ? ShipIconW : ShipIconB}
              alt="Ship"
              className="w-7 h-7 sm:w-8 sm:h-8 md:w-10 md:h-10 object-contain"
            />
          </div>

          {/* Desktop Title */}
          <div className="hidden md:flex items-center gap-2 text-xl font-bold">
            <span className="text-text-primary">Dolphin</span>
            <span className="text-text-primary">|</span>
            <span className="text-primary">AI</span>
          </div>

          {/* Connection Status */}
          <div className="flex items-center gap-1.5 ml-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="hidden sm:inline text-xs font-medium text-text-secondary">
              Connected
            </span>
          </div>
        </div>

        {/* ================= RIGHT ================= */}
        <div className="flex items-center gap-1.5 sm:gap-3">
          {/* Action Button: New Chat on Chat Route */}
          {!isAdminRoute && (
            <button
              type="button"
              disabled={disableNewChat}
              onClick={handleCreateNewSession}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-paper text-text-primary font-semibold text-sm shadow-sm hover:bg-bg-paper/80 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Plus className="w-4 h-4 text-primary" />
              <span className="hidden sm:inline">New Chat</span>
            </button>
          )}

          {/* User Profile Avatar / Menu Button */}
          <div className="relative">
            <button
              ref={userButtonRef}
              id="user-profile-button"
              type="button"
              onClick={() => {
                setPopoverView("profile");
                setOpenUserMenu(!openUserMenu);
              }}
              className={`p-1 rounded-full transition-colors ${openUserMenu ? "bg-bg-paper" : "hover:bg-bg-paper/50"}`}
              title="User Profile"
            >
              <div className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center font-bold text-sm shadow-sm">
                {getUserInitial()}
              </div>
            </button>

            {/* ================= USER INFO & SETTINGS POPOVER ================= */}
            {openUserMenu && (
              <div
                ref={popoverRef}
                id="user-info-popover"
                className="absolute right-0 mt-2 w-72 sm:w-80 p-4 rounded-2xl bg-bg-paper border border-border-theme shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-150"
              >
                {popoverView === "settings" ? (
                  /* ================= SETTINGS VIEW ================= */
                  <div>
                    <div className="flex items-center gap-2 mb-3">
                      <button
                        type="button"
                        onClick={() => setPopoverView("profile")}
                        className="p-1 rounded-lg hover:bg-bg-default text-text-primary transition-colors"
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </button>
                      <h3 className="text-sm font-bold text-text-primary m-0">Settings</h3>
                    </div>

                    {/* Font Size */}
                    <span className="block text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
                      Font Size
                    </span>
                    <div className="px-1 mb-4">
                      <div className="flex justify-between text-xs text-text-secondary mb-1">
                        <span className={fontLevel === 0 ? "font-bold text-primary" : ""}>Small</span>
                        <span className={fontLevel === 1 ? "font-bold text-primary" : ""}>Medium</span>
                        <span className={fontLevel === 2 ? "font-bold text-primary" : ""}>Large</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="2"
                        step="1"
                        value={fontLevel}
                        onChange={(e) => setFontLevel(Number(e.target.value))}
                        className="w-full h-1.5 bg-border-theme rounded-lg appearance-none cursor-pointer accent-primary"
                      />
                    </div>

                    <div className="h-px w-full bg-border-theme my-3" />

                    {/* Theme Mode */}
                    <span className="block text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
                      Theme
                    </span>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => mode !== "light" && toggleMode()}
                        className={`flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-semibold border transition-colors ${
                          mode === "light"
                            ? "bg-primary text-white border-primary"
                            : "border-border-theme text-text-primary hover:bg-bg-default"
                        }`}
                      >
                        <Sun className="w-4 h-4" />
                        Light
                      </button>
                      <button
                        type="button"
                        onClick={() => mode !== "dark" && toggleMode()}
                        className={`flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-semibold border transition-colors ${
                          mode === "dark"
                            ? "bg-primary text-white border-primary"
                            : "border-border-theme text-text-primary hover:bg-bg-default"
                        }`}
                      >
                        <Moon className="w-4 h-4" />
                        Dark
                      </button>
                    </div>
                  </div>
                ) : (
                  /* ================= PROFILE CARD VIEW ================= */
                  <div>
                    {/* Top Bar: Label + Settings Button */}
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-[0.68rem] font-bold text-text-secondary uppercase tracking-wider">
                        User Profile
                      </span>
                      <button
                        type="button"
                        onClick={() => setPopoverView("settings")}
                        className="p-1.5 rounded-lg border border-border-theme text-text-secondary hover:text-primary hover:border-primary hover:bg-bg-default transition-colors"
                        title="Settings"
                      >
                        <Settings className="w-4 h-4" />
                      </button>
                    </div>

                    {/* User ID Card */}
                    <div className="p-3.5 rounded-xl bg-primary/5 dark:bg-white/5 border border-primary/15 dark:border-white/10 mb-3">
                      {/* Avatar + Main Identity */}
                      <div className="flex items-center gap-3 mb-2.5">
                        <div className="w-10 h-10 rounded-full bg-primary text-white flex items-center justify-center font-bold text-base shadow-sm shrink-0">
                          {getUserInitial()}
                        </div>
                        <div className="overflow-hidden flex-1 min-w-0">
                          <p className="text-sm font-bold text-text-primary truncate m-0">
                            {userProfile?.name || "Mariner"}
                          </p>
                          <p className="text-xs text-text-secondary truncate m-0">
                            {userProfile?.email || "No email"}
                          </p>
                          {userProfile?.user_type && (
                            <span className="inline-block mt-1 px-2 py-0.5 text-[0.65rem] font-bold uppercase rounded bg-primary text-white">
                              {userProfile.user_type}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Details Grid */}
                      {(userProfile?.company_name || userProfile?.ship_name || userProfile?.ship_type) && (
                        <div className="pt-2 border-t border-dashed border-border-theme space-y-1.5 text-xs">
                          {userProfile?.company_name && (
                            <div className="flex justify-between items-center">
                              <span className="text-text-secondary">Company</span>
                              <span className="font-semibold text-text-primary truncate max-w-[60%] text-right">
                                {userProfile.company_name}
                              </span>
                            </div>
                          )}
                          {userProfile?.ship_name && (
                            <div className="flex justify-between items-center">
                              <span className="text-text-secondary">Ship Name</span>
                              <span className="font-semibold text-text-primary truncate max-w-[60%] text-right">
                                {userProfile.ship_name}
                              </span>
                            </div>
                          )}
                          {userProfile?.ship_type && (
                            <div className="flex justify-between items-center">
                              <span className="text-text-secondary">Ship Type</span>
                              <span className="font-semibold text-text-primary truncate max-w-[60%] text-right">
                                {userProfile.ship_type}
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Feedback Link */}
                    <button
                      id="feedback-dashboard-link-button"
                      type="button"
                      onClick={() => {
                        setOpenUserMenu(false);
                        if (isFeedbackRoute) {
                          navigate("/");
                        } else {
                          navigate("/feedback");
                        }
                      }}
                      className="w-full flex items-center justify-center gap-2 mb-2 py-2 px-3 rounded-lg border border-primary text-primary font-bold text-xs hover:bg-primary/10 transition-colors"
                    >
                      {isFeedbackRoute ? (
                        <>
                          <ArrowLeft className="w-4 h-4" />
                          Back to Chat
                        </>
                      ) : (
                        <>
                          <ThumbsUp className="w-4 h-4" />
                          Feedback Dashboard →
                        </>
                      )}
                    </button>

                    {/* Admin Link */}
                    {(isAdmin || isAdminRoute) && (
                      <button
                        id="admin-panel-link-button"
                        type="button"
                        onClick={() => {
                          setOpenUserMenu(false);
                          if (isAdminRoute) {
                            navigate("/");
                          } else {
                            navigate("/admin/chat-history");
                          }
                        }}
                        className="w-full flex items-center justify-center gap-2 mb-2 py-2 px-3 rounded-lg bg-primary text-white font-bold text-xs shadow hover:bg-primary-hover transition-colors"
                      >
                        {isAdminRoute ? (
                          <>
                            <ArrowLeft className="w-4 h-4" />
                            Back to Chat
                          </>
                        ) : (
                          <>
                            <Shield className="w-4 h-4" />
                            Go to Admin Panel →
                          </>
                        )}
                      </button>
                    )}

                    {/* Logout Button */}
                    <button
                      type="button"
                      onClick={() => {
                        setOpenUserMenu(false);
                        onLogout();
                      }}
                      className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg bg-rose-600 text-white font-semibold text-xs shadow hover:bg-rose-700 transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                      Logout
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Quick Logout Button */}
          <button
            type="button"
            onClick={onLogout}
            className="flex items-center gap-1.5 px-3 py-1.5 text-text-primary hover:text-rose-600 transition-colors text-sm font-semibold"
            title="Logout"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden md:inline">Logout</span>
          </button>
        </div>
      </header>

      {/* ================= MOBILE SIDEBAR DRAWER ================= */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/50 transition-opacity"
            onClick={() => setSidebarOpen(false)}
          />

          {/* Drawer Paper */}
          <div className="relative w-72 max-w-[85vw] h-full bg-bg-default shadow-2xl z-10 overflow-y-auto">
            {drawerContent || (
              <ChatSidebar
                onClose={() => setSidebarOpen(false)}
                sessionData={sessionData}
                loading={loading}
                activeIndex={activeIndex}
                setActiveIndex={setActiveIndex}
                sidebarOpen={sidebarOpen}
                setSidebarOpen={setSidebarOpen}
                selectSession={selectSession}
                fetchSessions={fetchSessions}
                currentSessionId={currentSessionId}
              />
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default Header;
