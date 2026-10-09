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
      className="fb-kpi-card"
      style={{
        padding: "16px 20px",
        borderRadius: 16,
        backgroundColor: "var(--fb-bg-paper)",
        border: borderHighlight ? "1.5px solid #f59e0b" : "1px solid var(--fb-border)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        minHeight: 125,
        boxSizing: "border-box",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 6 }}>
        <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--fb-text-secondary)" }}>
          {title}
        </span>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: "50%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            backgroundColor: iconBg,
            color: iconColor,
          }}
        >
          <Icon style={{ width: 16, height: 16 }} />
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", marginTop: "auto" }}>
        {loading ? (
          <div style={{ height: 28, width: 80, backgroundColor: "var(--fb-border)", borderRadius: 8, marginBottom: 4 }} />
        ) : (
          <span style={{ fontSize: 26, fontWeight: 800, color: "var(--fb-text-primary)", lineHeight: 1.1, margin: "2px 0", display: "block" }}>
            {value}
          </span>
        )}

        {subtext && (
          <span style={{ fontSize: 11, color: "var(--fb-text-secondary)", fontWeight: 500, display: "block", marginTop: 2 }}>
            {subtext}
          </span>
        )}
      </div>
    </div>
  );
};

const DashboardKpiCards = ({ summary = {}, loading = false }) => {
  const total = summary.total_feedback ?? summary.total_count ?? 0;
  const positive = summary.positive_feedback ?? summary.positive_count ?? 0;
  const negative = summary.negative_feedback ?? summary.negative_count ?? 0;
  const pending = summary.pending_issues ?? summary.pending_count ?? 0;
  const approved = summary.approved_issues ?? summary.approved_count ?? 0;
  const rejected = summary.rejected_issues ?? summary.rejected_count ?? 0;

  const positivePct = total > 0 ? ((positive / total) * 100).toFixed(0) : "0";
  const negativePct = total > 0 ? ((negative / total) * 100).toFixed(0) : "0";

  return (
    <div
      className="fb-kpi-grid"
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
        gap: "16px",
        marginBottom: "24px",
        width: "100%",
        boxSizing: "border-box",
      }}
    >
      {/* 1. Total Feedback */}
      <KpiCard
        title="Total Feedback"
        value={total.toLocaleString()}
        subtext="Positive + Negative"
        icon={MessageSquare}
        iconColor="var(--fb-primary)"
        iconBg="rgba(16, 107, 163, 0.12)"
        loading={loading}
      />

      {/* 2. Positive Feedback */}
      <KpiCard
        title="Positive Feedback"
        value={positive.toLocaleString()}
        subtext={`${positivePct}% of total ratings`}
        icon={ThumbsUp}
        iconColor="var(--fb-success)"
        iconBg="rgba(22, 163, 74, 0.12)"
        loading={loading}
      />

      {/* 3. Negative Feedback */}
      <KpiCard
        title="Negative Feedback"
        value={negative.toLocaleString()}
        subtext={`${negativePct}% reported issues`}
        icon={ThumbsDown}
        iconColor="var(--fb-danger)"
        iconBg="rgba(220, 38, 38, 0.12)"
        loading={loading}
      />

      {/* 4. Pending Issues */}
      <KpiCard
        title="Pending Issues"
        value={pending.toLocaleString()}
        subtext="Awaiting SME review"
        icon={Clock}
        iconColor="var(--fb-warning)"
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
        iconColor="var(--fb-success)"
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
