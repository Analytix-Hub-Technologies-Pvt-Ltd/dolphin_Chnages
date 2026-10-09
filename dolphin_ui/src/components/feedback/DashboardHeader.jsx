import React from "react";
import { Filter, RefreshCw, X } from "lucide-react";

const DATE_RANGE_OPTIONS = [
  { id: "7d", label: "Last 7 Days" },
  { id: "30d", label: "Last 30 Days" },
  { id: "90d", label: "Last 90 Days" },
  { id: "custom", label: "Custom Range" },
];

const STATUS_OPTIONS = [
  { id: "all", label: "All Statuses" },
  { id: "pending", label: "Pending" },
  { id: "approved", label: "Approved" },
  { id: "rejected", label: "Rejected" },
];

const CATEGORY_OPTIONS = [
  { id: "all", label: "All Categories" },
  { id: "incorrect_information", label: "Incorrect Information" },
  { id: "irrelevant_answer", label: "Irrelevant Answer" },
  { id: "does_not_match_procedure", label: "Doesn't Match Procedure" },
  { id: "incomplete_answer", label: "Incomplete Answer" },
  { id: "did_not_answer_question", label: "Didn't Answer Question" },
  { id: "other", label: "Other" },
];

const selectStyle = {
  padding: "6px 12px",
  borderRadius: 10,
  border: "1px solid var(--fb-border)",
  backgroundColor: "var(--fb-bg-default)",
  color: "var(--fb-text-primary)",
  fontSize: 12,
  fontWeight: 500,
  cursor: "pointer",
  outline: "none",
};

const DashboardHeader = ({
  filters,
  onFilterChange,
  onRefresh,
  loading = false,
  availableCompanies = [],
  availableShipTypes = [],
}) => {
  const isFiltered =
    filters.dateRange !== "30d" ||
    (filters.companyId && filters.companyId !== "all") ||
    (filters.shipType && filters.shipType !== "all") ||
    (filters.status && filters.status !== "all") ||
    (filters.feedbackType && filters.feedbackType !== "all");

  const handleClearFilters = () => {
    onFilterChange({
      dateRange: "30d",
      fromDate: null,
      toDate: null,
      companyId: "all",
      shipType: "all",
      status: "all",
      feedbackType: "all",
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, marginBottom: 20 }}>
      {/* Title & Top Actions */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <h2
            style={{
              fontSize: 24,
              fontWeight: 800,
              color: "var(--fb-text-primary)",
              letterSpacing: "-0.02em",
              margin: 0,
            }}
          >
            Feedback Dashboard
          </h2>
          <p style={{ fontSize: 12, color: "var(--fb-text-secondary)", margin: "4px 0 0 0" }}>
            Monitor Dolphin AI response quality, user feedback, and review progress.
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {isFiltered && (
            <button
              type="button"
              onClick={handleClearFilters}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 14px",
                borderRadius: 12,
                border: "1px solid var(--fb-border)",
                color: "var(--fb-text-secondary)",
                fontSize: 12,
                fontWeight: 600,
                background: "var(--fb-bg-paper)",
                cursor: "pointer",
              }}
            >
              <X style={{ width: 14, height: 14 }} />
              <span>Clear Filters</span>
            </button>
          )}

          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "8px 18px",
              borderRadius: 12,
              backgroundColor: "var(--fb-primary)",
              color: "#ffffff",
              fontSize: 12,
              fontWeight: 600,
              border: "none",
              cursor: "pointer",
              boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
            }}
          >
            <RefreshCw
              style={{
                width: 14,
                height: 14,
                animation: loading ? "spin 1s linear infinite" : "none",
              }}
            />
            <span>{loading ? "Refreshing..." : "Refresh"}</span>
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div
        className="fb-filter-bar"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "10px 16px",
          borderRadius: 16,
          backgroundColor: "var(--fb-bg-paper)",
          border: "1px solid var(--fb-border)",
          boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--fb-text-secondary)", marginRight: 6 }}>
          <Filter style={{ width: 14, height: 14, color: "var(--fb-primary)" }} />
          <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Filters
          </span>
        </div>

        {/* Date Range */}
        <select
          value={filters.dateRange || "30d"}
          onChange={(e) => onFilterChange({ ...filters, dateRange: e.target.value })}
          style={selectStyle}
        >
          {DATE_RANGE_OPTIONS.map((opt) => (
            <option key={opt.id} value={opt.id}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Custom Range */}
        {filters.dateRange === "custom" && (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input
              type="date"
              value={filters.fromDate || ""}
              onChange={(e) => onFilterChange({ ...filters, fromDate: e.target.value })}
              style={{ ...selectStyle, padding: "4px 8px" }}
            />
            <span style={{ fontSize: 12, color: "var(--fb-text-secondary)" }}>to</span>
            <input
              type="date"
              value={filters.toDate || ""}
              onChange={(e) => onFilterChange({ ...filters, toDate: e.target.value })}
              style={{ ...selectStyle, padding: "4px 8px" }}
            />
          </div>
        )}

        {/* Company */}
        <select
          value={filters.companyId || "all"}
          onChange={(e) => onFilterChange({ ...filters, companyId: e.target.value })}
          style={selectStyle}
        >
          <option value="all">All Companies</option>
          {availableCompanies.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>

        {/* Ship Type */}
        {availableShipTypes.length > 0 && (
          <select
            value={filters.shipType || "all"}
            onChange={(e) => onFilterChange({ ...filters, shipType: e.target.value })}
            style={selectStyle}
          >
            <option value="all">All Ship Types</option>
            {availableShipTypes.map((st) => (
              <option key={st} value={st}>
                {st}
              </option>
            ))}
          </select>
        )}

        {/* Status */}
        <select
          value={filters.status || "all"}
          onChange={(e) => onFilterChange({ ...filters, status: e.target.value })}
          style={selectStyle}
        >
          {STATUS_OPTIONS.map((st) => (
            <option key={st.id} value={st.id}>
              {st.label}
            </option>
          ))}
        </select>

        {/* Category */}
        <select
          value={filters.feedbackType || "all"}
          onChange={(e) => onFilterChange({ ...filters, feedbackType: e.target.value })}
          style={selectStyle}
        >
          {CATEGORY_OPTIONS.map((cat) => (
            <option key={cat.id} value={cat.id}>
              {cat.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
};

export default React.memo(DashboardHeader);
