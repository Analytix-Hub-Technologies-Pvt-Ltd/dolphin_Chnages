import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import dolphinBlack from "../assets/images/dolphin_b.png";
import DolphinWhite from "../assets/images/dolphin_w.png";
import { useThemeMode } from "../context/ThemeModeContext";
import APP_URL from "../config/apiConfig";
import { X } from "lucide-react";

export default function ForgotPasswordPopup({ open, handleClose }) {
  const [email, setEmail] = useState("");
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const { mode } = useThemeMode();
  const modalRef = useRef(null);

  useEffect(() => {
    if (!open) {
      setEmail("");
      setSuccess(false);
      setError(false);
      setLoading(false);
    }
  }, [open]);

  // Click outside to close
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && open) {
        handleClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, handleClose]);

  if (!open) return null;

  const handleSubmit = async (e) => {
    e?.preventDefault();
    setLoading(true);
    setError(false);
    try {
      await axios.post(`${APP_URL}/forgot-password`, {
        email: email,
      });
      setSuccess(true);
    } catch (err) {
      setError(true);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        ref={modalRef}
        className="relative w-full max-w-md bg-bg-paper rounded-3xl p-6 sm:p-8 shadow-2xl border border-border-theme text-text-primary"
      >
        {/* Close Button */}
        <button
          type="button"
          onClick={handleClose}
          className="absolute top-4 right-4 p-1.5 rounded-full text-text-secondary hover:text-text-primary hover:bg-bg-default transition-colors"
          aria-label="Close dialog"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Brand Header */}
        <div className="flex flex-col items-center gap-2 mb-4 text-center">
          <img
            src={mode === "dark" ? DolphinWhite : dolphinBlack}
            alt="dolphin"
            className="w-12 h-12 object-contain"
          />
          <h2 className="text-xl font-bold text-primary m-0">
            Dolphin | AI
          </h2>
          {!success && (
            <p className="text-sm font-medium text-text-secondary px-4 m-0 mt-1">
              Enter your email or user ID to receive your new password.
            </p>
          )}
        </div>

        {/* Content Body */}
        {success ? (
          <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-400 text-sm font-medium text-center">
            New password has been sent to your email.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="block text-xs font-semibold text-text-secondary mb-1">
                Email or User ID
              </label>
              <input
                type="text"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email or user ID"
                className="w-full px-3.5 py-2.5 rounded-xl bg-bg-default border border-border-theme text-text-primary text-sm focus:outline-hidden focus:border-primary focus:ring-1 focus:ring-primary transition-all placeholder:text-text-placeholder1"
              />
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs font-medium">
                Failed to send password. Please try again.
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 rounded-xl bg-primary text-white font-semibold text-sm shadow hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Sending..." : "Send Password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
