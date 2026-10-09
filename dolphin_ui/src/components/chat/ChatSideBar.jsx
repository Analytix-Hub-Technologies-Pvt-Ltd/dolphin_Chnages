import {
  Box,
  InputAdornment,
  Stack,
  TextField,
  Typography,
  Skeleton,
  Button,
  Tabs,
  Tab,
  Dialog,
  DialogContent,
  RadioGroup,
  FormControlLabel,
  Radio,
} from "@mui/material";
import React, { useEffect, useState, useMemo } from "react";
import { ChatItem } from "./ChatItem";
import { useThemeMode } from "../../context/ThemeModeContext";
import { Message } from "../../assets/svgIcons/message";
import { SaveIcon } from "../../assets/svgIcons/Saveicon";
import { Search } from "../../assets/svgIcons/Search";
import CheckRoundedIcon from "@mui/icons-material/CheckRounded";
import { getSidebarWidth } from "../../theme/layoutScale";
import { getSavedSessions } from "../../api/fetchApi";

const ChatSideBar = ({
  sessionData,
  setActiveIndex,
  selectSession,
  loading,
  setSidebarOpen,
  fetchSessions,
  currentSessionId,
}) => {
  const { mode } = useThemeMode();
  const [valueTab, setValueTab] = useState(0);
  const [openFilter, setOpenFilter] = useState(false);
  const [filterValue, setFilterValue] = useState("pinned");
  const [searchTerm, setSearchTerm] = useState("");
  const [savedSessions, setSavedSessions] = useState([]);
  const [savedLoading, setSavedLoading] = useState(false);
  const [localSessions, setLocalSessions] = useState(sessionData || []);
  const [pinnedSessions, setPinnedSessions] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("pinned_sessions") || "[]");
    } catch {
      return [];
    }
  });

  const handleTogglePin = (id) => {
    setPinnedSessions((prev) => {
      const isPinned = prev.includes(id);
      const newPinned = isPinned ? prev.filter((p) => p !== id) : [...prev, id];
      localStorage.setItem("pinned_sessions", JSON.stringify(newPinned));
      return newPinned;
    });
  };

  // Fetch saved sessions when tab changes to Saved Chats
  useEffect(() => {
    if (valueTab === 1) {
      loadSavedSessions();
    }
  }, [valueTab]);

  useEffect(() => {
    setLocalSessions((prev) => {
      return (sessionData || []).map((apiChat) => {
        const local = prev.find((s) => s.session_id === apiChat.session_id);

        //  keep local is_saved if exists
        return local ? { ...apiChat, is_saved: local.is_saved } : apiChat;
      });
    });
  }, [sessionData]);

  const handleToggleSave = (id, newStatus) => {
    const chat = localSessions.find((s) => s.session_id === id);

    // update My Chats
    setLocalSessions((prev) =>
      prev.map((s) =>
        s.session_id === id ? { ...s, is_saved: newStatus } : s,
      ),
    );

    // update Saved Chats
    if (newStatus) {
      setSavedSessions((prev) => {
        const exists = prev.some((s) => s.session_id === id);
        if (exists) return prev;
        return chat ? [{ ...chat, is_saved: true }, ...prev] : prev;
      });
    } else {
      setSavedSessions((prev) => prev.filter((s) => s.session_id !== id));
    }
  };

  const loadSavedSessions = async () => {
    try {
      setSavedLoading(true);
      const response = await getSavedSessions();
      setSavedSessions(response.saved_sessions || []);
    } catch (error) {
      console.error("Failed to load saved sessions:", error);
      setSavedSessions([]);
    } finally {
      setSavedLoading(false);
    }
  };

  // Debounced search
  useEffect(() => {
    if (valueTab === 0) {
      const delayDebounce = setTimeout(() => {
        fetchSessions(searchTerm);
      }, 400);
      return () => clearTimeout(delayDebounce);
    }
  }, [searchTerm, valueTab, fetchSessions]);

  const tabStyle = (active) => ({
    flex: "0 0 auto",
    width: "auto",
    px: 0.6,
    py: 0.5,
    borderRadius: 2,
    minHeight: 35,
    fontWeight: 500,
    color: active ? "text.white" : "text.primary",
    bgcolor: active ? "primary.main" : "transparent",
    transition: "all 0.25s ease",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 0.5,
    "&.Mui-selected": {
      color: "text.white",
    },
  });

  // Helper function to check if date is today
  const isToday = (dateString) => {
    if (!dateString) return false;
    const date = new Date(dateString);
    const today = new Date();
    return date.toDateString() === today.toDateString();
  };

  // Helper function to check if date is yesterday
  const isYesterday = (dateString) => {
    if (!dateString) return false;
    const date = new Date(dateString);
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    return date.toDateString() === yesterday.toDateString();
  };

  // Get sessions based on selected tab
  const displaySessions = useMemo(() => {
    if (valueTab === 1) {
      return savedSessions;
    }
    return localSessions || [];
  }, [valueTab, localSessions, savedSessions]);
  // Group sessions by date
  const groupedSessions = useMemo(() => {
    if (!displaySessions || !displaySessions.length) {
      return { pinned: [], today: [], yesterday: [], older: [] };
    }

    const groups = {
      pinned: [],
      today: [],
      yesterday: [],
      older: [],
    };

    displaySessions.forEach((chat, index) => {
      const dateField = chat.updated_at || chat.created_at || chat.timestamp;
      const chatWithIndex = { ...chat, originalIndex: index };

      if (pinnedSessions.includes(chat.session_id)) {
        groups.pinned.push(chatWithIndex);
      } else if (isToday(dateField)) {
        groups.today.push(chatWithIndex);
      } else if (isYesterday(dateField)) {
        groups.yesterday.push(chatWithIndex);
      } else {
        groups.older.push(chatWithIndex);
      }
    });

    return groups;
  }, [displaySessions, pinnedSessions]);

  const { fontLevel } = useThemeMode();

  const isLoading = valueTab === 1 ? savedLoading : loading;
  const hasSavedChats = (savedSessions?.length || 0) > 0;

  return (
    <Box
      sx={{
        width: { xs: "100%", md: getSidebarWidth(fontLevel) },
        p: 2,
        display: "flex",
        flexDirection: "column",
        boxSizing: "border-box",
        bgcolor: "background.sidebar",
        height: { xs: "100vh", md: "90vh" },
      }}
    >
      <Box
        sx={{
          width: "100%",
          bgcolor: "background.lightblue1",
          p: 0.3,
          borderRadius: 2,
          mb: 1.5,
        }}
      >
        <Tabs
          value={valueTab}
          onChange={(_, newValue) => setValueTab(newValue)}
          TabIndicatorProps={{ style: { display: "none" } }}
          sx={{
            minHeight: 45,
            height: 40,
            width: "100%",
            "& .MuiTabs-flexContainer": {
              gap: 0.5,
              width: "100%",
            },
            "& .MuiTabs-list": {
              display: "flex",
              justifyContent: "space-around",
              alignItems: "center",
            },
            "& .MuiTabs-scroller": {
              display: "flex",
              mx: 0.5,
            },
          }}
        >
          <Tab
            icon={
              <Message
                size={18}
                color={
                  valueTab === 0
                    ? "#ffffff"
                    : mode === "dark"
                      ? "#1cb0f6"
                      : "#106BA3"
                }
              />
            }
            iconPosition="start"
            label="My Chats"
            sx={tabStyle(valueTab === 0)}
          />

          <Tab
            icon={
              <SaveIcon
                size={18}
                color={
                  valueTab === 1
                    ? "#ffffff"
                    : mode === "dark"
                      ? "#1cb0f6"
                      : "#106BA3"
                }
              />
            }
            iconPosition="start"
            label="Saved Chats"
            sx={tabStyle(valueTab === 1)}
          />
        </Tabs>
      </Box>

      <Box
        sx={{
          display: "flex",
          gap: 0.5,
          border: "1",
          mb: 2,
          justifyContent: "space-between",
        }}
      >
        <TextField
          placeholder="Search here..."
          size="small"
          onChange={(e) => setSearchTerm(e.target.value)}
          sx={{
            bgcolor: "background.grey",
            border: "none",
            height: 35,
            width: "100%",
            borderRadius: 2,
            "& .MuiOutlinedInput-root": {
              height: 35,
              borderRadius: 2,
              fontSize: 10,
              border: "none",
              color: "text.placeholder",
              "& fieldset": {
                border: "none",
              },
              "&:hover fieldset": {
                border: "none",
              },
              "&.Mui-focused fieldset": {
                border: "none",
              },
            },
            "& .MuiOutlinedInput-input": {
              padding: "0 8px",
            },
          }}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <Search size={18} color={"#0f1c2e"} />
                </InputAdornment>
              ),
            },
          }}
        />
      </Box>

      <Typography variant={"body2"} sx={{ mb: 1, color: "text.smallheading" }}>
        {valueTab === 0 ? "Your Chats" : "Saved Chats"}
      </Typography>

      <Box
        sx={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: 1,
          pr: 0.5,
        }}
      >
        {isLoading ? (
          <Stack spacing={1}>
            {[...Array(6)].map((_, index) => (
              <Skeleton
                key={index}
                variant="rounded"
                height={35}
                animation="wave"
                sx={{ borderRadius: 2 }}
              />
            ))}
          </Stack>
        ) : valueTab === 1 && !hasSavedChats ? (
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              minHeight: 200,
              gap: 2,
            }}
          >
            <SaveIcon
              size={48}
              color={mode === "dark" ? "#1cb0f6" : "#106BA3"}
              opacity={0.5}
            />
            <Typography
              variant="body2"
              sx={{
                fontSize: 14,
                color: "text.secondary",
                textAlign: "center",
                fontWeight: 500,
              }}
            >
              NO SAVED CHATS
            </Typography>
            <Typography
              variant="caption"
              sx={{
                fontSize: 12,
                color: "text.disabled",
                textAlign: "center",
              }}
            >
              Pin or save your favorite chats to see them here
            </Typography>
          </Box>
        ) : displaySessions && displaySessions.length ? (
          <>
            {groupedSessions.pinned.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 600,
                    mb: 1,
                    display: "block",
                    fontSize: 11,
                    letterSpacing: "0.5px",
                  }}
                >
                  PINNED
                </Typography>
                <Stack spacing={1}>
                  {groupedSessions.pinned.map((chat) => (
                    <ChatItem
                      key={chat.session_id || chat.originalIndex}
                      title={chat.title}
                      tabType={valueTab}
                      isSaved={chat.is_saved}
                      onSave={(chat) => {
                        setSavedSessions((prev) => {
                          const exists = prev.some(
                            (s) => s.session_id === chat.session_id,
                          );
                          if (exists) return prev;
                          return [chat, ...prev];
                        });
                      }}
                      onToggleSave={handleToggleSave}
                      active={chat.session_id === currentSessionId}
                      sessionId={chat.session_id}
                      isPinned={true}
                      onTogglePin={handleTogglePin}
                      onDelete={(id) => {
                        if (valueTab === 1) {
                          setSavedSessions((prev) =>
                            prev.filter((s) => s.session_id !== id),
                          );
                        } else {
                          setLocalSessions((prev) =>
                            prev.filter((s) => s.session_id !== id),
                          );
                        }
                      }}
                      onClick={() => {
                        setActiveIndex(chat.originalIndex);
                        selectSession(chat.session_id);
                        setSidebarOpen(false);
                      }}
                    />
                  ))}
                </Stack>
              </Box>
            )}

            {groupedSessions.today.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 600,
                    mb: 1,
                    display: "block",
                    fontSize: 11,
                    letterSpacing: "0.5px",
                  }}
                >
                  RECENT
                </Typography>
                <Stack spacing={1}>
                  {groupedSessions.today.map((chat) => (
                    <ChatItem
                      key={chat.session_id || chat.originalIndex}
                      title={chat.title}
                      tabType={valueTab}
                      isSaved={chat.is_saved}
                      onSave={(chat) => {
                        // ✅ update saved tab
                        setSavedSessions((prev) => {
                          const exists = prev.some(
                            (s) => s.session_id === chat.session_id,
                          );
                          if (exists) return prev;
                          return [chat, ...prev];
                        });
                      }}
                      onToggleSave={handleToggleSave}
                      onUpdateSession={(id, updates) => {
                        // fetchSessions(); // OR better: update local state if you store it
                      }}
                      active={chat.session_id === currentSessionId}
                      sessionId={chat.session_id}
                      isPinned={false}
                      onTogglePin={handleTogglePin}
                      onDelete={(id) => {
                        if (valueTab === 1) {
                          setSavedSessions((prev) =>
                            prev.filter((s) => s.session_id !== id),
                          );
                        } else {
                          setLocalSessions((prev) =>
                            prev.filter((s) => s.session_id !== id),
                          );
                        }
                      }}
                      onClick={() => {
                        setActiveIndex(chat.originalIndex);
                        selectSession(chat.session_id);
                        setSidebarOpen(false);
                      }}
                    />
                  ))}
                </Stack>
              </Box>
            )}

            {groupedSessions.yesterday.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 600,
                    mb: 1,
                    display: "block",
                    fontSize: 11,
                    letterSpacing: "0.5px",
                  }}
                >
                  PREVIOUS
                </Typography>
                <Stack spacing={1}>
                  {groupedSessions.yesterday.map((chat) => (
                    <ChatItem
                      key={chat.session_id || chat.originalIndex}
                      title={chat.title}
                      tabType={valueTab}
                      isSaved={chat.is_saved}
                      onToggleSave={handleToggleSave}
                      onSave={(chat) => {
                        // ✅ update saved tab
                        setSavedSessions((prev) => {
                          const exists = prev.some(
                            (s) => s.session_id === chat.session_id,
                          );
                          if (exists) return prev;
                          return [chat, ...prev];
                        });
                      }}
                      onUpdateSession={(id, updates) => {
                        // ✅ update My Chats tab
                        // fetchSessions(); // OR better: update local state if you store it
                      }}
                      active={chat.session_id === currentSessionId}
                      sessionId={chat.session_id} // ✅ ADD THIS
                      isPinned={false}
                      onTogglePin={handleTogglePin}
                      onDelete={(id) => {
                        if (valueTab === 1) {
                          setSavedSessions((prev) =>
                            prev.filter((s) => s.session_id !== id),
                          );
                        } else {
                          setLocalSessions((prev) =>
                            prev.filter((s) => s.session_id !== id),
                          );
                        }
                      }}
                      onClick={() => {
                        setActiveIndex(chat.originalIndex);
                        selectSession(chat.session_id);
                        setSidebarOpen(false);
                      }}
                    />
                  ))}
                </Stack>
              </Box>
            )}

            {groupedSessions.older.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 600,
                    mb: 1,
                    display: "block",
                    fontSize: 11,
                    letterSpacing: "0.5px",
                  }}
                >
                  OLDER
                </Typography>
                <Stack spacing={1}>
                  {groupedSessions.older.map((chat) => (
                    <ChatItem
                      key={chat.session_id || chat.originalIndex}
                      title={chat.title}
                      tabType={valueTab}
                      isSaved={chat.is_saved}
                      onToggleSave={handleToggleSave}
                      onSave={(chat) => {
                        //  update saved tab
                        setSavedSessions((prev) => {
                          const exists = prev.some(
                            (s) => s.session_id === chat.session_id,
                          );
                          if (exists) return prev;
                          return [chat, ...prev];
                        });
                      }}
                      isPinned={false}
                      onTogglePin={handleTogglePin}
                      onDelete={(id) => {
                        if (valueTab === 1) {
                          setSavedSessions((prev) =>
                            prev.filter((s) => s.session_id !== id),
                          );
                        } else {
                          setLocalSessions((prev) =>
                            prev.filter((s) => s.session_id !== id),
                          );
                        }
                      }}
                      active={chat.session_id === currentSessionId}
                      onClick={() => {
                        setActiveIndex(chat.originalIndex);
                        selectSession(chat.session_id);
                        setSidebarOpen(false);
                      }}
                    />
                  ))}
                </Stack>
              </Box>
            )}
          </>
        ) : (
          <Typography
            variant={"body2"}
            sx={{ fontSize: 12, color: "text.secondary" }}
          >
            {valueTab === 0
              ? "Your chat history is empty."
              : "No saved chats available."}
          </Typography>
        )}
      </Box>
      <Dialog
        open={openFilter}
        sx={{
          "& .MuiDialog-container": {
            width: { xs: "100vw", md: "80vw" },
            height: "90vh",
            marginTop: "10vh",
            marginLeft: { xs: 0, md: "20vw" },
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          },
        }}
        onClose={() => {
          setOpenFilter(false);
        }}
        BackdropProps={{
          sx: {
            width: { xs: "100vw", md: "80vw" },
            height: "90vh",
            marginTop: "10vh",
            marginLeft: { xs: 0, md: "20vw" },
            backdropFilter: "blur(1px)",
          },
        }}
        PaperProps={{
          sx: {
            borderRadius: 5,
            width: 360,
            border: "1.5px solid",
            borderColor: "primary.main",
          },
        }}
      >
        <DialogContent>
          <Typography fontSize={18} fontWeight={600} mb={2}>
            Filter
          </Typography>

          <RadioGroup
            value={filterValue}
            onChange={(e) => setFilterValue(e.target.value)}
          >
            <FormControlLabel
              value="pinned"
              control={<Radio />}
              label="Pinned Chat"
            />
          </RadioGroup>

          <Box display="flex" justifyContent="flex-end" mt={3}>
            <Button
              variant="contained"
              startIcon={<CheckRoundedIcon />}
              onClick={() => {
                setOpenFilter(false);
              }}
              sx={{
                borderRadius: 2,
                px: 3,
                textTransform: "none",
                boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
              }}
            >
              Apply
            </Button>
          </Box>
        </DialogContent>
      </Dialog>
    </Box>
  );
};

export default ChatSideBar;
