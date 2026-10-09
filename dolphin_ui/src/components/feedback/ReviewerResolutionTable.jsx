import React from "react";
import { Users } from "lucide-react";

const ReviewerResolutionTable = ({
  reviewerData = [],
  loading = false,
}) => {
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
            <Users style={{ width: 18, height: 18 }} />
          </div>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--fb-text-primary)", margin: 0 }}>
            Total Issues Resolved by SMEs
          </h3>
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--fb-text-secondary)" }}>
          {reviewerData.length} active reviewers
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
        ) : reviewerData.length === 0 ? (
          <div style={{ textAlign: "center", padding: "32px 0", color: "var(--fb-text-secondary)", fontSize: 12 }}>
            No reviewer resolution records found for this period.
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
                  Reviewer
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
                  Approved
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
                  Rejected
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
                  Total Resolved
                </th>
              </tr>
            </thead>
            <tbody>
              {reviewerData.map((row, idx) => (
                <tr
                  key={row.reviewer || idx}
                  style={{ borderBottom: "1px solid var(--fb-border)" }}
                >
                  <td style={{ padding: "10px 12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div
                        style={{
                          width: 28,
                          height: 28,
                          borderRadius: "50%",
                          backgroundColor: "var(--fb-primary)",
                          color: "#ffffff",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 12,
                          fontWeight: 700,
                          flexShrink: 0,
                        }}
                      >
                        {row.reviewer ? row.reviewer.charAt(0).toUpperCase() : "U"}
                      </div>
                      <span style={{ fontSize: 12, fontWeight: 600, color: "var(--fb-text-primary)" }}>
                        {row.reviewer || "Unknown Reviewer"}
                      </span>
                    </div>
                  </td>
                  <td style={{ padding: "10px 12px", textAlign: "center" }}>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        padding: "2px 8px",
                        borderRadius: 9999,
                        fontSize: 12,
                        fontWeight: 700,
                        backgroundColor: "rgba(22, 163, 74, 0.12)",
                        color: "var(--fb-success)",
                      }}
                    >
                      {row.approved}
                    </span>
                  </td>
                  <td style={{ padding: "10px 12px", textAlign: "center" }}>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        padding: "2px 8px",
                        borderRadius: 9999,
                        fontSize: 12,
                        fontWeight: 700,
                        backgroundColor: "rgba(107, 114, 128, 0.12)",
                        color: "#6b7280",
                      }}
                    >
                      {row.rejected}
                    </span>
                  </td>
                  <td
                    style={{
                      padding: "10px 12px",
                      textAlign: "right",
                      fontWeight: 800,
                      color: "var(--fb-primary)",
                      fontSize: 13,
                    }}
                  >
                    {row.total_resolved}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default React.memo(ReviewerResolutionTable);
