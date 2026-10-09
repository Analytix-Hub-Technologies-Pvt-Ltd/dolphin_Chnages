import React from "react";
import { BarChart3, Clock, CheckCircle2 } from "lucide-react";

const NAV_ITEMS = [
  {
    id: "dashboard",
    index: 0,
    label: "Dashboard",
    icon: BarChart3,
    path: "/feedback/dashboard",
  },
  {
    id: "pending",
    index: 1,
    label: "Pending",
    icon: Clock,
    badgeKey: "pending_count",
    badgeColor: "bg-amber-500 text-white",
    path: "/feedback/pending",
  },
  {
    id: "approved",
    index: 2,
    label: "Approved",
    icon: CheckCircle2,
    badgeKey: "approved_count",
    badgeColor: "bg-green-600 text-white",
    path: "/feedback/approved",
  },
];

const FeedbackSidebar = ({
  activeTab = 0,
  onTabChange,
  stats = { pending_count: 0, approved_count: 0 },
}) => {
  return (
    <aside className="fb-sidebar" style={{ width: 220, minWidth: 220, maxWidth: 220, flexShrink: 0 }}>
      <div className="fb-sidebar-nav-label">
        Navigation
      </div>

      {NAV_ITEMS.map((item) => {
        const isActive = activeTab === item.index;
        const Icon = item.icon;
        const count = item.badgeKey ? stats[item.badgeKey] || 0 : null;

        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onTabChange(item.index, item.path)}
            className={`fb-sidebar-item ${isActive ? "active" : ""}`}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 14px",
              borderRadius: 12,
              fontSize: 13,
              cursor: "pointer",
              backgroundColor: isActive ? "rgba(16, 107, 163, 0.12)" : "transparent",
              color: isActive ? "#106BA3" : "#5c7080",
              fontWeight: isActive ? 700 : 500,
              border: isActive ? "1px solid rgba(16, 107, 163, 0.3)" : "1px solid transparent",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Icon style={{ width: 16, height: 16, color: isActive ? "#106BA3" : "#5c7080", flexShrink: 0 }} />
              <span>{item.label}</span>
            </div>

            {count !== null && count > 0 && (
              <span
                style={{
                  marginLeft: 8,
                  padding: "2px 8px",
                  borderRadius: 10,
                  fontSize: 11,
                  fontWeight: 700,
                  backgroundColor: item.id === "pending" ? "#f59e0b" : "#16a34a",
                  color: "#ffffff",
                }}
              >
                {count > 999 ? "999+" : count}
              </span>
            )}
          </button>
        );
      })}
    </aside>
  );
};

export default React.memo(FeedbackSidebar);
