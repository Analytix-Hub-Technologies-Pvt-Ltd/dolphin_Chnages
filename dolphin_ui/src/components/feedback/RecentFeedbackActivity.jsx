import React from "react";
import { History, ThumbsUp, ThumbsDown, Eye, ArrowRight } from "lucide-react";

const getFeedbackTypeChip = (type) => {
  switch (type) {
    case "positive":
      return (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            padding: "2px 8px",
            borderRadius: 9999,
            fontSize: 11,
            fontWeight: 600,
            backgroundColor: "rgba(22, 163, 74, 0.12)",
            color: "var(--fb-success)",
          }}
        >
          <ThumbsUp style={{ width: 12, height: 12 }} /> Positive
        </span>
      );
    case "incorrect_information":
      return (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "2px 8px",
            borderRadius: 9999,
            fontSize: 11,
            fontWeight: 600,
            border: "1px solid rgba(220, 38, 38, 0.3)",
            color: "var(--fb-danger)",
            backgroundColor: "rgba(220, 38, 38, 0.1)",
          }}
        >
          Incorrect Info
        </span>
      );
    case "does_not_match_procedure":
      return (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "2px 8px",
            borderRadius: 9999,
            fontSize: 11,
            fontWeight: 600,
            border: "1px solid rgba(217, 119, 6, 0.3)",
            color: "var(--fb-warning)",
            backgroundColor: "rgba(217, 119, 6, 0.1)",
          }}
        >
          Mismatch Procedure
        </span>
      );
    case "irrelevant_answer":
      return (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "2px 8px",
            borderRadius: 9999,
            fontSize: 11,
            fontWeight: 600,
            border: "1px solid rgba(107, 114, 128, 0.3)",
            color: "#6b7280",
            backgroundColor: "rgba(107, 114, 128, 0.1)",
          }}
        >
          Irrelevant
        </span>
      );
    case "incomplete_answer":
      return (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "2px 8px",
            borderRadius: 9999,
            fontSize: 11,
            fontWeight: 600,
            border: "1px solid rgba(2, 132, 199, 0.3)",
            color: "#0284c7",
            backgroundColor: "rgba(2, 132, 199, 0.1)",
          }}
        >
          Incomplete
        </span>
      );
    case "did_not_answer_question":
      return (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "2px 8px",
            borderRadius: 9999,
            fontSize: 11,
            fontWeight: 600,
            border: "1px solid rgba(147, 51, 234, 0.3)",
            color: "#9333ea",
            backgroundColor: "rgba(147, 51, 234, 0.1)",
          }}
        >
          Didn't Answer
        </span>
      );
    default:
      return (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "2px 8px",
            borderRadius: 9999,
            fontSize: 11,
            fontWeight: 600,
            border: "1px solid var(--fb-border)",
            color: "var(--fb-text-secondary)",
          }}
        >
          {type || "Feedback"}
        </span>
      );
  }
};

const getStatusBadge = (status, feedbackType) => {
  if (status === "positive" || feedbackType === "positive") {
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          padding: "2px 8px",
          borderRadius: 9999,
          fontSize: 11,
          fontWeight: 700,
          backgroundColor: "rgba(22, 163, 74, 0.12)",
          color: "var(--fb-success)",
        }}
      >
        Positive 👍
      </span>
    );
  }
  if (status === "approved") {
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          padding: "2px 8px",
          borderRadius: 9999,
          fontSize: 11,
          fontWeight: 700,
          backgroundColor: "rgba(22, 163, 74, 0.12)",
          color: "var(--fb-success)",
        }}
      >
        Approved
      </span>
    );
  }
  if (status === "rejected") {
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          padding: "2px 8px",
          borderRadius: 9999,
          fontSize: 11,
          fontWeight: 700,
          backgroundColor: "rgba(107, 114, 128, 0.12)",
          color: "#6b7280",
        }}
      >
        Rejected
      </span>
    );
  }
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 8px",
        borderRadius: 9999,
        fontSize: 11,
        fontWeight: 700,
        backgroundColor: "rgba(217, 119, 6, 0.12)",
        color: "var(--fb-warning)",
      }}
    >
      Pending
    </span>
  );
};

const formatDate = (isoStr) => {
  if (!isoStr) return "-";
  try {
    const d = new Date(isoStr);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (e) {
    return isoStr;
  }
};

const RecentFeedbackActivity = ({
  recentItems = [],
  loading = false,
  onSelectItem,
  onViewAllPending,
}) => {
  const safeRecent = Array.isArray(recentItems) ? recentItems : [];

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
      {/* Title & View All Link */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 16,
          flexWrap: "wrap",
          gap: 10,
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
            <History style={{ width: 18, height: 18 }} />
          </div>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--fb-text-primary)", margin: 0 }}>
            Recent Feedback Activity
          </h3>
        </div>

        <button
          type="button"
          onClick={onViewAllPending}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 12,
            fontWeight: 600,
            color: "var(--fb-primary)",
            background: "transparent",
            border: "none",
            cursor: "pointer",
            padding: "4px 8px",
          }}
        >
          <span>View all pending feedback</span>
          <ArrowRight style={{ width: 14, height: 14 }} />
        </button>
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflowX: "auto" }}>
        {loading ? (
          <div style={{ padding: "8px 0", display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ height: 40, backgroundColor: "var(--fb-border)", borderRadius: 8, width: "100%" }} />
            <div style={{ height: 40, backgroundColor: "var(--fb-border)", borderRadius: 8, width: "100%" }} />
            <div style={{ height: 40, backgroundColor: "var(--fb-border)", borderRadius: 8, width: "100%" }} />
          </div>
        ) : safeRecent.length === 0 ? (
          <div style={{ textAlign: "center", padding: "32px 0", color: "var(--fb-text-secondary)", fontSize: 12 }}>
            No recent feedback recorded.
          </div>
        ) : (
          <table
            className="fb-table"
            style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 13 }}
          >
            <thead>
              <tr style={{ borderBottom: "1px solid var(--fb-border)" }}>
                <th
                  style={{
                    padding: "10px 12px",
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    color: "var(--fb-text-secondary)",
                    backgroundColor: "var(--fb-bg-default)",
                    width: 48,
                  }}
                >
                  Rating
                </th>
                <th
                  style={{
                    padding: "10px 12px",
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    color: "var(--fb-text-secondary)",
                    backgroundColor: "var(--fb-bg-default)",
                    minWidth: 220,
                  }}
                >
                  Question
                </th>
                <th
                  style={{
                    padding: "10px 12px",
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    color: "var(--fb-text-secondary)",
                    backgroundColor: "var(--fb-bg-default)",
                    width: 140,
                  }}
                >
                  Feedback Type
                </th>
                <th
                  style={{
                    padding: "10px 12px",
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    color: "var(--fb-text-secondary)",
                    backgroundColor: "var(--fb-bg-default)",
                    width: 110,
                  }}
                >
                  Company
                </th>
                <th
                  style={{
                    padding: "10px 12px",
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    color: "var(--fb-text-secondary)",
                    backgroundColor: "var(--fb-bg-default)",
                    width: 100,
                  }}
                >
                  Status
                </th>
                <th
                  style={{
                    padding: "10px 12px",
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    color: "var(--fb-text-secondary)",
                    backgroundColor: "var(--fb-bg-default)",
                    width: 120,
                  }}
                >
                  Created Date
                </th>
                <th
                  style={{
                    padding: "10px 12px",
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    color: "var(--fb-text-secondary)",
                    backgroundColor: "var(--fb-bg-default)",
                    textAlign: "center",
                    width: 80,
                  }}
                >
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {safeRecent.map((item) => {
                const isPos = item.feedback_type === "positive" || item.status === "positive";

                return (
                  <tr
                    key={item.feedback_id}
                    onClick={() => onSelectItem && onSelectItem(item.feedback_id, item.status)}
                    style={{
                      borderBottom: "1px solid var(--fb-border)",
                      cursor: "pointer",
                      transition: "background-color 0.2s ease",
                    }}
                  >
                    <td style={{ padding: "10px 12px" }}>
                      {isPos ? (
                        <span title="Helpful 👍">
                          <ThumbsUp style={{ width: 16, height: 16, color: "var(--fb-success)" }} />
                        </span>
                      ) : (
                        <span title="Reported Issue 👎">
                          <ThumbsDown style={{ width: 16, height: 16, color: "var(--fb-danger)" }} />
                        </span>
                      )}
                    </td>

                    <td style={{ padding: "10px 12px" }}>
                      <div
                        style={{
                          fontSize: 12,
                          fontWeight: 600,
                          color: "var(--fb-text-primary)",
                          maxWidth: 380,
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {item.question}
                      </div>
                    </td>

                    <td style={{ padding: "10px 12px" }}>{getFeedbackTypeChip(item.feedback_type)}</td>

                    <td style={{ padding: "10px 12px" }}>
                      <span style={{ fontSize: 12, color: "var(--fb-text-secondary)", fontWeight: 500 }}>
                        {item.company_id || "Global"}
                      </span>
                    </td>

                    <td style={{ padding: "10px 12px" }}>{getStatusBadge(item.status, item.feedback_type)}</td>

                    <td style={{ padding: "10px 12px" }}>
                      <span style={{ fontSize: 12, color: "var(--fb-text-secondary)" }}>
                        {formatDate(item.created_at)}
                      </span>
                    </td>

                    <td style={{ padding: "10px 12px", textAlign: "center" }}>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (onSelectItem) onSelectItem(item.feedback_id, item.status);
                        }}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          padding: "4px 10px",
                          borderRadius: 8,
                          backgroundColor: "var(--fb-primary)",
                          color: "#ffffff",
                          fontSize: 11,
                          fontWeight: 600,
                          border: "none",
                          cursor: "pointer",
                          boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
                        }}
                      >
                        <Eye style={{ width: 12, height: 12 }} />
                        <span>Review</span>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default React.memo(RecentFeedbackActivity);
