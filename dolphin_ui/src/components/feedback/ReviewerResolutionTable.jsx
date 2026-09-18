import React from "react";
import { Users } from "lucide-react";

const ReviewerResolutionTable = ({
  reviewerData = [],
  loading = false,
}) => {
  return (
    <div className="p-6 rounded-2xl bg-bg-paper border border-border-theme shadow-sm h-full flex flex-col">
      {/* Title */}
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-2">
          <Users className="w-5 h-5 text-primary" />
          <h3 className="font-bold text-base text-text-primary">
            Total Issues Resolved by SMEs
          </h3>
        </div>
        <span className="text-xs font-semibold text-text-secondary">
          {reviewerData.length} active reviewers
        </span>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-x-auto">
        {loading ? (
          <div className="py-2 animate-pulse space-y-3">
            <div className="h-9 bg-slate-200 dark:bg-slate-700 rounded-lg w-full" />
            <div className="h-9 bg-slate-200 dark:bg-slate-700 rounded-lg w-full" />
            <div className="h-9 bg-slate-200 dark:bg-slate-700 rounded-lg w-full" />
          </div>
        ) : reviewerData.length === 0 ? (
          <div className="text-center py-8 text-text-secondary text-sm">
            No reviewer resolution records found for this period.
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-border-theme text-xs font-semibold text-text-secondary">
                <th className="py-2.5 px-3">Reviewer</th>
                <th className="py-2.5 px-3 text-center">Approved</th>
                <th className="py-2.5 px-3 text-center">Rejected</th>
                <th className="py-2.5 px-3 text-right">Total Resolved</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-theme text-sm">
              {reviewerData.map((row, idx) => (
                <tr
                  key={row.reviewer || idx}
                  className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors"
                >
                  <td className="py-2.5 px-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-xs font-bold flex-shrink-0">
                        {row.reviewer ? row.reviewer.charAt(0).toUpperCase() : "U"}
                      </div>
                      <span className="font-semibold text-xs text-text-primary">
                        {row.reviewer || "Unknown Reviewer"}
                      </span>
                    </div>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                      {row.approved}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-bold bg-slate-500/15 text-slate-600 dark:text-slate-400">
                      {row.rejected}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right font-extrabold text-primary text-xs">
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
