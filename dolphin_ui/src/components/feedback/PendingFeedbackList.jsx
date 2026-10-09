import React from "react";
import { Search, Eye, RefreshCw, Inbox, ChevronLeft, ChevronRight } from "lucide-react";

const getFeedbackTypeChip = (type) => {
  switch (type) {
    case "positive":
      return (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "2px 8px",
            borderRadius: 9999,
            fontSize: 11,
            fontWeight: 600,
            backgroundColor: "rgba(22, 163, 74, 0.12)",
            color: "var(--fb-success)",
          }}
        >
          Positive 👍
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
          Mismatch SMS/Procedure
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

const PendingFeedbackList = ({
  items = [],
  loading = false,
  onSelectItem,
  onRefresh,
  searchTerm = "",
  onSearchChange,
  page = 0,
  rowsPerPage = 10,
  onPageChange,
  onRowsPerPageChange,
  totalCount,
}) => {
  const itemList = Array.isArray(items)
    ? items
    : items && Array.isArray(items.items)
    ? items.items
    : [];
  const count =
    totalCount !== undefined
      ? totalCount
      : typeof items?.total === "number"
      ? items.total
      : itemList.length;
  const totalPages = Math.ceil(count / rowsPerPage) || 1;

  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Search & Actions Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div style={{ position: "relative", width: 340, maxWidth: "100%" }}>
          <Search
            style={{
              width: 16,
              height: 16,
              position: "absolute",
              left: 12,
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--fb-text-secondary)",
            }}
          />
          <input
            type="text"
            placeholder="Search question, feedback ID, comments..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            style={{
              width: "100%",
              paddingLeft: 36,
              paddingRight: 16,
              paddingTop: 8,
              paddingBottom: 8,
              fontSize: 12,
              borderRadius: 12,
              backgroundColor: "var(--fb-bg-paper)",
              border: "1px solid var(--fb-border)",
              color: "var(--fb-text-primary)",
              boxSizing: "border-box",
              outline: "none",
            }}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            type="button"
            onClick={onRefresh}
            title="Refresh List"
            style={{
              padding: "8px 12px",
              borderRadius: 12,
              backgroundColor: "var(--fb-bg-paper)",
              border: "1px solid var(--fb-border)",
              color: "var(--fb-text-secondary)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <RefreshCw style={{ width: 16, height: 16 }} />
          </button>
        </div>
      </div>

      {/* Main Table Container */}
      <div
        className="fb-card"
        style={{
          padding: 0,
          borderRadius: 16,
          backgroundColor: "var(--fb-bg-paper)",
          border: "1px solid var(--fb-border)",
          boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          overflow: "hidden",
          flex: 1,
          display: "flex",
          flexDirection: "column",
        }}
      >
        {loading ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flex: 1,
              padding: "64px 0",
              color: "var(--fb-text-secondary)",
            }}
          >
            <RefreshCw style={{ width: 28, height: 28, animation: "spin 1s linear infinite", color: "var(--fb-primary)" }} />
          </div>
        ) : itemList.length === 0 ? (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              flex: 1,
              padding: "64px 16px",
              color: "var(--fb-text-secondary)",
              textAlign: "center",
            }}
          >
            <Inbox style={{ width: 44, height: 44, marginBottom: 12, opacity: 0.4 }} />
            <h4 style={{ fontSize: 16, fontWeight: 700, color: "var(--fb-text-primary)", margin: "0 0 4px 0" }}>
              No Pending Feedback
            </h4>
            <p style={{ fontSize: 12, maxWidth: 360, margin: 0 }}>
              All submitted feedback has been reviewed and processed.
            </p>
          </div>
        ) : (
          <div style={{ flex: 1, overflowX: "auto" }}>
            <table
              className="fb-table"
              style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 13 }}
            >
              <thead>
                <tr style={{ borderBottom: "1px solid var(--fb-border)" }}>
                  <th style={{ padding: "12px 16px", fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--fb-text-secondary)", backgroundColor: "var(--fb-bg-default)", width: 110 }}>
                    Feedback ID
                  </th>
                  <th style={{ padding: "12px 16px", fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--fb-text-secondary)", backgroundColor: "var(--fb-bg-default)", minWidth: 240 }}>
                    Question
                  </th>
                  <th style={{ padding: "12px 16px", fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--fb-text-secondary)", backgroundColor: "var(--fb-bg-default)", width: 150 }}>
                    Feedback Type
                  </th>
                  <th style={{ padding: "12px 16px", fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--fb-text-secondary)", backgroundColor: "var(--fb-bg-default)", width: 110 }}>
                    Company
                  </th>
                  <th style={{ padding: "12px 16px", fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--fb-text-secondary)", backgroundColor: "var(--fb-bg-default)", width: 120 }}>
                    Date
                  </th>
                  <th style={{ padding: "12px 16px", fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--fb-text-secondary)", backgroundColor: "var(--fb-bg-default)", width: 90 }}>
                    Status
                  </th>
                  <th style={{ padding: "12px 16px", fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--fb-text-secondary)", backgroundColor: "var(--fb-bg-default)", textAlign: "center", width: 90 }}>
                    Action
                  </th>
                </tr>
              </thead>
              <tbody>
                {itemList.map((row) => (
                  <tr
                    key={row.feedback_id}
                    onClick={() => onSelectItem(row.feedback_id)}
                    style={{ borderBottom: "1px solid var(--fb-border)", cursor: "pointer", transition: "background-color 0.2s ease" }}
                  >
                    <td style={{ padding: "12px 16px", fontFamily: "monospace", fontSize: 12, color: "var(--fb-text-secondary)" }}>
                      {row.feedback_id}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <div
                        style={{
                          fontWeight: 600,
                          fontSize: 12,
                          color: "var(--fb-text-primary)",
                          maxWidth: 380,
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {row.question}
                      </div>
                      {row.feedback_comment && (
                        <div
                          style={{
                            fontSize: 11,
                            color: "var(--fb-text-secondary)",
                            fontStyle: "italic",
                            marginTop: 2,
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            maxWidth: 380,
                          }}
                        >
                          "{row.feedback_comment}"
                        </div>
                      )}
                    </td>
                    <td style={{ padding: "12px 16px" }}>{getFeedbackTypeChip(row.feedback_type)}</td>
                    <td style={{ padding: "12px 16px", fontSize: 12, color: "var(--fb-text-secondary)", fontWeight: 500 }}>
                      {row.company_id || "Global"}
                    </td>
                    <td style={{ padding: "12px 16px", fontSize: 12, color: "var(--fb-text-secondary)" }}>
                      {formatDate(row.created_at)}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
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
                    </td>
                    <td style={{ padding: "12px 16px", textAlign: "center" }}>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectItem(row.feedback_id);
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
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "12px 16px",
            borderTop: "1px solid var(--fb-border)",
            fontSize: 12,
            color: "var(--fb-text-secondary)",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span>Rows per page:</span>
            <select
              value={rowsPerPage}
              onChange={(e) => onRowsPerPageChange && onRowsPerPageChange(Number(e.target.value))}
              style={{
                padding: "4px 8px",
                borderRadius: 8,
                backgroundColor: "var(--fb-bg-paper)",
                border: "1px solid var(--fb-border)",
                fontSize: 12,
                color: "var(--fb-text-primary)",
              }}
            >
              {[10, 25, 50, 100].map((num) => (
                <option key={num} value={num}>
                  {num}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span>
              {count === 0 ? 0 : page * rowsPerPage + 1} - {Math.min(count, (page + 1) * rowsPerPage)} of {count}
            </span>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <button
                type="button"
                disabled={page === 0}
                onClick={() => onPageChange && onPageChange(page - 1)}
                style={{
                  padding: 4,
                  borderRadius: 6,
                  border: "1px solid var(--fb-border)",
                  backgroundColor: "var(--fb-bg-paper)",
                  cursor: page === 0 ? "not-allowed" : "pointer",
                  opacity: page === 0 ? 0.3 : 1,
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <ChevronLeft style={{ width: 16, height: 16 }} />
              </button>
              <button
                type="button"
                disabled={page >= totalPages - 1}
                onClick={() => onPageChange && onPageChange(page + 1)}
                style={{
                  padding: 4,
                  borderRadius: 6,
                  border: "1px solid var(--fb-border)",
                  backgroundColor: "var(--fb-bg-paper)",
                  cursor: page >= totalPages - 1 ? "not-allowed" : "pointer",
                  opacity: page >= totalPages - 1 ? 0.3 : 1,
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <ChevronRight style={{ width: 16, height: 16 }} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default React.memo(PendingFeedbackList);
