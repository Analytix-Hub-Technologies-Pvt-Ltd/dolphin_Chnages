import React from "react";
import { Layers, ChevronRight } from "lucide-react";

const CATEGORY_COLORS = {
  incorrect_information: "#dc2626", // Red
  did_not_answer_question: "#ea580c", // Dark Orange
  irrelevant_answer: "#f97316", // Orange
  incomplete_answer: "#0284c7", // Sky Blue
  does_not_match_procedure: "#9333ea", // Purple
  other: "#6b7280", // Grey
};

const IssueCategoryChart = ({
  categories = [],
  loading = false,
  onCategoryClick,
}) => {
  const totalNegativeCount = categories.reduce((sum, c) => sum + (c.count || 0), 0);
  const maxCount = categories.length > 0 ? Math.max(...categories.map((c) => c.count || 0), 1) : 1;

  return (
    <div className="bg-bg-paper border border-border-theme rounded-2xl p-4 sm:p-5 shadow-xs h-full flex flex-col">
      {/* Title */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <Layers className="w-4 h-4" />
          </div>
          <h3 className="text-sm sm:text-base font-bold text-text-primary m-0">
            Issue Category Breakdown
          </h3>
        </div>
        <span className="text-[11px] font-semibold text-text-secondary">
          {totalNegativeCount} total issues
        </span>
      </div>

      {/* Categories Bar List */}
      <div className="flex-1 flex flex-col gap-3 justify-center">
        {loading ? (
          Array.from({ length: 5 }).map((_, idx) => (
            <div key={idx} className="w-full animate-pulse">
              <div className="h-3.5 w-1/3 bg-slate-200 dark:bg-slate-700 rounded-md mb-1.5" />
              <div className="h-2 w-full bg-slate-200 dark:bg-slate-700 rounded-full" />
            </div>
          ))
        ) : categories.length === 0 || totalNegativeCount === 0 ? (
          <div className="text-center py-6 text-text-secondary text-xs">
            No issue category data available.
          </div>
        ) : (
          categories.map((cat) => {
            const barPct = ((cat.count || 0) / maxCount) * 100;
            const barColor = CATEGORY_COLORS[cat.id] || "#106BA3";

            return (
              <button
                key={cat.id}
                type="button"
                onClick={() => onCategoryClick && onCategoryClick(cat.id)}
                title={`Click to view pending "${cat.label}" issues`}
                className="w-full flex flex-col text-left p-2 rounded-xl hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer group"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: barColor }}
                    />
                    <span className="text-xs font-semibold text-text-primary group-hover:text-primary transition-colors">
                      {cat.label}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 text-xs">
                    <span className="font-bold text-text-primary">{cat.count}</span>
                    <span className="text-text-secondary text-[11px]">
                      ({cat.percentage}%)
                    </span>
                    <ChevronRight className="w-3 h-3 text-text-secondary group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                  </div>
                </div>

                {/* Progress track */}
                <div className="w-full h-2 rounded-full bg-black/5 dark:bg-white/5 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${barPct}%`, backgroundColor: barColor }}
                  />
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
};

export default React.memo(IssueCategoryChart);
