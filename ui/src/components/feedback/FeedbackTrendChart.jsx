import React, { useState } from "react";
import { TrendingUp, RefreshCw } from "lucide-react";
import { useThemeMode } from "../../context/ThemeModeContext";

const FeedbackTrendChart = ({
  trendData = [],
  loading = false,
  error = null,
  onRetry,
  dateRangeLabel = "Last 30 Days",
}) => {
  const { mode } = useThemeMode();
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
    <div className="bg-bg-paper border border-border-theme rounded-2xl p-4 sm:p-5 shadow-xs flex flex-col mb-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <TrendingUp className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm sm:text-base font-bold text-text-primary m-0">
              Feedback Volume & Sentiment Trend
            </h3>
            <span className="text-[11px] text-text-secondary">
              Daily trend: Total ratings vs Positive vs Negative ({dateRangeLabel})
            </span>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-3 text-xs font-semibold">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-primary" />
            <span className="text-text-secondary text-[11px]">Total</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-green-600" />
            <span className="text-text-secondary text-[11px]">Positive</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-red-600" />
            <span className="text-text-secondary text-[11px]">Negative</span>
          </div>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="relative w-full min-h-[220px] flex items-center justify-center overflow-x-auto">
        {loading ? (
          <div className="w-full h-48 flex items-center justify-center gap-2 text-text-secondary text-xs animate-pulse">
            <span>Loading trend metrics...</span>
          </div>
        ) : error ? (
          <div className="text-center py-6 flex flex-col items-center gap-2 text-red-500 text-xs">
            <span>{error}</span>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="flex items-center gap-1 px-3 py-1 rounded-lg border border-red-500/30 text-red-500 hover:bg-red-500/10 cursor-pointer"
              >
                <RefreshCw className="w-3 h-3" />
                <span>Retry</span>
              </button>
            )}
          </div>
        ) : !hasData ? (
          <div className="text-center py-8 text-text-secondary text-xs">
            No feedback trend data available for this period.
          </div>
        ) : (
          <div className="w-full h-full relative">
            <svg
              viewBox={`0 0 ${width} ${height}`}
              className="w-full h-auto min-w-[480px] overflow-visible"
            >
              <defs>
                <linearGradient id="totalTrendGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#106BA3" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#106BA3" stopOpacity="0.01" />
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
                      stroke={mode === "dark" ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)"}
                      strokeDasharray="4 4"
                    />
                    <text
                      x={padding.left - 8}
                      y={y + 4}
                      textAnchor="end"
                      fontSize="11"
                      className="fill-text-secondary select-none"
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
                stroke="#106BA3"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {/* Positive Line (Green) */}
              <path
                d={createPath("positive")}
                fill="none"
                stroke="#16a34a"
                strokeWidth="2"
                strokeDasharray="3 3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {/* Negative Line (Red) */}
              <path
                d={createPath("negative")}
                fill="none"
                stroke="#dc2626"
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
                    className="cursor-pointer"
                  >
                    {isHovered && (
                      <line
                        x1={cx}
                        y1={padding.top}
                        x2={cx}
                        y2={padding.top + chartHeight}
                        stroke="#106BA3"
                        strokeWidth="1.5"
                        strokeDasharray="3 3"
                        opacity="0.6"
                      />
                    )}

                    <circle
                      cx={cx}
                      cy={cyTotal}
                      r={isHovered ? 5.5 : 3.5}
                      fill="#106BA3"
                      stroke="#ffffff"
                      strokeWidth="1.5"
                    />
                    <circle cx={cx} cy={cyPos} r={isHovered ? 4.5 : 2.5} fill="#16a34a" />
                    <circle cx={cx} cy={cyNeg} r={isHovered ? 4.5 : 2.5} fill="#dc2626" />

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
                    className="fill-text-secondary select-none"
                  >
                    {label.text ? label.text.slice(5) : ""}
                  </text>
                );
              })}
            </svg>

            {/* Hover Tooltip Card */}
            {hoveredIndex !== null && trendData[hoveredIndex] && (
              <div className="absolute top-2 right-4 p-2.5 rounded-xl bg-bg-paper border border-border-theme shadow-lg z-10 min-w-[130px] flex flex-col gap-1 text-xs animate-fade-in pointer-events-none">
                <span className="font-bold text-text-secondary text-[11px]">
                  {trendData[hoveredIndex].date}
                </span>
                <div className="flex justify-between text-primary font-bold">
                  <span>Total:</span>
                  <span>{trendData[hoveredIndex].total || 0}</span>
                </div>
                <div className="flex justify-between text-green-600 font-semibold">
                  <span>Positive:</span>
                  <span>{trendData[hoveredIndex].positive || 0}</span>
                </div>
                <div className="flex justify-between text-red-600 font-semibold">
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
