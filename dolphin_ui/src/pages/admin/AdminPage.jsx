import React, { useState } from "react";
import MainLayout from "../../layouts/MainLayout";
import Header from "../../components/header/Header";
import AdminSidebar from "../../components/admin/AdminSidebar";
import { Outlet } from "react-router-dom";
import { Box } from "@mui/material";

const AdminPage = ({ onLogout, feedbackOnly = false }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <MainLayout
      header={
        <Header
          onLogout={onLogout}
          sidebarOpen={sidebarOpen}
          setSidebarOpen={setSidebarOpen}
          drawerContent={<AdminSidebar setSidebarOpen={setSidebarOpen} feedbackOnly={feedbackOnly} />}
        />
      }
      leftPanel={<AdminSidebar setSidebarOpen={setSidebarOpen} feedbackOnly={feedbackOnly} />}
      contentPanel={
        <Box sx={{ flex: 1, minWidth: 0, overflowY: "auto", bgcolor: 'background.default', height: "100%" }}>
          <Outlet />
        </Box>
      }
    />
  );
};

export default AdminPage;
