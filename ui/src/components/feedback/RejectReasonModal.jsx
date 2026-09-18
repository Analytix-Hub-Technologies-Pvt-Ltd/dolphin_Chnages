import React, { useState } from "react";
import { Ban, X, Loader2 } from "lucide-react";

const RejectReasonModal = ({
  open,
  onClose,
  onConfirmReject,
  loading = false,
}) => {
  const [reason, setReason] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  if (!open) return null;

  const handleClose = () => {
    if (loading) return;
    setReason("");
    setErrorMsg("");
    onClose();
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!reason.trim()) {
      setErrorMsg("Rejection reason is mandatory.");
      return;
    }
    setErrorMsg("");
    onConfirmReject(reason.trim());
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="w-full max-w-lg bg-bg-paper border border-border-theme rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border-theme">
          <div className="flex items-center gap-2 text-red-600 dark:text-red-400 font-bold text-base">
            <Ban className="w-5 h-5" />
            <span>Reject Feedback Record</span>
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={loading}
            className="p-1 rounded-lg text-text-secondary hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <p className="text-xs text-text-secondary leading-relaxed">
            Please provide a mandatory reason for rejecting this feedback. Rejected feedback records are kept for auditing purposes but will not be added to the approved feedback memory or the DPO training dataset.
          </p>

          <div>
            <label className="block text-xs font-semibold text-text-primary mb-1.5">
              Rejection Reason <span className="text-red-500">*</span>
            </label>
            <textarea
              rows={3}
              placeholder="Enter the justification for rejecting this feedback submission..."
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
                if (e.target.value.trim()) setErrorMsg("");
              }}
              disabled={loading}
              className={`w-full p-3 text-xs rounded-xl bg-bg-default border ${
                errorMsg
                  ? "border-red-500 focus:ring-red-500"
                  : "border-border-theme focus:ring-primary focus:border-primary"
              } focus:outline-hidden focus:ring-1 resize-none disabled:opacity-50 transition-all`}
            />
            {errorMsg && (
              <p className="text-xs text-red-500 mt-1 font-medium">{errorMsg}</p>
            )}
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-border-theme">
            <button
              type="button"
              onClick={handleClose}
              disabled={loading}
              className="px-4 py-2 text-xs font-medium text-text-secondary hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 rounded-xl shadow-xs transition-colors disabled:opacity-50"
            >
              {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              {loading ? "Rejecting..." : "Confirm Rejection"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default RejectReasonModal;
