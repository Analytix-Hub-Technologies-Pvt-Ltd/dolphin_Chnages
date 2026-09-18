import React, { useState } from "react";
import { PieChart, ArrowRight } from "lucide-react";

const STATUS_CONFIG = {
  pending: {
    label: "Pending",
    color: "#ed6c02", // Orange
    bgColor: "rgba(237, 108, 2, 0.12)",
    path: "/feedback/pending",
    actionText: "Review Queue",
  },
  approved: {
    label: "Approved",
    color: "#2e7d32", // Green
    bgColor: "rgba(46, 125, 50, 0.12)",
    path: "/feedback/approved",
    actionText: "Memory & DPO",
  },
  rejected: {
    label: "Rejected",
    color: "#757575", // Grey
    bgColor: "rgba(117, 117, 117, 0.12)",
    path: null,
    actionText: "Archived",
  },
};

const ResolutionStatusChart = ({
  resolutionData = [],
  loading = false,
  onNavigateTab,
}) => {
  const [hoveredStatus, setHoveredStatus] = useState(null);

  const total = resolutionData.reduce((sum, item) => sum + (item.count || 0), 0);

  // SVG Donut Chart Parameters
  const size = 160;
  const strokeWidth = 22;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  // Calculate segment stroke-dasharrays
  let accumulatedAngle = 0;
  const segments = resolutionData.map((item) => {
    const count = item.count || 0;
    const ratio = total > 0 ? count / total : 0;
    const dashLength = ratio * circumference;
    const dashOffset = -accumulatedAngle;
    accumulatedAngle += dashLength;
    const config = STATUS_CONFIG[item.status] || {
      label: item.status,
      color: "#106BA3",
      bgColor: "rgba(16, 107, 163, 0.1)",
    };

    return {
      status: item.status,
      count,
      percentage: item.percentage || (total > 0 ? ((count / total) * 100).toFixed(1) : 0),
      dashLength,
      dashOffset,
      circumference,
      config,
    };
  });

  return (
    <div className="p-6 rounded-2xl bg-bg-paper border border-border-theme shadow-sm h-full flex flex-col">
      {/* Title */}
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-2">
          <PieChart className="w-5 h-5 text-primary" />
          <h3 className="font-bold text-base text-text-primary">
            Feedback Resolution Status
          </h3>
        </div>
        <span className="text-xs font-semibold text-text-secondary">
          {total} Total Issues
        </span>
      </div>

      {/* Donut & Stats Breakdown */}
      <div className="flex-1 flex items-center justify-around flex-wrap gap-6">
        {loading ? (
          <div className="flex items-center gap-6 w-full justify-center animate-pulse">
            <div className="w-36 h-36 rounded-full bg-slate-200 dark:bg-slate-700" />
            <div className="w-36 space-y-3">
              <div className="h-6 bg-slate-200 dark:bg-slate-700 rounded" />
              <div className="h-6 bg-slate-200 dark:bg-slate-700 rounded" />
              <div className="h-6 bg-slate-200 dark:bg-slate-700 rounded" />
            </div>
          </div>
        ) : total === 0 ? (
          <div className="text-center py-8 text-text-secondary text-sm">
            No feedback resolution data available.
          </div>
        ) : (
          <>
            {/* SVG Donut */}
            <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
              <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
                {/* Background Ring */}
                <circle
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="transparent"
                  stroke="currentColor"
                  className="text-slate-100 dark:text-slate-800"
                  strokeWidth={strokeWidth}
                />

                {/* Segments */}
                {segments.map((seg) => {
                  const isHovered = hoveredStatus === seg.status;
                  return (
                    <circle
                      key={seg.status}
                      cx={size / 2}
                      cy={size / 2}
                      r={radius}
                      fill="transparent"
                      stroke={seg.config.color}
                      strokeWidth={isHovered ? strokeWidth + 4 : strokeWidth}
                      strokeDasharray={`${seg.dashLength} ${seg.circumference - seg.dashLength}`}
                      strokeDashoffset={seg.dashOffset}
                      transform={`rotate(-90 ${size / 2} ${size / 2})`}
                      className="transition-all duration-300 cursor-pointer"
                      onMouseEnter={() => setHoveredStatus(seg.status)}
                      onMouseLeave={() => setHoveredStatus(null)}
                      onClick={() => {
                        if (seg.status === "pending" && onNavigateTab) onNavigateTab(1, "/feedback/pending");
                        if (seg.status === "approved" && onNavigateTab) onNavigateTab(2, "/feedback/approved");
                      }}
                    />
                  );
                })}
              </svg>

              {/* Center Stat */}
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-xl font-extrabold text-text-primary leading-none">
                  {hoveredStatus
                    ? segments.find((s) => s.status === hoveredStatus)?.count || total
                    : total}
                </span>
                <span className="text-xs font-semibold text-text-secondary mt-1">
                  {hoveredStatus
                    ? STATUS_CONFIG[hoveredStatus]?.label || "Issues"
                    : "Total"}
                </span>
              </div>
            </div>

            {/* Status Legend Buttons */}
            <div className="flex flex-col gap-2 min-w-[160px] flex-1">
              {segments.map((seg) => {
                const isClickable = seg.status === "pending" || seg.status === "approved";
                const isHovered = hoveredStatus === seg.status;

                return (
                  <button
                    type="button"
                    key={seg.status}
                    onClick={() => {
                      if (seg.status === "pending" && onNavigateTab) onNavigateTab(1, "/feedback/pending");
                      if (seg.status === "approved" && onNavigateTab) onNavigateTab(2, "/feedback/approved");
                    }}
                    onMouseEnter={() => setHoveredStatus(seg.status)}
                    onMouseLeave={() => setHoveredStatus(null)}
                    disabled={!isClickable}
                    className={`flex items-center justify-between p-2.5 rounded-xl border transition-all text-left ${
                      isClickable ? "cursor-pointer hover:shadow-xs" : "cursor-default"
                    } ${
                      isHovered
                        ? "border-current"
                        : "border-transparent hover:bg-slate-50 dark:hover:bg-slate-800/40"
                    }`}
                    style={{
                      backgroundColor: isHovered ? seg.config.bgColor : undefined,
                      borderColor: isHovered ? seg.config.color : undefined,
                    }}
                  >
                    <div className="flex items-center gap-2.5">
                      <span
                        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                        style={{ backgroundColor: seg.config.color }}
                      />
                      <div>
                        <div className="font-semibold text-xs text-text-primary">
                          {seg.config.label}
                        </div>
                        <div className="text-[11px] text-text-secondary">
                          {seg.config.actionText}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 ml-2">
                      <span className="font-bold text-xs text-text-primary">
                        {seg.count}
                      </span>
                      <span className="text-[11px] text-text-secondary min-w-[32px] text-right">
                        ({seg.percentage}%)
                      </span>
                      {isClickable && (
                        <ArrowRight
                          className="w-3.5 h-3.5 ml-0.5"
                          style={{ color: seg.config.color }}
                        />
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default React.memo(ResolutionStatusChart);
