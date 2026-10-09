import React from "react";
import { Clock, AlertTriangle } from "lucide-react";

const PendingAgingTable = ({
  agingData = [],
  loading = false,
  onAgingBucketClick,
}) => {
  const totalPending = agingData.reduce((sum, a) => sum + (a.count || 0), 0);

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
              backgroundColor: "rgba(217, 119, 6, 0.1)",
              color: "var(--fb-warning)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Clock style={{ width: 18, height: 18 }} />
          </div>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--fb-text-primary)", margin: 0 }}>
            Pending Issue — Aging
          </h3>
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--fb-text-secondary)" }}>
          {totalPending} total pending
        </span>
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflowX: "auto" }}>
        {loading ? (
          <div style={{ padding: "8px 0", display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ height: 36, backgroundColor: "var(--fb-border)", borderRadius: 8, width: "100%" }} />
            <div style={{ height: 36, backgroundColor: "var(--fb-border)", borderRadius: 8, width: "100%" }} />
            <div style={{ height: 36, backgroundColor: "var(--fb-border)", borderRadius: 8, width: "100%" }} />
          </div>
        ) : agingData.length === 0 || totalPending === 0 ? (
          <div style={{ textAlign: "center", padding: "32px 0", color: "var(--fb-text-secondary)", fontSize: 12 }}>
            No pending issues in queue. All clear! 🎉
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
                  }}
                >
                  Age Bracket
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
                  }}
                >
                  Issues Count
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
                    textAlign: "right",
                  }}
                >
                  Status Indicator
                </th>
              </tr>
            </thead>
            <tbody>
              {agingData.map((row) => {
                const isOldest = row.is_oldest || row.bucket === "> 3 days";
                const hasIssues = (row.count || 0) > 0;

                return (
                  <tr
                    key={row.bucket}
                    onClick={() => onAgingBucketClick && onAgingBucketClick(row.bucket)}
                    style={{
                      borderBottom: "1px solid var(--fb-border)",
                      cursor: "pointer",
                      backgroundColor: isOldest && hasIssues ? "rgba(245, 158, 11, 0.08)" : "transparent",
                      transition: "background-color 0.2s ease",
                    }}
                  >
                    <td style={{ padding: "10px 12px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        {isOldest && hasIssues && (
                          <AlertTriangle style={{ width: 14, height: 14, color: "var(--fb-warning)", flexShrink: 0 }} />
                        )}
                        <span
                          style={{
                            fontSize: 12,
                            fontWeight: isOldest ? 700 : 600,
                            color: isOldest && hasIssues ? "var(--fb-warning)" : "var(--fb-text-primary)",
                          }}
                        >
                          {row.bucket}
                        </span>
                      </div>
                    </td>

                    <td style={{ padding: "10px 12px", textAlign: "center" }}>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          padding: "2px 10px",
                          borderRadius: 9999,
                          fontSize: 12,
                          fontWeight: 700,
                          backgroundColor:
                            isOldest && hasIssues
                              ? "rgba(245, 158, 11, 0.2)"
                              : hasIssues
                              ? "rgba(16, 107, 163, 0.12)"
                              : "var(--fb-bg-default)",
                          color:
                            isOldest && hasIssues
                              ? "#b45309"
                              : hasIssues
                              ? "var(--fb-primary)"
                              : "var(--fb-text-secondary)",
                        }}
                      >
                        {row.count}
                      </span>
                    </td>

                    <td style={{ padding: "10px 12px", textAlign: "right" }}>
                      {isOldest && hasIssues ? (
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            padding: "2px 8px",
                            borderRadius: 9999,
                            fontSize: 11,
                            fontWeight: 600,
                            border: "1px solid #f59e0b",
                            color: "var(--fb-warning)",
                            backgroundColor: "rgba(245, 158, 11, 0.1)",
                          }}
                        >
                          Requires Attention
                        </span>
                      ) : hasIssues ? (
                        <span style={{ fontSize: 12, color: "var(--fb-text-secondary)", fontWeight: 500 }}>
                          Normal Queue
                        </span>
                      ) : (
                        <span style={{ fontSize: 12, color: "rgba(92, 112, 128, 0.5)" }}>
                          None
                        </span>
                      )}
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

export default React.memo(PendingAgingTable);
