import React, { useEffect, useRef } from "react";
import { CheckCircle, AlertCircle } from "lucide-react";

const ActionDialog = ({
  open,
  mode = "confirm", // "confirm" | "success" | "error"
  message,
  onClose,
  onConfirm,
}) => {
  const isConfirm = mode === "confirm";
  const isSuccess = mode === "success";
  const isError = mode === "error";

  const dialogRef = useRef(null);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && open) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30 backdrop-blur-xs animate-in fade-in duration-150">
      <div
        ref={dialogRef}
        className="w-full max-w-sm rounded-3xl bg-bg-paper border border-border-theme p-6 sm:p-8 shadow-2xl text-center flex flex-col items-center justify-center gap-4 animate-in zoom-in-95 duration-150"
      >
        {/* ICON */}
        {isSuccess && (
          <CheckCircle className="w-14 h-14 text-primary animate-in zoom-in" />
        )}
        {isError && (
          <AlertCircle className="w-14 h-14 text-primary animate-in zoom-in" />
        )}

        {/* TITLE */}
        <h3 className="text-xl font-bold text-text-primary m-0">
          {isConfirm ? "Delete Chat?" : isSuccess ? "Success" : "Error"}
        </h3>

        {/* MESSAGE */}
        <p className="text-sm text-text-secondary m-0 leading-relaxed">
          {message ||
            (isConfirm
              ? "Are you sure you want to permanently delete this session?"
              : "")}
        </p>

        {/* ACTION BUTTONS */}
        {isConfirm ? (
          <div className="flex gap-3 mt-2 w-full justify-center">
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2 rounded-xl border border-border-theme text-text-primary font-semibold text-sm hover:bg-bg-default transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onConfirm}
              className="px-5 py-2 rounded-xl bg-primary text-white font-semibold text-sm shadow hover:bg-primary-hover transition-colors"
            >
              Yes, Delete
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={onClose}
            className="mt-2 px-6 py-2 rounded-xl bg-primary text-white font-semibold text-sm shadow hover:bg-primary-hover transition-colors"
          >
            OK
          </button>
        )}
      </div>
    </div>
  );
};

export default ActionDialog;