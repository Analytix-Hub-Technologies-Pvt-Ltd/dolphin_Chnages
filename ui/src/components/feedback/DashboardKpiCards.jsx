import React from "react";
import {
  MessageSquare,
  ThumbsUp,
  ThumbsDown,
  Clock,
  CheckCircle2,
  XCircle,
} from "lucide-react";

const KpiCard = ({
  title,
  value,
  subtext,
  icon: Icon,
  iconColor,
  iconBg,
  borderHighlight = null,
  loading = false,
}) => {
  return (
    <div
      className={`p-4 rounded-2xl bg-bg-paper border transition-all flex flex-col justify-between min-h-[120px] shadow-xs hover:shadow-md hover:-translate-y-0.5 ${
        borderHighlight || "border-border-theme"
      }`}
    >
      <div className="flex items-start justify-between mb-2">
        <span className="text-[11px] font-bold uppercase tracking-wider text-text-secondary">
          {title}
        </span>
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
          style={{ backgroundColor: iconBg, color: iconColor }}
        >
          <Icon className="w-4 h-4" />
        </div>
      </div>

      <div>
        {loading ? (
          <div className="h-7 w-20 bg-slate-200 dark:bg-slate-700 rounded-lg animate-pulse mb-1" />
        ) : (
          <span className="text-2xl font-extrabold text-text-primary tracking-tight block leading-tight">
            {value}
          </span>
        )}

        {subtext && (
          <span className="text-[11px] text-text-secondary font-medium block mt-0.5">
            {subtext}
          </span>
        )}
      </div>
    </div>
  );
};

const DashboardKpiCards = ({ summary = {}, loading = false }) => {
  const total = summary.total_feedback || 0;
  const positive = summary.positive_feedback || 0;
  const negative = summary.negative_feedback || 0;
  const pending = summary.pending_issues || 0;
  const approved = summary.approved_issues || 0;
  const rejected = summary.rejected_issues || 0;

  const positivePct = total > 0 ? ((positive / total) * 100).toFixed(0) : "0";
  const negativePct = total > 0 ? ((negative / total) * 100).toFixed(0) : "0";

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3.5 mb-5 w-full">
      {/* 1. Total Feedback */}
      <KpiCard
        title="Total Feedback"
        value={total.toLocaleString()}
        subtext="Positive + Negative"
        icon={MessageSquare}
        iconColor="#106BA3"
        iconBg="rgba(16, 107, 163, 0.12)"
        loading={loading}
      />

      {/* 2. Positive Feedback */}
      <KpiCard
        title="Positive Feedback"
        value={positive.toLocaleString()}
        subtext={`${positivePct}% of total ratings`}
        icon={ThumbsUp}
        iconColor="#16a34a"
        iconBg="rgba(22, 163, 74, 0.12)"
        loading={loading}
      />

      {/* 3. Negative Feedback */}
      <KpiCard
        title="Negative Feedback"
        value={negative.toLocaleString()}
        subtext={`${negativePct}% reported issues`}
        icon={ThumbsDown}
        iconColor="#dc2626"
        iconBg="rgba(220, 38, 38, 0.12)"
        loading={loading}
      />

      {/* 4. Pending Issues */}
      <KpiCard
        title="Pending Issues"
        value={pending.toLocaleString()}
        subtext="Awaiting SME review"
        icon={Clock}
        iconColor="#d97706"
        iconBg="rgba(217, 119, 6, 0.12)"
        borderHighlight={pending > 0 ? "border-amber-500/50" : null}
        loading={loading}
      />

      {/* 5. Approved Issues */}
      <KpiCard
        title="Approved Issues"
        value={approved.toLocaleString()}
        subtext="In Memory & DPO"
        icon={CheckCircle2}
        iconColor="#16a34a"
        iconBg="rgba(22, 163, 74, 0.12)"
        loading={loading}
      />

      {/* 6. Rejected Issues */}
      <KpiCard
        title="Rejected Issues"
        value={rejected.toLocaleString()}
        subtext="Archived for audit"
        icon={XCircle}
        iconColor="#6b7280"
        iconBg="rgba(107, 114, 128, 0.12)"
        loading={loading}
      />
    </div>
  );
};

export default React.memo(DashboardKpiCards);
