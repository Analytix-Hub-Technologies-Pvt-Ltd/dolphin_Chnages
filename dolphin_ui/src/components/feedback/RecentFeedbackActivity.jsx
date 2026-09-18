import React from "react";
import { History, ThumbsUp, ThumbsDown, Eye, ArrowRight } from "lucide-react";

const getFeedbackTypeChip = (type) => {
  switch (type) {
    case "positive":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
          <ThumbsUp className="w-3 h-3" /> Positive
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
          Mismatch Procedure
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

const getStatusBadge = (status, feedbackType) => {
  if (status === "positive" || feedbackType === "positive") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
        Positive 👍
      </span>
    );
  }
  if (status === "approved") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
        Approved
      </span>
    );
  }
  if (status === "rejected") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-slate-500/15 text-slate-600 dark:text-slate-400">
        Rejected
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-amber-500/15 text-amber-600 dark:text-amber-400">
      Pending
    </span>
  );
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

const RecentFeedbackActivity = ({
  recentItems = [],
  loading = false,
  onSelectItem,
  onViewAllPending,
}) => {
  return (
    <div className="p-6 rounded-2xl bg-bg-paper border border-border-theme shadow-sm h-full flex flex-col">
      {/* Title & View All Link */}
      <div className="flex justify-between items-center mb-4 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <History className="w-5 h-5 text-primary" />
          <h3 className="font-bold text-base text-text-primary">
            Recent Feedback Activity
          </h3>
        </div>

        <button
          type="button"
          onClick={onViewAllPending}
          className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
        >
          View all pending feedback
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-x-auto">
        {loading ? (
          <div className="py-2 animate-pulse space-y-3">
            <div className="h-10 bg-slate-200 dark:bg-slate-700 rounded-lg w-full" />
            <div className="h-10 bg-slate-200 dark:bg-slate-700 rounded-lg w-full" />
            <div className="h-10 bg-slate-200 dark:bg-slate-700 rounded-lg w-full" />
          </div>
        ) : recentItems.length === 0 ? (
          <div className="text-center py-8 text-text-secondary text-sm">
            No recent feedback recorded.
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-border-theme text-xs font-semibold text-text-secondary">
                <th className="py-2.5 px-3 w-12">Rating</th>
                <th className="py-2.5 px-3 min-w-[240px]">Question</th>
                <th className="py-2.5 px-3 w-36">Feedback Type</th>
                <th className="py-2.5 px-3 w-28">Company</th>
                <th className="py-2.5 px-3 w-24">Status</th>
                <th className="py-2.5 px-3 w-32">Created Date</th>
                <th className="py-2.5 px-3 text-center w-20">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-theme text-sm">
              {recentItems.map((item) => {
                const isPos = item.feedback_type === "positive" || item.status === "positive";

                return (
                  <tr
                    key={item.feedback_id}
                    onClick={() => onSelectItem && onSelectItem(item.feedback_id, item.status)}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/40 cursor-pointer transition-colors"
                  >
                    <td className="py-2.5 px-3">
                      {isPos ? (
                        <span title="Helpful 👍">
                          <ThumbsUp className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                        </span>
                      ) : (
                        <span title="Reported Issue 👎">
                          <ThumbsDown className="w-4 h-4 text-red-600 dark:text-red-400" />
                        </span>
                      )}
                    </td>

                    <td className="py-2.5 px-3">
                      <div className="font-semibold text-xs text-text-primary line-clamp-1 max-w-md">
                        {item.question}
                      </div>
                    </td>

                    <td className="py-2.5 px-3">{getFeedbackTypeChip(item.feedback_type)}</td>

                    <td className="py-2.5 px-3">
                      <span className="text-xs text-text-secondary font-medium">
                        {item.company_id || "Global"}
                      </span>
                    </td>

                    <td className="py-2.5 px-3">{getStatusBadge(item.status, item.feedback_type)}</td>

                    <td className="py-2.5 px-3">
                      <span className="text-xs text-text-secondary">
                        {formatDate(item.created_at)}
                      </span>
                    </td>

                    <td className="py-2.5 px-3 text-center">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (onSelectItem) onSelectItem(item.feedback_id, item.status);
                        }}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-primary hover:bg-primary-hover text-white text-xs font-semibold shadow-xs transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        Review
                      </button>
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

export default React.memo(RecentFeedbackActivity);
