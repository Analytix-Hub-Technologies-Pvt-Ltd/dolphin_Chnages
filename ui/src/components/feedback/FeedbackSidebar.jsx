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
    <aside className="w-full md:w-56 shrink-0 bg-bg-paper border border-border-theme rounded-2xl p-2 md:p-3 flex md:flex-col gap-1.5 overflow-x-auto md:overflow-x-visible shadow-xs">
      <div className="hidden md:block px-2.5 py-1.5 mb-1 border-b border-border-theme">
        <span className="text-[11px] font-bold uppercase tracking-wider text-text-secondary">
          Navigation
        </span>
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
            className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs transition-all cursor-pointer select-none shrink-0 md:shrink border ${
              isActive
                ? "bg-primary/10 border-primary/30 text-primary font-bold shadow-xs"
                : "border-transparent text-text-secondary hover:text-text-primary hover:bg-black/5 dark:hover:bg-white/5 font-medium"
            }`}
          >
            <div className="flex items-center gap-2.5">
              <Icon className={`w-4 h-4 shrink-0 ${isActive ? "text-primary" : "text-text-secondary"}`} />
              <span className="whitespace-nowrap">{item.label}</span>
            </div>

            {count !== null && count > 0 && (
              <span
                className={`ml-2 px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                  item.badgeColor || "bg-primary text-white"
                }`}
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
