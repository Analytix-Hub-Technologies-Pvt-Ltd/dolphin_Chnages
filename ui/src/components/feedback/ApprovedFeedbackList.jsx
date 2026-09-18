import React from "react";
import { Search, Eye, RefreshCw, CheckCircle2, ChevronLeft, ChevronRight } from "lucide-react";

const getFeedbackTypeChip = (type) => {
  switch (type) {
    case "positive":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
          Positive 👍
        </span>
      );
    case "incorrect_information":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border border-red-500/30 text-red-600 dark:text-red-400 bg-red-500/10">
          Incorrect Info
        </span>
      );
    case "does_not_match_procedure":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border border-amber-500/30 text-amber-600 dark:text-amber-400 bg-amber-500/10">
          Mismatch SMS/Procedure
        </span>
      );
    case "irrelevant_answer":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border border-slate-500/30 text-slate-600 dark:text-slate-400 bg-slate-500/10">
          Irrelevant
        </span>
      );
    case "incomplete_answer":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border border-sky-500/30 text-sky-600 dark:text-sky-400 bg-sky-500/10">
          Incomplete
        </span>
      );
    case "did_not_answer_question":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border border-purple-500/30 text-purple-600 dark:text-purple-400 bg-purple-500/10">
          Didn't Answer
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border border-border-theme text-text-secondary">
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

const ApprovedFeedbackList = ({
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
  const count = totalCount !== undefined ? totalCount : items.length;
  const totalPages = Math.ceil(count / rowsPerPage) || 1;

  return (
    <div className="w-full h-full flex flex-col space-y-4">
      {/* Search & Actions Bar */}
      <div className="flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-3">
        <div className="relative w-full sm:w-96">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
          <input
            type="text"
            placeholder="Search approved questions, feedback ID, comments..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-xs rounded-xl bg-bg-paper border border-border-theme text-text-primary focus:outline-hidden focus:ring-1 focus:ring-primary shadow-2xs"
          />
        </div>

        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onRefresh}
            title="Refresh List"
            className="p-2 rounded-xl bg-bg-paper border border-border-theme text-text-secondary hover:text-text-primary hover:bg-slate-50 dark:hover:bg-slate-800/40 shadow-2xs transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Table Container */}
      <div className="flex-1 flex flex-col rounded-2xl bg-bg-paper border border-border-theme shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center flex-1 py-16 animate-pulse text-text-secondary">
            <RefreshCw className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center flex-1 py-16 text-text-secondary text-center px-4">
            <CheckCircle2 className="w-12 h-12 mb-3 opacity-40 text-emerald-500" />
            <h4 className="text-base font-bold text-text-primary mb-1">
              No Approved Feedback Yet
            </h4>
            <p className="text-xs max-w-sm">
              Review and approve pending feedback to build the feedback memory and DPO dataset.
            </p>
          </div>
        ) : (
          <div className="flex-1 overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-border-theme bg-bg-header/50 text-xs font-semibold text-text-secondary">
                  <th className="py-3 px-4 min-w-[280px]">Question</th>
                  <th className="py-3 px-4 w-40">Feedback Type</th>
                  <th className="py-3 px-4 w-28">Company</th>
                  <th className="py-3 px-4 w-36">Approved Date</th>
                  <th className="py-3 px-4 w-24">Status</th>
                  <th className="py-3 px-4 text-center w-24">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-theme text-sm">
                {items.map((row) => (
                  <tr
                    key={row.feedback_id}
                    onClick={() => onSelectItem(row.feedback_id)}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/40 cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-4">
                      <div className="font-medium text-xs text-text-primary line-clamp-2">
                        {row.question}
                      </div>
                      {row.preferred_response && (
                        <div className="text-[11px] text-primary font-medium line-clamp-1 mt-0.5">
                          Correction: {row.preferred_response.slice(0, 80)}...
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4">{getFeedbackTypeChip(row.feedback_type)}</td>
                    <td className="py-3 px-4 text-xs text-text-secondary font-medium">
                      {row.company_id || "Global"}
                    </td>
                    <td className="py-3 px-4 text-xs text-text-secondary">
                      {formatDate(row.reviewed_at || row.updated_at || row.created_at)}
                    </td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                        Approved
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectItem(row.feedback_id);
                        }}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-primary/40 text-primary hover:bg-primary/10 text-xs font-semibold shadow-2xs transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-3 border-t border-border-theme text-xs text-text-secondary">
          <div className="flex items-center gap-2">
            <span>Rows per page:</span>
            <select
              value={rowsPerPage}
              onChange={(e) => onRowsPerPageChange && onRowsPerPageChange(Number(e.target.value))}
              className="px-2 py-1 rounded-lg bg-bg-paper border border-border-theme text-xs font-medium text-text-primary focus:outline-hidden"
            >
              {[10, 25, 50, 100].map((num) => (
                <option key={num} value={num}>
                  {num}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-3">
            <span>
              {count === 0 ? 0 : page * rowsPerPage + 1} - {Math.min(count, (page + 1) * rowsPerPage)} of {count}
            </span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled={page === 0}
                onClick={() => onPageChange && onPageChange(page - 1)}
                className="p-1 rounded-md border border-border-theme disabled:opacity-30 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                type="button"
                disabled={page >= totalPages - 1}
                onClick={() => onPageChange && onPageChange(page + 1)}
                className="p-1 rounded-md border border-border-theme disabled:opacity-30 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default React.memo(ApprovedFeedbackList);
