import React, { useState } from "react";
import MainLayout from "../../layouts/MainLayout";
import Header from "../../components/header/Header";
import AdminSidebar from "../../components/admin/AdminSidebar";
import { Outlet } from "react-router-dom";

const AdminPage = ({ onLogout }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <MainLayout
      header={
        <Header
          onLogout={onLogout}
          sidebarOpen={sidebarOpen}
          setSidebarOpen={setSidebarOpen}
          drawerContent={<AdminSidebar setSidebarOpen={setSidebarOpen} />}
        />
      }
      leftPanel={<AdminSidebar setSidebarOpen={setSidebarOpen} />}
      contentPanel={
        <div className="flex-1 min-w-0 overflow-y-auto overflow-x-hidden bg-bg-default h-full w-full max-w-full">
          <Outlet />
        </div>
      }
    />
  );
};

export default AdminPage;
