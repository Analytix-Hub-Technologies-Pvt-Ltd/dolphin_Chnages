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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Avatar,
  Tooltip,

} from "@mui/material";
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import AddRoundedIcon from "@mui/icons-material/AddRounded";
import MenuIcon from "@mui/icons-material/Menu";
import AccountCircleOutlinedIcon from "@mui/icons-material/AccountCircleOutlined";
import ArrowBackIosNewIcon from "@mui/icons-material/ArrowBackIosNew";
import HistoryIcon from "@mui/icons-material/History";

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
  savedSessions,
  drawerContent,
}) => {
  const theme = useTheme();
  const navigate = useNavigate();
  const { mode, toggleMode } = useThemeMode();

  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const isTablet = useMediaQuery(theme.breakpoints.between("sm", "md"));

  const [anchorElFont, setAnchorElFont] = useState(null);
  const [logoutDialogOpen, setLogoutDialogOpen] = useState(false);
  const [settingsView, setSettingsView] = useState("general");
  const userData = JSON.parse(localStorage.getItem("userData") || "{}");
  const profile = userData.user_profile || userData;

  const { fontLevel, setFontLevel } = useThemeMode();

  const handleOpenFontMenu = (event) => {
    setAnchorElFont(event.currentTarget);
  };

  const openFontMenu = Boolean(anchorElFont);
  const handleCreateNewSession = async () => {
    if (setCurrentSessionData) setCurrentSessionData(null);
    if (setActiveIndex) setActiveIndex(null);
    if (setCurrentSessionId) setCurrentSessionId(null);
    if (setmessages) setmessages([]);
    localStorage.removeItem("active_session_id");
    navigate("/");
  };

  // Handle logout button click - open confirmation dialog
  const handleLogoutClick = () => {
    setLogoutDialogOpen(true);
  };

  // Handle confirm logout
  const handleConfirmLogout = () => {
    setLogoutDialogOpen(false);
    onLogout();
  };

  // Handle cancel logout
  const handleCancelLogout = () => {
    setLogoutDialogOpen(false);
  };

  // const handleDummyClick = async () => {
  //   try {
  //     await newSession((chunk) => {
  //       //  Do nothing with UI
  //       console.log("Streaming chunk:", chunk);
  //     });
  //   } catch (err) {
  //     console.error("Streaming error:", err);
  //   }
  // };

  return (
    <>
      {/* == HEADER == */}
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
          <Box
            display="flex"
            alignItems="center"
            gap={{ xs: 1.5, sm: 2, md: 3.5 }}
          >
            {(isMobile || isTablet) && (
              <IconButton onClick={() => setSidebarOpen && setSidebarOpen(true)}>
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
                    fontWeight: 700,
                    color: "text.heading1",
                  }}
                >
                  Dolphin
                </Typography>
                <Typography
                  variant="h2"
                  sx={{
                    fontWeight: 700,
                    color: "text.heading1",
                  }}
                >
                  |
                </Typography>
                <Typography
                  variant="h2"
                  sx={{
                    fontWeight: 700,
                    color: "primary.main",
                  }}
                >
                  AI
                </Typography>
              </Box>
            )}

            {/* Connection Status */}

          </Box>

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

            {/* User Avatar */}
            <Tooltip title="Profile">
              <IconButton
                onClick={(e) => {
                  setSettingsView("profile");
                  handleOpenFontMenu(e);
                }}
                sx={{ p: 0.5 }}
              >
                <Avatar
                  sx={{
                    width: 35,
                    height: 35,
                    bgcolor: "primary.main",
                    fontSize: "1rem",
                    fontWeight: 600,
                    border: "2px solid",
                    borderColor: mode === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.05)"
                  }}
                >
                  {profile?.name?.charAt(0).toUpperCase() || "U"}
                </Avatar>
              </IconButton>
            </Tooltip>

            {/* Logout - Updated with confirmation */}
            <Button
              startIcon={<LogoutOutlinedIcon sx={{ color: "text.primary" }} />}
              onClick={handleLogoutClick}
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

      {/* dialog box for logout */}

      <Dialog
        open={logoutDialogOpen}
        onClose={handleCancelLogout}
        maxWidth="xs"
        fullWidth
        BackdropProps={{
          sx: {
            backdropFilter: "blur(10px)",
            backgroundColor: "rgba(0,0,0,0.2)",
          },
        }}
        PaperProps={{
          sx: {
            borderRadius: 2,
            px: 1,
            border: "1.5px solid #38bdf8",
            boxShadow: "0 8px 30px rgba(56,189,248,0.25)",
          },
        }}
      >
        <DialogTitle sx={{ pb: 1, fontWeight: 600 }}>
          Confirm Logout
        </DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ color: "text.secondary" }}>
            Are you sure you want to logout? You will need to login again to
            access your chats.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2, gap: 1 }}>
          <Button
            onClick={handleCancelLogout}
            variant="outlined"
            sx={{
              textTransform: "none",
              fontWeight: 600,
              borderRadius: 2,
            }}
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirmLogout}
            variant="contained"
            color="primary"
            sx={{
              textTransform: "none",
              fontWeight: 600,
              borderRadius: 2,
            }}
            autoFocus
          >
            Logout
          </Button>
        </DialogActions>
      </Dialog>

      <Drawer
        anchor="left"
        open={sidebarOpen}
        onClose={() => setSidebarOpen && setSidebarOpen(false)}
        ModalProps={{ keepMounted: true }}
        PaperProps={{
          sx: {
            width: 280,
            backgroundColor: "background.default",
            height: "100vh",
          },
        }}
      >
        {drawerContent || (
          <ChatSidebar
            onClose={() => setSidebarOpen && setSidebarOpen(false)}
            sessionData={sessionData}
            savedSessions={savedSessions}
            loading={loading}
            activeIndex={activeIndex}
            setActiveIndex={setActiveIndex}
            sidebarOpen={sidebarOpen}
            setSidebarOpen={setSidebarOpen}
            selectSession={selectSession}
            fetchSessions={fetchSessions}
          />
        )}
      </Drawer>

      {/* = FONT POPOVER = */}
      <Popover
        open={openFontMenu}
        anchorEl={anchorElFont}
        onClose={() => {
          setAnchorElFont(null);
          setSettingsView("general");
        }}
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
            py: 3,
            px: 4,
            width: 350,
            borderRadius: 4,
            mt: 2,
            boxShadow: "0 10px 40px rgba(0,0,0,0.1)",
            border: "1px solid",
            borderColor: "divider",
            backgroundColor: "background.paper",
          },
        }}
      >
        {settingsView === "general" ? (
          <>
            <Box
              display="flex"
              justifyContent="space-between"
              alignItems="center"
              mb={2}
            >
              <Typography variant="h4" fontWeight={700}>
                Settings
              </Typography>
              <Button
                size="small"
                startIcon={<AccountCircleOutlinedIcon />}
                onClick={() => setSettingsView("profile")}
                sx={{ textTransform: "none", borderRadius: 2 }}
              >
                View Profile
              </Button>
            </Box>

            <Box
              display="flex"
              alignItems="center"
              gap={2}
              p={1.5}
              mb={2}
              sx={{
                bgcolor: "action.hover",
                borderRadius: 2,
                cursor: "pointer",
                transition: "opacity 0.2s",
                "&:hover": { opacity: 0.8 }
              }}
              onClick={() => setSettingsView("profile")}
            >
              <Avatar
                sx={{
                  width: 40,
                  height: 40,
                  bgcolor: "primary.main",
                  fontSize: "1.1rem",
                }}
              >
                {profile?.name?.charAt(0).toUpperCase() || "U"}
              </Avatar>
              <Box sx={{ overflow: "hidden" }}>
                <Typography variant="body1" fontWeight={600} noWrap>
                  {profile?.name || "User Name"}
                </Typography>
                <Typography variant="caption" color="text.secondary" noWrap sx={{ display: "block" }}>
                  {profile?.email || "No email provided"}
                </Typography>
              </Box>
            </Box>

            <Divider sx={{ my: 2 }} />

            <Typography variant="body1" fontWeight={600} mb={1}>
              Font Size
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
              sx={{ mb: 1 }}
            />

            <Stack direction="row" justifyContent="space-between" mb={3}>

            </Stack>

            <Divider sx={{ my: 2 }} />

            <Typography variant="body1" fontWeight={600} mb={2}>
              Theme
            </Typography>

            <Stack direction="row" spacing={2}>
              <Button
                fullWidth
                variant={mode === "light" ? "contained" : "outlined"}
                startIcon={<LightModeIcon />}
                onClick={() => mode !== "light" && toggleMode()}
                sx={{ borderRadius: 2, textTransform: "none" }}
              >
                Light
              </Button>
              <Button
                fullWidth
                variant={mode === "dark" ? "contained" : "outlined"}
                startIcon={<DarkModeIcon />}
                onClick={() => mode !== "dark" && toggleMode()}
                sx={{ borderRadius: 2, textTransform: "none" }}
              >
                Dark
              </Button>
            </Stack>
          </>
        ) : (
          <>
            <Box
              display="flex"
              justifyContent="space-between"
              alignItems="center"
              mb={3}
            >
              <Box display="flex" alignItems="center">
                <IconButton
                  size="small"
                  onClick={() => setSettingsView("general")}
                  sx={{ mr: 1 }}
                >
                  <ArrowBackIosNewIcon fontSize="small" />
                </IconButton>
                <Typography variant="h4" fontWeight={700}>
                  Profile
                </Typography>
              </Box>
              <Button
                size="small"
                startIcon={<SettingsOutlinedIcon />}
                onClick={() => setSettingsView("general")}
                sx={{ textTransform: "none", borderRadius: 2 }}
              >
                Settings
              </Button>
            </Box>

            <Box
              display="flex"
              flexDirection="column"
              alignItems="center"
              textAlign="center"
              py={2}
            >
              <Avatar
                sx={{
                  width: 80,
                  height: 80,
                  bgcolor: "primary.main",
                  mb: 2,
                  fontSize: "2rem",
                }}
              >
                {profile?.name?.charAt(0).toUpperCase() || "U"}
              </Avatar>
              <Typography variant="h5" fontWeight={700} gutterBottom>
                {profile?.name || "User Name"}
              </Typography>
              <Typography variant="body2" color="text.secondary" mb={1}>
                {profile?.email || ""}
              </Typography>
              {profile?.role && (
                <Box
                  sx={{
                    bgcolor: "action.hover",
                    px: 2,
                    py: 0.5,
                    borderRadius: 5,
                    mt: 1,
                  }}
                >
                  <Typography variant="caption" fontWeight={600}>
                    {profile.role.toUpperCase()}
                  </Typography>
                </Box>
              )}
            </Box>


            {(userData.user_role === "ADMIN" || userData.user_role === "SUPER_ADMIN") && (
              <>
              <Divider sx={{ my: 3 }} />
              <Button
                fullWidth
                variant="outlined"
                color="primary"
                sx={{ mb: 2, borderRadius: 2, textTransform: "none" }}
                onClick={() => {
                  setAnchorElFont(null);
                  setSettingsView("general");
                  navigate('/admin/feedback');
                }}
              >
                Admin Page
              </Button>
              </>
            )}

          </>
        )}
      </Popover>
    </>
  );
};

export default Header;
