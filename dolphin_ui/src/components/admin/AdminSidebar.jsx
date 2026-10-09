import React from 'react';
import { Box, Button, Typography, List, ListItem, ListItemIcon, ListItemText, ListItemButton } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import HistoryIcon from '@mui/icons-material/History';
import GroupIcon from '@mui/icons-material/Group';
import RateReviewIcon from '@mui/icons-material/RateReview';
import { useThemeMode } from '../../context/ThemeModeContext';
import { getSidebarWidth } from '../../theme/layoutScale';
import { useNavigate, useLocation } from 'react-router-dom';
import { isFeedbackAuthorized, getCurrentUserEmail, getCurrentUserRole } from '../../utils/feedbackAuth';

const AdminSidebar = ({ setSidebarOpen, feedbackOnly = false }) => {
  const { fontLevel } = useThemeMode();
  const navigate = useNavigate();
  const location = useLocation();

  const isFeedbackAllowed = isFeedbackAuthorized(getCurrentUserEmail(), getCurrentUserRole());

  const allMenuItems = [
    {
      title: 'Feedback & Learning',
      icon: <RateReviewIcon />,
      path: feedbackOnly ? '/feedback' : '/admin/feedback',
      feedbackOnly: true
    },
    {
      title: 'Chat History',
      icon: <HistoryIcon />,
      path: '/admin/chat-history'
    },
    {
      title: 'Members',
      icon: <GroupIcon />,
      path: '/admin/members'
    }
  ];

  const menuItems = allMenuItems.filter(item => (!feedbackOnly || item.feedbackOnly) && (!item.feedbackOnly || isFeedbackAllowed));

  return (
    <Box
      sx={{
        width: { xs: "100%", md: getSidebarWidth(fontLevel) },
        p: 2,
        flexShrink: 0,
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        boxSizing: "border-box",
        bgcolor: "background.sidebar",
        height: { xs: "100vh", md: "90vh" },
        borderRight: "1px solid",
        borderColor: "divider"
      }}
    >
      <Button
        startIcon={<ArrowBackIcon />}
        onClick={() => {
          navigate('/');
          if (setSidebarOpen) setSidebarOpen(false);
        }}
        sx={{ mb: 2, px: 2, justifyContent: 'flex-start', textTransform: 'none', borderRadius: 2 }}
      >
        Back to Chat
      </Button>
      <Typography variant="h6" sx={{ mb: 2, fontWeight: 600, px: 2, color: 'text.primary' }}>
        Admin Panel
      </Typography>
      
      <List sx={{ width: '100%' }}>
        {menuItems.map((item) => {
          const isActive = location.pathname.includes(item.path);
          return (
            <React.Fragment key={item.title}>
            <ListItem disablePadding sx={{ mb: 1 }}>
              <ListItemButton
                selected={isActive}
                onClick={() => {
                  navigate(item.path);
                  if (setSidebarOpen) setSidebarOpen(false);
                }}
                sx={{
                  borderRadius: 2,
                  '&.Mui-selected': {
                    bgcolor: 'primary.main',
                    color: 'primary.contrastText',
                    '&:hover': {
                      bgcolor: 'primary.dark',
                    },
                    '& .MuiListItemIcon-root': {
                      color: 'primary.contrastText',
                    }
                  }
                }}
              >
                <ListItemIcon sx={{ minWidth: 40, color: isActive ? 'primary.contrastText' : 'text.secondary' }}>
                  {item.icon}
                </ListItemIcon>
                <ListItemText 
                  primary={item.title} 
                  primaryTypographyProps={{ 
                    fontWeight: isActive ? 600 : 500,
                    fontSize: '0.9rem'
                  }} 
                />
              </ListItemButton>
            </ListItem>
            {item.feedbackOnly && (
              <List disablePadding aria-label="Feedback & Learning" sx={{ pl: 3, mb: 1 }}>
                {["Dashboard", "Pending", "Approved"].map((title) => {
                  const path = `${item.path}/${title.toLowerCase()}`;
                  const selected = location.pathname === path || location.pathname.startsWith(`${path}/`)
                    || (title === "Dashboard" && location.pathname.replace(/\/$/, "") === item.path);
                  return (
                    <ListItem key={title} disablePadding>
                      <ListItemButton selected={selected} aria-current={selected ? "page" : undefined}
                        sx={{ borderRadius: 2, color: selected ? "primary.main" : "text.secondary" }}
                        onClick={() => { navigate(path); if (setSidebarOpen) setSidebarOpen(false); }}>
                        <ListItemText primary={title} primaryTypographyProps={{ fontSize: "0.85rem", fontWeight: selected ? 700 : 400 }} />
                      </ListItemButton>
                    </ListItem>
                  );
                })}
              </List>
            )}
            </React.Fragment>
          );
        })}
      </List>
    </Box>
  );
};

export default AdminSidebar;
