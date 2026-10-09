import React, { useState } from "react";
import { TrendingUp, RefreshCw } from "lucide-react";

const FeedbackTrendChart = ({
  trendData = [],
  loading = false,
  error = null,
  onRetry,
  dateRangeLabel = "Last 30 Days",
}) => {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  const hasData =
    Array.isArray(trendData) &&
    trendData.length > 0 &&
    trendData.some((d) => (d.total || 0) > 0);

  // SVG Chart Calculations
  const width = 860;
  const height = 240;
  const padding = { top: 25, right: 30, bottom: 40, left: 45 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const maxVal = Math.max(
    ...trendData.map((d) => Math.max(d.total || 0, d.positive || 0, d.negative || 0)),
    5
  );

  const getY = (val) => {
    return padding.top + chartHeight - (val / maxVal) * chartHeight;
  };

  const getX = (idx) => {
    if (trendData.length <= 1) return padding.left + chartWidth / 2;
    return padding.left + (idx / (trendData.length - 1)) * chartWidth;
  };

  const createPath = (key) => {
    if (!trendData.length) return "";
    return trendData
      .map((d, i) => `${i === 0 ? "M" : "L"} ${getX(i)} ${getY(d[key] || 0)}`)
      .join(" ");
  };

  const createAreaPath = () => {
    if (!trendData.length) return "";
    const linePart = createPath("total");
    const lastX = getX(trendData.length - 1);
    const firstX = getX(0);
    const bottomY = padding.top + chartHeight;
    return `${linePart} L ${lastX} ${bottomY} L ${firstX} ${bottomY} Z`;
  };

  const yTicks = [0, Math.round(maxVal / 2), maxVal];

  const getXAxisLabels = () => {
    if (!trendData.length) return [];
    if (trendData.length <= 7) {
      return trendData.map((d, idx) => ({ idx, text: d.date }));
    }
    const step = Math.ceil(trendData.length / 6);
    const labels = [];
    for (let i = 0; i < trendData.length; i += step) {
      labels.push({ idx: i, text: trendData[i].date });
    }
    if (labels[labels.length - 1]?.idx !== trendData.length - 1) {
      labels.push({
        idx: trendData.length - 1,
        text: trendData[trendData.length - 1].date,
      });
    }
    return labels;
  };

  return (
    <div
      className="fb-card"
      style={{
        padding: 20,
        borderRadius: 16,
        backgroundColor: "var(--fb-bg-paper)",
        border: "1px solid var(--fb-border)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
        marginBottom: 20,
        boxSizing: "border-box",
        width: "100%",
      }}
    >
      {/* Header & Legend */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 12,
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
            <TrendingUp style={{ width: 18, height: 18 }} />
          </div>
          <div>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--fb-text-primary)", margin: 0 }}>
              Feedback Volume & Sentiment Trend
            </h3>
            <span style={{ fontSize: 11, color: "var(--fb-text-secondary)", display: "block", marginTop: 2 }}>
              Daily trend: Total ratings vs Positive vs Negative ({dateRangeLabel})
            </span>
          </div>
        </div>

        {/* Legend */}
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                backgroundColor: "var(--fb-primary)",
                display: "inline-block",
              }}
            />
            <span style={{ color: "var(--fb-text-secondary)", fontSize: 12, fontWeight: 600 }}>Total</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                backgroundColor: "var(--fb-success)",
                display: "inline-block",
              }}
            />
            <span style={{ color: "var(--fb-text-secondary)", fontSize: 12, fontWeight: 600 }}>Positive</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                backgroundColor: "var(--fb-danger)",
                display: "inline-block",
              }}
            />
            <span style={{ color: "var(--fb-text-secondary)", fontSize: 12, fontWeight: 600 }}>Negative</span>
          </div>
        </div>
      </div>

      {/* Chart Canvas */}
      <div
        style={{
          position: "relative",
          width: "100%",
          minHeight: 220,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflowX: "auto",
        }}
      >
        {loading ? (
          <div
            style={{
              width: "100%",
              height: 180,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--fb-text-secondary)",
              fontSize: 12,
            }}
          >
            <span>Loading trend metrics...</span>
          </div>
        ) : error ? (
          <div
            style={{
              textAlign: "center",
              padding: "24px 0",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 8,
              color: "var(--fb-danger)",
              fontSize: 12,
            }}
          >
            <span>{error}</span>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "4px 12px",
                  borderRadius: 8,
                  border: "1px solid rgba(220, 38, 38, 0.3)",
                  color: "var(--fb-danger)",
                  backgroundColor: "transparent",
                  cursor: "pointer",
                }}
              >
                <RefreshCw style={{ width: 12, height: 12 }} />
                <span>Retry</span>
              </button>
            )}
          </div>
        ) : !hasData ? (
          <div style={{ textAlign: "center", padding: "32px 0", color: "var(--fb-text-secondary)", fontSize: 12 }}>
            No feedback trend data available for this period.
          </div>
        ) : (
          <div style={{ width: "100%", height: "100%", position: "relative" }}>
            <svg
              viewBox={`0 0 ${width} ${height}`}
              style={{ width: "100%", height: "auto", minWidth: 480, overflow: "visible" }}
            >
              <defs>
                <linearGradient id="totalTrendGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--fb-primary)" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="var(--fb-primary)" stopOpacity="0.01" />
                </linearGradient>
              </defs>

              {/* Grid Lines */}
              {yTicks.map((tickVal, i) => {
                const y = getY(tickVal);
                return (
                  <g key={`grid-${i}`}>
                    <line
                      x1={padding.left}
                      y1={y}
                      x2={padding.left + chartWidth}
                      y2={y}
                      stroke="rgba(0,0,0,0.06)"
                      strokeDasharray="4 4"
                    />
                    <text
                      x={padding.left - 8}
                      y={y + 4}
                      textAnchor="end"
                      fontSize="11"
                      fill="var(--fb-text-secondary)"
                      style={{ userSelect: "none" }}
                    >
                      {tickVal}
                    </text>
                  </g>
                );
              })}

              {/* Area fill for Total */}
              <path d={createAreaPath()} fill="url(#totalTrendGradient)" />

              {/* Total Line (Blue) */}
              <path
                d={createPath("total")}
                fill="none"
                stroke="var(--fb-primary)"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {/* Positive Line (Green) */}
              <path
                d={createPath("positive")}
                fill="none"
                stroke="var(--fb-success)"
                strokeWidth="2"
                strokeDasharray="3 3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {/* Negative Line (Red) */}
              <path
                d={createPath("negative")}
                fill="none"
                stroke="var(--fb-danger)"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {/* Data points */}
              {trendData.map((d, idx) => {
                const cx = getX(idx);
                const cyTotal = getY(d.total || 0);
                const cyPos = getY(d.positive || 0);
                const cyNeg = getY(d.negative || 0);
                const isHovered = hoveredIndex === idx;

                return (
                  <g
                    key={`point-${idx}`}
                    onMouseEnter={() => setHoveredIndex(idx)}
                    onMouseLeave={() => setHoveredIndex(null)}
                    style={{ cursor: "pointer" }}
                  >
                    {isHovered && (
                      <line
                        x1={cx}
                        y1={padding.top}
                        x2={cx}
                        y2={padding.top + chartHeight}
                        stroke="var(--fb-primary)"
                        strokeWidth="1.5"
                        strokeDasharray="3 3"
                        opacity="0.6"
                      />
                    )}

                    <circle
                      cx={cx}
                      cy={cyTotal}
                      r={isHovered ? 5.5 : 3.5}
                      fill="var(--fb-primary)"
                      stroke="#ffffff"
                      strokeWidth="1.5"
                    />
                    <circle cx={cx} cy={cyPos} r={isHovered ? 4.5 : 2.5} fill="var(--fb-success)" />
                    <circle cx={cx} cy={cyNeg} r={isHovered ? 4.5 : 2.5} fill="var(--fb-danger)" />

                    <rect
                      x={cx - chartWidth / (trendData.length * 2 || 1)}
                      y={padding.top}
                      width={chartWidth / (trendData.length || 1)}
                      height={chartHeight}
                      fill="transparent"
                    />
                  </g>
                );
              })}

              {/* X Axis Labels */}
              {getXAxisLabels().map((label, i) => {
                const x = getX(label.idx);
                return (
                  <text
                    key={`x-label-${i}`}
                    x={x}
                    y={padding.top + chartHeight + 20}
                    textAnchor="middle"
                    fontSize="11"
                    fill="var(--fb-text-secondary)"
                    style={{ userSelect: "none" }}
                  >
                    {label.text ? label.text.slice(5) : ""}
                  </text>
                );
              })}
            </svg>

            {/* Hover Tooltip Card */}
            {hoveredIndex !== null && trendData[hoveredIndex] && (
              <div
                style={{
                  position: "absolute",
                  top: 8,
                  right: 16,
                  padding: "10px 14px",
                  borderRadius: 12,
                  backgroundColor: "var(--fb-bg-paper)",
                  border: "1px solid var(--fb-border)",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                  zIndex: 10,
                  minWidth: 130,
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  fontSize: 12,
                  pointerEvents: "none",
                }}
              >
                <span style={{ fontWeight: 700, color: "var(--fb-text-secondary)", fontSize: 11 }}>
                  {trendData[hoveredIndex].date}
                </span>
                <div style={{ display: "flex", justifyContent: "space-between", color: "var(--fb-primary)", fontWeight: 700 }}>
                  <span>Total:</span>
                  <span>{trendData[hoveredIndex].total || 0}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", color: "var(--fb-success)", fontWeight: 600 }}>
                  <span>Positive:</span>
                  <span>{trendData[hoveredIndex].positive || 0}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", color: "var(--fb-danger)", fontWeight: 600 }}>
                  <span>Negative:</span>
                  <span>{trendData[hoveredIndex].negative || 0}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default React.memo(FeedbackTrendChart);
