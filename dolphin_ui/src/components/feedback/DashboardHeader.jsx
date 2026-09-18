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
    <div className="flex flex-col gap-3">
      {/* Title & Top Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-text-primary tracking-tight m-0">
            Feedback Dashboard
          </h2>
          <p className="text-xs text-text-secondary mt-0.5 m-0">
            Monitor Dolphin AI response quality, user feedback, and review progress.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          {isFiltered && (
            <button
              type="button"
              onClick={handleClearFilters}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-border-theme text-text-secondary hover:text-text-primary text-xs font-semibold hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
              <span>Clear Filters</span>
            </button>
          )}

          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-primary hover:bg-primary-hover text-white text-xs font-semibold shadow-xs transition-colors cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>{loading ? "Refreshing..." : "Refresh"}</span>
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-bg-paper border border-border-theme rounded-2xl p-3 flex flex-wrap items-center gap-2.5 shadow-xs">
        <div className="flex items-center gap-1 text-text-secondary mr-1">
          <Filter className="w-3.5 h-3.5 text-primary" />
          <span className="text-[11px] font-bold uppercase tracking-wider">Filters</span>
        </div>

        {/* Date Range */}
        <select
          value={filters.dateRange || "30d"}
          onChange={(e) => onFilterChange({ ...filters, dateRange: e.target.value })}
          className="px-2.5 py-1.5 rounded-xl border border-border-theme bg-bg-default text-text-primary text-xs font-medium focus:outline-none focus:border-primary transition-colors cursor-pointer"
        >
          {DATE_RANGE_OPTIONS.map((opt) => (
            <option key={opt.id} value={opt.id}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Custom Range */}
        {filters.dateRange === "custom" && (
          <div className="flex items-center gap-1.5">
            <input
              type="date"
              value={filters.fromDate || ""}
              onChange={(e) => onFilterChange({ ...filters, fromDate: e.target.value })}
              className="px-2 py-1 rounded-xl border border-border-theme bg-bg-default text-text-primary text-xs focus:outline-none focus:border-primary"
            />
            <span className="text-xs text-text-secondary">to</span>
            <input
              type="date"
              value={filters.toDate || ""}
              onChange={(e) => onFilterChange({ ...filters, toDate: e.target.value })}
              className="px-2 py-1 rounded-xl border border-border-theme bg-bg-default text-text-primary text-xs focus:outline-none focus:border-primary"
            />
          </div>
        )}

        {/* Company */}
        <select
          value={filters.companyId || "all"}
          onChange={(e) => onFilterChange({ ...filters, companyId: e.target.value })}
          className="px-2.5 py-1.5 rounded-xl border border-border-theme bg-bg-default text-text-primary text-xs font-medium focus:outline-none focus:border-primary transition-colors cursor-pointer"
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
            className="px-2.5 py-1.5 rounded-xl border border-border-theme bg-bg-default text-text-primary text-xs font-medium focus:outline-none focus:border-primary transition-colors cursor-pointer"
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
          className="px-2.5 py-1.5 rounded-xl border border-border-theme bg-bg-default text-text-primary text-xs font-medium focus:outline-none focus:border-primary transition-colors cursor-pointer"
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
          className="px-2.5 py-1.5 rounded-xl border border-border-theme bg-bg-default text-text-primary text-xs font-medium focus:outline-none focus:border-primary transition-colors cursor-pointer"
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
