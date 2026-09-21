import React from 'react';
import { History, Users, ArrowLeft } from 'lucide-react';
import { useThemeMode } from '../../context/ThemeModeContext';
import { getSidebarWidth } from '../../theme/layoutScale';
import { useNavigate, useLocation } from 'react-router-dom';

const AdminSidebar = ({ setSidebarOpen }) => {
  const { fontLevel } = useThemeMode();
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    {
      title: 'Chat History',
      icon: <History className="w-5 h-5" />,
      path: '/admin/chat-history'
    },
    {
      title: 'Members',
      icon: <Users className="w-5 h-5" />,
      path: '/admin/members'
    }
  ];

  return (
    <aside
      style={{ width: typeof window !== 'undefined' && window.innerWidth >= 768 ? getSidebarWidth(fontLevel) : '100%' }}
      className="p-4 flex flex-col box-border bg-bg-sidebar h-screen md:h-[90vh] border-r border-border-theme shrink-0"
    >
      <h2 className="mb-4 font-semibold text-lg px-2 text-text-primary">
        Admin Panel
      </h2>

      <div className="px-1 mb-4">
        <button
          type="button"
          onClick={() => {
            navigate("/");
            if (setSidebarOpen) setSidebarOpen(false);
          }}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg border border-primary text-primary font-semibold text-[0.82rem] transition-colors duration-200 hover:bg-primary hover:text-white"
        >
          <ArrowLeft className="w-4 h-4" />
          Return to Chat
        </button>
      </div>

      <nav className="w-full space-y-1">
        {menuItems.map((item) => {
          const isActive = location.pathname.includes(item.path);
          return (
            <button
              key={item.title}
              type="button"
              onClick={() => {
                navigate(item.path);
                if (setSidebarOpen) setSidebarOpen(false);
              }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors duration-150 text-left ${
                isActive
                  ? 'bg-primary text-white font-semibold'
                  : 'text-text-secondary hover:bg-bg-lightblue1/40 hover:text-text-primary font-medium'
              }`}
            >
              <span className={`shrink-0 ${isActive ? 'text-white' : 'text-text-secondary'}`}>
                {item.icon}
              </span>
              <span>{item.title}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
};

export default AdminSidebar;
