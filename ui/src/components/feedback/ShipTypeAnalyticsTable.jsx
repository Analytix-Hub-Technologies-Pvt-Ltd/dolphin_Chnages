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
    <div className="p-6 rounded-2xl bg-bg-paper border border-border-theme shadow-sm h-full flex flex-col">
      {/* Title */}
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-2">
          <Ship className="w-5 h-5 text-primary" />
          <h3 className="font-bold text-base text-text-primary">
            Feedback by Ship Type
          </h3>
        </div>
        <span className="text-xs font-semibold text-text-secondary">
          {shipTypeData.length} ship types
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
        ) : shipTypeData.length === 0 ? (
          <div className="text-center py-8 text-text-secondary text-sm">
            Ship type analytics are not available for the current data.
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-border-theme text-xs font-semibold text-text-secondary">
                <th className="py-2.5 px-3">Ship Type</th>
                <th className="py-2.5 px-3 text-center">Total</th>
                <th className="py-2.5 px-3 text-center">Positive 👍</th>
                <th className="py-2.5 px-3 text-center">Negative 👎</th>
                <th className="py-2.5 px-3 text-center">Pending</th>
                <th className="py-2.5 px-3 text-center">Approved</th>
                <th className="py-2.5 px-3 text-right min-w-[140px]">Satisfaction Rate</th>
              </tr>
            </thead>
            <tbody className="divide-y border-border-theme text-sm">
              {shipTypeData.map((row) => {
                const satRate = row.satisfaction_rate;
                const hasRate = satRate !== null && satRate !== undefined && !isNaN(satRate);

                return (
                  <tr
                    key={row.ship_type}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="py-2.5 px-3 font-semibold text-text-primary text-xs">
                      {row.ship_type}
                    </td>
                    <td className="py-2.5 px-3 text-center font-bold text-text-primary text-xs">
                      {row.total}
                    </td>
                    <td className="py-2.5 px-3 text-center font-semibold text-emerald-600 dark:text-emerald-400 text-xs">
                      {row.positive}
                    </td>
                    <td className="py-2.5 px-3 text-center font-semibold text-red-600 dark:text-red-400 text-xs">
                      {row.negative}
                    </td>
                    <td className="py-2.5 px-3 text-center font-semibold text-amber-600 dark:text-amber-400 text-xs">
                      {row.pending}
                    </td>
                    <td className="py-2.5 px-3 text-center font-semibold text-emerald-600 dark:text-emerald-400 text-xs">
                      {row.approved}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="w-16 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                          {hasRate && (
                            <div
                              className={`h-full rounded-full ${
                                satRate >= 70
                                  ? "bg-emerald-500"
                                  : satRate >= 50
                                  ? "bg-amber-500"
                                  : "bg-red-500"
                              }`}
                              style={{ width: `${Math.min(100, Math.max(0, satRate))}%` }}
                            />
                          )}
                        </div>
                        <span className="text-xs font-bold text-text-primary min-w-[42px] text-right">
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
