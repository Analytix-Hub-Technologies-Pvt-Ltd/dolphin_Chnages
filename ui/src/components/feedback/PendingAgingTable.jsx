import React from "react";
import { Clock, AlertTriangle } from "lucide-react";

const PendingAgingTable = ({
  agingData = [],
  loading = false,
  onAgingBucketClick,
}) => {
  const totalPending = agingData.reduce((sum, a) => sum + (a.count || 0), 0);

  return (
    <div className="p-6 rounded-2xl bg-bg-paper border border-border-theme shadow-sm h-full flex flex-col">
      {/* Title */}
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-2">
          <Clock className="w-5 h-5 text-primary" />
          <h3 className="font-bold text-base text-text-primary">
            Pending Issue — Aging
          </h3>
        </div>
        <span className="text-xs font-semibold text-text-secondary">
          {totalPending} total pending
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
        ) : agingData.length === 0 || totalPending === 0 ? (
          <div className="text-center py-8 text-text-secondary text-sm">
            No pending issues in queue. All clear! 🎉
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-border-theme text-xs font-semibold text-text-secondary">
                <th className="py-2.5 px-3">Age Bracket</th>
                <th className="py-2.5 px-3 text-center">Issues Count</th>
                <th className="py-2.5 px-3 text-right">Status Indicator</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-theme text-sm">
              {agingData.map((row) => {
                const isOldest = row.is_oldest || row.bucket === "> 3 days";
                const hasIssues = (row.count || 0) > 0;

                return (
                  <tr
                    key={row.bucket}
                    onClick={() => onAgingBucketClick && onAgingBucketClick(row.bucket)}
                    className={`cursor-pointer transition-colors ${
                      isOldest && hasIssues
                        ? "bg-amber-500/10 hover:bg-amber-500/15"
                        : "hover:bg-slate-50 dark:hover:bg-slate-800/40"
                    }`}
                  >
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-1.5">
                        {isOldest && hasIssues && (
                          <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0" />
                        )}
                        <span
                          className={`text-xs ${
                            isOldest ? "font-bold" : "font-semibold"
                          } ${
                            isOldest && hasIssues
                              ? "text-amber-600 dark:text-amber-400"
                              : "text-text-primary"
                          }`}
                        >
                          {row.bucket}
                        </span>
                      </div>
                    </td>

                    <td className="py-2.5 px-3 text-center">
                      <span
                        className={`inline-flex items-center justify-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                          isOldest && hasIssues
                            ? "bg-amber-500/20 text-amber-700 dark:text-amber-300"
                            : hasIssues
                            ? "bg-primary/10 text-primary"
                            : "bg-slate-100 dark:bg-slate-800 text-text-secondary"
                        }`}
                      >
                        {row.count}
                      </span>
                    </td>

                    <td className="py-2.5 px-3 text-right">
                      {isOldest && hasIssues ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border border-amber-500 text-amber-600 dark:text-amber-400">
                          Requires Attention
                        </span>
                      ) : hasIssues ? (
                        <span className="text-xs text-text-secondary font-medium">
                          Normal Queue
                        </span>
                      ) : (
                        <span className="text-xs text-text-secondary/50">
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
