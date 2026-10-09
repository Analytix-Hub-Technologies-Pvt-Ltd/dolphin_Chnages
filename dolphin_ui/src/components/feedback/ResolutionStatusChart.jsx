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
      color: "var(--fb-primary)",
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
    <div
      className="fb-card"
      style={{
        padding: 20,
        borderRadius: 16,
        backgroundColor: "var(--fb-bg-paper)",
        border: "1px solid var(--fb-border)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        boxSizing: "border-box",
      }}
    >
      {/* Title */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 16,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 10,
              backgroundColor: "rgba(16, 107, 163, 0.1)",
              color: "var(--fb-primary)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <PieChart style={{ width: 18, height: 18 }} />
          </div>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--fb-text-primary)", margin: 0 }}>
            Feedback Resolution Status
          </h3>
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--fb-text-secondary)" }}>
          {total} Total Issues
        </span>
      </div>

      {/* Donut & Stats Breakdown */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-around",
          flexWrap: "wrap",
          gap: 20,
          flex: 1,
        }}
      >
        {loading ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 20,
              width: "100%",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                width: 140,
                height: 140,
                borderRadius: "50%",
                backgroundColor: "var(--fb-border)",
              }}
            />
            <div style={{ width: 140, display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ height: 28, backgroundColor: "var(--fb-border)", borderRadius: 8 }} />
              <div style={{ height: 28, backgroundColor: "var(--fb-border)", borderRadius: 8 }} />
              <div style={{ height: 28, backgroundColor: "var(--fb-border)", borderRadius: 8 }} />
            </div>
          </div>
        ) : total === 0 ? (
          <div style={{ textAlign: "center", padding: "32px 0", color: "var(--fb-text-secondary)", fontSize: 12 }}>
            No feedback resolution data available.
          </div>
        ) : (
          <>
            {/* SVG Donut */}
            <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
              <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
                {/* Background Ring */}
                <circle
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="transparent"
                  stroke="var(--fb-bg-default)"
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
                      strokeWidth={isHovered ? strokeWidth + 3 : strokeWidth}
                      strokeDasharray={`${seg.dashLength} ${seg.circumference - seg.dashLength}`}
                      strokeDashoffset={seg.dashOffset}
                      transform={`rotate(-90 ${size / 2} ${size / 2})`}
                      style={{ transition: "all 0.3s ease", cursor: "pointer" }}
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
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  pointerEvents: "none",
                }}
              >
                <span style={{ fontSize: 22, fontWeight: 800, color: "var(--fb-text-primary)", lineHeight: 1 }}>
                  {hoveredStatus
                    ? segments.find((s) => s.status === hoveredStatus)?.count || total
                    : total}
                </span>
                <span style={{ fontSize: 11, fontWeight: 600, color: "var(--fb-text-secondary)", marginTop: 4 }}>
                  {hoveredStatus
                    ? STATUS_CONFIG[hoveredStatus]?.label || "Issues"
                    : "Total"}
                </span>
              </div>
            </div>

            {/* Status Legend Buttons */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 8,
                minWidth: 170,
                flex: 1,
              }}
            >
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
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "8px 12px",
                      borderRadius: 12,
                      border: isHovered ? `1px solid ${seg.config.color}` : "1px solid var(--fb-border)",
                      backgroundColor: isHovered ? seg.config.bgColor : "var(--fb-bg-default)",
                      cursor: isClickable ? "pointer" : "default",
                      width: "100%",
                      boxSizing: "border-box",
                      textAlign: "left",
                      transition: "all 0.2s ease",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span
                        style={{
                          width: 10,
                          height: 10,
                          borderRadius: "50%",
                          backgroundColor: seg.config.color,
                          flexShrink: 0,
                        }}
                      />
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--fb-text-primary)" }}>
                          {seg.config.label}
                        </div>
                        <div style={{ fontSize: 10, color: "var(--fb-text-secondary)" }}>
                          {seg.config.actionText}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginLeft: 8 }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: "var(--fb-text-primary)" }}>
                        {seg.count}
                      </span>
                      <span style={{ fontSize: 11, color: "var(--fb-text-secondary)", minWidth: 36, textAlign: "right" }}>
                        ({seg.percentage}%)
                      </span>
                      {isClickable && (
                        <ArrowRight
                          style={{ width: 14, height: 14, color: seg.config.color, marginLeft: 2 }}
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
