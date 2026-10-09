import React from "react";
import { Ship } from "lucide-react";

const formatSatisfactionRate = (rate) => {
  if (rate === null || rate === undefined || isNaN(rate) || !isFinite(rate)) {
    return "N/A";
  }
  return `${Number(rate).toFixed(1)}%`;
};

const ShipTypeAnalyticsTable = ({
  shipTypeData = [],
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
            <Ship style={{ width: 18, height: 18 }} />
          </div>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--fb-text-primary)", margin: 0 }}>
            Feedback by Ship Type
          </h3>
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--fb-text-secondary)" }}>
          {shipTypeData.length} ship types
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
        ) : shipTypeData.length === 0 ? (
          <div style={{ textAlign: "center", padding: "32px 0", color: "var(--fb-text-secondary)", fontSize: 12 }}>
            Ship type analytics are not available for the current data.
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
                  Ship Type
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
                  Total
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
                  Positive 👍
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
                  Negative 👎
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
                  Pending
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
                    textAlign: "right",
                    minWidth: 140,
                  }}
                >
                  Satisfaction Rate
                </th>
              </tr>
            </thead>
            <tbody>
              {shipTypeData.map((row) => {
                const satRate = row.satisfaction_rate;
                const hasRate = satRate !== null && satRate !== undefined && !isNaN(satRate);

                return (
                  <tr
                    key={row.ship_type}
                    style={{ borderBottom: "1px solid var(--fb-border)" }}
                  >
                    <td style={{ padding: "10px 12px", fontWeight: 600, color: "var(--fb-text-primary)", fontSize: 12 }}>
                      {row.ship_type}
                    </td>
                    <td style={{ padding: "10px 12px", textAlign: "center", fontWeight: 700, color: "var(--fb-text-primary)", fontSize: 12 }}>
                      {row.total}
                    </td>
                    <td style={{ padding: "10px 12px", textAlign: "center", fontWeight: 600, color: "var(--fb-success)", fontSize: 12 }}>
                      {row.positive}
                    </td>
                    <td style={{ padding: "10px 12px", textAlign: "center", fontWeight: 600, color: "var(--fb-danger)", fontSize: 12 }}>
                      {row.negative}
                    </td>
                    <td style={{ padding: "10px 12px", textAlign: "center", fontWeight: 600, color: "var(--fb-warning)", fontSize: 12 }}>
                      {row.pending}
                    </td>
                    <td style={{ padding: "10px 12px", textAlign: "center", fontWeight: 600, color: "var(--fb-success)", fontSize: 12 }}>
                      {row.approved}
                    </td>
                    <td style={{ padding: "10px 12px", textAlign: "right" }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 8 }}>
                        <div style={{ width: 64, height: 6, borderRadius: 9999, backgroundColor: "var(--fb-border)", overflow: "hidden" }}>
                          {hasRate && (
                            <div
                              style={{
                                height: "100%",
                                borderRadius: 9999,
                                width: `${Math.min(100, Math.max(0, satRate))}%`,
                                backgroundColor: satRate >= 70 ? "var(--fb-success)" : satRate >= 50 ? "#f59e0b" : "var(--fb-danger)",
                              }}
                            />
                          )}
                        </div>
                        <span style={{ fontSize: 12, fontWeight: 700, color: "var(--fb-text-primary)", minWidth: 42, textAlign: "right" }}>
                          {formatSatisfactionRate(satRate)}
                        </span>
                      </div>
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

export default React.memo(ShipTypeAnalyticsTable);
