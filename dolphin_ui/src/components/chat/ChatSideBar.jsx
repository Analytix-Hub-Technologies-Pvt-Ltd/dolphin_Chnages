import {
  Box,
  InputAdornment,
  Stack,
  TextField,
  Typography,
  Skeleton,
  Avatar,
  Button,
  IconButton,
  Tabs,
  Tab,
  Dialog,
  DialogContent,
  RadioGroup,
  FormControlLabel,
  Radio,
} from "@mui/material";
import React, { useEffect, useState } from "react";
import { ChatItem } from "./ChatItem";
import LightModeIcon from "@mui/icons-material/LightMode";
import { useThemeMode } from "../../context/ThemeModeContext";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import { Message } from "../../assets/svgIcons/message";
import { SaveIcon } from "../../assets/svgIcons/Saveicon";
import { Search } from "../../assets/svgIcons/Search";
import { FilterIcon } from "../../assets/svgIcons/FilterIcon";
import CheckRoundedIcon from "@mui/icons-material/CheckRounded";
import { getSidebarWidth } from "../../theme/layoutScale";

const ChatSideBar = ({
  sessionData,
  activeIndex,
  setActiveIndex,
  selectSession,
  loading,
  sidebarOpen,
  setSidebarOpen,
  fetchSessions,
}) => {
  const { mode } = useThemeMode();
  const [valueTab, setValueTab] = useState(0);

  const [openFilter, setOpenFilter] = useState(false);
  const [filterValue, setFilterValue] = useState("pinned");

  const [searchTerm, setSearchTerm] = useState("");

  const [userData, setUserData] = useState(() => {
    try {
      const stored = localStorage.getItem("userData");
      return stored ? JSON.parse(stored) : null;
    } catch (e) {
      return null;
    }
  });

  useEffect(() => {
    const delayDebounce = setTimeout(() => {
      fetchSessions(searchTerm);
    }, 400); // debounce delay (ms)

    return () => clearTimeout(delayDebounce);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchTerm]);

  const tabStyle = (active) => ({
    flex: "0 0 auto", // 👈 do NOT grow
    width: "auto",
    // textTransform: "none",
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

  const { fontLevel } = useThemeMode();
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
            width: "85%",
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
        <Box
          sx={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            height: 35,
            width: 35,
            borderRadius: 2,
            bgcolor: "background.grey",
            cursor: "pointer",
          }}
          onClick={() => {
            setSidebarOpen(false);
            setOpenFilter(true);
          }}
        >
          <FilterIcon
            size={20}
            color={mode === "dark" ? "#1cb0f6" : "#106BA3"}
          />
        </Box>
      </Box>

      <Typography variant={"body2"} sx={{ mb: 1, color: "text.smallheading" }}>
        Your Chats
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
        {loading ? (
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
        ) : sessionData && sessionData.length ? (
          sessionData.map((chat, index) => (
            <ChatItem
              key={chat.session_id || index}
              title={chat.title}
              active={index === activeIndex}
              onClick={() => {
                setActiveIndex(index);
                selectSession(chat.session_id);
                setSidebarOpen(false);
              }}
            />
          ))
        ) : (
          <Typography
            variant={"body2"}
            sx={{ fontSize: 12, color: "text.secondary" }}
          >
            Your chat history is empty.
          </Typography>
        )}
      </Box>

      <Box sx={{ display: "flex", alignItems: "center" }}>
        <Avatar sx={{ width: 35, height: 35, bgcolor: "primary.main", fontSize: "0.9rem", fontWeight: 700 }}>
          {userData?.name ? userData.name.charAt(0).toUpperCase() : "U"}
        </Avatar>
        <Box
          sx={{ display: "flex", flexDirection: "column", width: "70%", pl: 1 }}
        >
          <Typography variant="body1" color="primary.main">
            {userData?.name
              ? userData.name.charAt(0).toUpperCase() + userData.name.slice(1)
              : ""}
          </Typography>
          <Typography variant="caption" color="primary.main" fontWeight={500}>
            {userData?.email || ""}
          </Typography>
        </Box>
        <IconButton
          // onClick={toggleMode}
          sx={{
            width: 35,
            height: 35,
            background: "linear-gradient(180deg, #1187D6 0%, #2F428D 100%)",
            padding: 2,
            "&:hover": {
              bgcolor: "primary.main",
            },
          }}
        >
          {mode === "dark" ? (
            <DarkModeOutlinedIcon sx={{ color: "text.primary" }} />
          ) : (
            <LightModeIcon sx={{ color: "background.default" }} />
          )}
        </IconButton>
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
            // p: 2,
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
