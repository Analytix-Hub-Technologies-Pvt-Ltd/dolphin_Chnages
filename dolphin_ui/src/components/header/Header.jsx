import {
  AppBar,
  Box,
  Button,
  IconButton,
  Popover,
  Slider,
  Stack,
  Toolbar,
  Typography,
  Drawer,
  useMediaQuery,
  Divider,
} from "@mui/material";
import React, { useState } from "react";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import AddRoundedIcon from "@mui/icons-material/AddRounded";
import MenuIcon from "@mui/icons-material/Menu";
import TextFieldsIcon from "@mui/icons-material/TextFields";

import DolphinIconB from "../../assets/images/dolphin_b.png";
import DolphinIconW from "../../assets/images/dolphin_w.png";
import ShipIconB from "../../assets/images/ship.png";
import ShipIconW from "../../assets/images/ship_w.png";

import { useTheme } from "@mui/material/styles";
import { useThemeMode } from "../../context/ThemeModeContext";

import DarkModeIcon from "@mui/icons-material/DarkMode";

import LightModeIcon from "@mui/icons-material/LightMode";
import ChatSidebar from "../chat/ChatSideBar";

const Header = ({
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
}) => {
  const theme = useTheme();
   const { mode, toggleMode } = useThemeMode();

  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const isTablet = useMediaQuery(theme.breakpoints.between("sm", "md"));

  const [anchorElFont, setAnchorElFont] = useState(null);

  const { fontLevel, setFontLevel } = useThemeMode();

  const handleOpenFontMenu = (event) => {
    setAnchorElFont(event.currentTarget);
  };

  const openFontMenu = Boolean(anchorElFont);

  const handleCreateNewSession = async () => {
    setCurrentSessionData();
    setActiveIndex(null);
    setCurrentSessionId(null);
    setmessages([]);
  };

  return (
    <>
      {/* ================= HEADER ================= */}
      <AppBar
        position="static"
        elevation={0}
        sx={{
          height: "10vh",
          backgroundColor: "background.header",
          justifyContent: "center",
        }}
      >
        <Toolbar
          sx={{
            height: "100%",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            px: { xs: 1, sm: 3, md: 4 },
          }}
        >
          {/* ================= LEFT ================= */}
          <Box
            display="flex"
            alignItems="center"
            gap={{ xs: 1.5, sm: 2, md: 3.5 }}
          >
            {(isMobile || isTablet) && (
              <IconButton onClick={() => setSidebarOpen(true)}>
                <MenuIcon sx={{ color: "text.primary" }} />
              </IconButton>
            )}

            <Box
              component="img"
              src={mode === "dark" ? DolphinIconW : DolphinIconB}
              alt="Dolphin"
              sx={{
                width: { xs: 40, sm: 34, md: 60 },
                height: { xs: 40, sm: 34, md: 60 },
              }}
            />

            <Box
              component="img"
              src={mode === "dark" ? ShipIconW : ShipIconB}
              alt="Ship"
              sx={{
                width: { xs: 30, sm: 34, md: 40 },
                height: { xs: 30, sm: 34, md: 40 },
              }}
            />

            {/* Desktop title (UNCHANGED) */}
            {!isMobile && !isTablet && (
              <Box sx={{ display: "flex", gap: 1.5 }}>
                <Typography
                  variant="h2"
                  sx={{
                    // fontSize: 22,
                    fontWeight: 700,
                    color: "text.heading1",
                  }}
                >
                  Dolphin
                </Typography>
                <Typography
                  variant="h2"
                  sx={{
                    // fontSize: 22,
                    fontWeight: 700,
                    color: "text.heading1",
                  }}
                >
                  |
                </Typography>
                <Typography
                  variant="h2"
                  sx={{
                    // fontSize: 22,
                    fontWeight: 700,
                    color: "primary.main",
                  }}
                >
                  AI
                </Typography>
              </Box>
            )}

            {/* Connection */}
            <Box display="flex" alignItems="center" gap={1}>
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  backgroundColor: "#22c55e",
                }}
              />
              {!isMobile && (
                <Typography variant="body2" color="text.secondary">
                  Connected
                </Typography>
              )}
            </Box>
          </Box>

          {/* ================= RIGHT ================= */}
          <Stack
            direction="row"
            spacing={{ xs: 0.5, sm: 1, md: 2 }}
            alignItems="center"
          >
            {/* New Chat */}
            <Button
              disabled={disableNewChat}
              onClick={handleCreateNewSession}
              variant="contained"
              startIcon={!isMobile && <AddRoundedIcon />}
              sx={{
                backgroundColor: "background.light",
                color: "text.primary",
                textTransform: "none",
                fontWeight: 600,
                boxShadow: "none",
                minWidth: isMobile ? 40 : "auto",
                px: isMobile ? 1 : 2,
                "&:hover": {
                  backgroundColor: "background.light",
                  boxShadow: "none",
                },
              }}
            >
              {!isMobile && "New Chat"}
              {isMobile && <AddRoundedIcon />}
            </Button>

            {/* Settings */}
            <Button
              startIcon={
                <SettingsOutlinedIcon sx={{ color: "text.primary" }} />
              }
              onClick={handleOpenFontMenu}
              sx={{
                textTransform: "none",
                color: "text.primary",
                minWidth: isMobile || isTablet ? 40 : "auto",
                px: isMobile || isTablet ? 1 : 2,
              }}
            >
              {!isMobile && !isTablet && "Settings"}
            </Button>

            {/* Logout */}
            <Button
              startIcon={<LogoutOutlinedIcon sx={{ color: "text.primary" }} />}
              onClick={onLogout}
              sx={{
                textTransform: "none",
                color: "text.primary",
                minWidth: isMobile || isTablet ? 40 : "auto",
                px: isMobile || isTablet ? 1 : 2,
              }}
            >
              {!isMobile && !isTablet && "Logout"}
            </Button>
          </Stack>
        </Toolbar>
      </AppBar>

      {/* ================= SIDEBAR DRAWER ================= */}
      <Drawer
        anchor="left"
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        ModalProps={{ keepMounted: true }} // better mobile performance
        PaperProps={{
          sx: {
            width: 280,
            backgroundColor: "background.default",
            height: "100vh",
          },
        }}
      >
        {/* 🔹 YOUR EXISTING CHAT SIDEBAR COMPONENT */}
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
        />
      </Drawer>

      {/* ================= FONT POPOVER ================= */}
      <Popover
        open={openFontMenu}
        anchorEl={anchorElFont}
        onClose={() => setAnchorElFont(null)}
        anchorOrigin={{
          vertical: "bottom",
          horizontal: "right",
        }}
        transformOrigin={{
          vertical: "top",
          horizontal: "right",
        }}
        PaperProps={{
          sx: {
            py: 2,
            px: 5,
            width: 400,
            borderRadius: 5,
            mt: 3,
            boxShadow: "none",
            border: "1px solid",
            borderColor: "primary.main",
            backgroundColor: "background.paper",
          },
        }}
      >
        <Typography variant="h4" fontWeight={600} mb={1}>
          Font
        </Typography>

        <Slider
          value={fontLevel}
          min={0}
          max={2}
          step={1}
          marks={[
            { value: 0, label: "Small" },
            { value: 1, label: "Medium" },
            { value: 2, label: "Large" },
          ]}
          onChange={(_, value) => setFontLevel(value)}
        />

        <Stack direction="row" justifyContent="space-between" mt={1}>
          <Stack alignItems="center">
            <TextFieldsIcon fontSize="small" />
            <Typography variant="caption">Small</Typography>
          </Stack>
          <Stack alignItems="center">
            <TextFieldsIcon />
            <Typography variant="caption">Medium</Typography>
          </Stack>
          <Stack alignItems="center">
            <TextFieldsIcon fontSize="large" />
            <Typography variant="caption">Large</Typography>
          </Stack>
        </Stack>

        <Divider sx={{ my: 1 }} />

        {/* Theme section */}
        <Typography variant="h4" fontWeight={600} mb={2}>
          Theme
        </Typography>

        <Stack direction="row" spacing={1}>
          <Button
            fullWidth
            variant={mode === "dark"?"outlined":"contained"}
            startIcon={<LightModeIcon />}
            size="medium"
            sx={{
              borderRadius: 3,
              // py: 1.5,
              textTransform: "none",
              fontWeight: 600,
            }}
            onClick={toggleMode}
          >
            Light Mode
          </Button>

          <Button
            fullWidth
            variant={mode === "dark"?"contained":"outlined"}
            startIcon={<DarkModeIcon />}
             size="medium"
            sx={{
              borderRadius: 3,
              // py: 1.5,
              textTransform: "none",
              fontWeight: 600,
            }}
            onClick={toggleMode}
          >
            Dark Mode
          </Button>
        </Stack>
      </Popover>
    </>
  );
};

export default Header;
