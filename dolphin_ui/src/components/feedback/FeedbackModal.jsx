import React, { useState } from "react";
import { X, MessageSquare, Loader2 } from "lucide-react";
import { submitFeedback, formatErrorMessage } from "../../api/feedbackApi";

const FEEDBACK_CATEGORIES = [
  { id: "irrelevant_answer", label: "Irrelevant answer" },
  { id: "incorrect_information", label: "Incorrect information" },
  { id: "does_not_match_procedure", label: "Doesn't match company procedure" },
  { id: "incomplete_answer", label: "Incomplete answer" },
  { id: "did_not_answer_question", label: "Didn't answer my question" },
  { id: "other", label: "Other" },
];

const FeedbackModal = ({
  open,
  onClose,
  onSubmitSuccess,
  question,
  originalResponse,
  sessionId,
  messageId,
  userProfile,
  sourceMetadata = null,
}) => {
  const [selectedCategory, setSelectedCategory] = useState("incorrect_information");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  if (!open) return null;

  const handleClose = () => {
    if (submitting) return;
    setErrorMsg("");
    onClose();
  };

  const handleSubmit = async () => {
    try {
      setSubmitting(true);
      setErrorMsg("");

      const storedUserData = localStorage.getItem("userData");
      const parsedUser = storedUserData ? JSON.parse(storedUserData) : {};
      const currentUserId =
        userProfile?.id ||
        parsedUser.user_id ||
        parsedUser.id ||
        localStorage.getItem("userId") ||
        localStorage.getItem("user_id") ||
        "anonymous";
      const companyId = userProfile?.company_id || parsedUser.company_id || null;
      const shipType = userProfile?.ship_type || parsedUser.ship_type || null;

      await submitFeedback({
        question: question || "Maritime query",
        original_response: originalResponse || "",
        feedback_type: selectedCategory,
        feedback_comment: comment.trim() || null,
        user_id: String(currentUserId),
        conversation_id: sessionId ? String(sessionId) : null,
        message_id: messageId ? String(messageId) : null,
        company_id: companyId ? String(companyId) : null,
        ship_type: shipType ? String(shipType) : null,
        source_metadata:
          sourceMetadata && typeof sourceMetadata === "object" ? sourceMetadata : {},
      });

      setSubmitting(false);
      setComment("");
      onSubmitSuccess();
    } catch (err) {
      console.error("Failed to submit feedback:", err);
      setErrorMsg(formatErrorMessage(err, "Failed to submit feedback. Please try again."));
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-fade-in">
      <div className="bg-bg-paper border border-border-theme rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-theme">
          <div className="flex items-center gap-2 text-primary font-bold text-base">
            <MessageSquare className="w-5 h-5 shrink-0" />
            <h3 className="text-text-primary text-base font-bold m-0">
              What was wrong with this answer?
            </h3>
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={submitting}
            className="p-1 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 text-text-secondary transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 flex flex-col gap-4 overflow-y-auto max-h-[75vh]">
          <p className="text-xs text-text-secondary m-0 leading-relaxed">
            Your feedback helps us continuously improve the quality and accuracy of Dolphin AI responses.
          </p>

          {/* Radio Options */}
          <div className="flex flex-col gap-2">
            {FEEDBACK_CATEGORIES.map((cat) => (
              <label
                key={cat.id}
                className={`flex items-center gap-3 p-2.5 rounded-xl border transition-all cursor-pointer ${
                  selectedCategory === cat.id
                    ? "border-primary bg-primary/5 text-text-primary font-semibold"
                    : "border-border-theme hover:border-primary/40 text-text-secondary"
                }`}
              >
                <input
                  type="radio"
                  name="feedback_category"
                  value={cat.id}
                  checked={selectedCategory === cat.id}
                  onChange={() => setSelectedCategory(cat.id)}
                  className="w-4 h-4 text-primary accent-primary cursor-pointer"
                />
                <span className="text-xs">{cat.label}</span>
              </label>
            ))}
          </div>

          {/* Additional Comment */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-text-primary">
              Additional Feedback (Optional)
            </label>
            <textarea
              rows={3}
              placeholder="Please describe what should be corrected or improved..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              disabled={submitting}
              className="w-full px-3 py-2 text-xs rounded-xl border border-border-theme bg-bg-default text-text-primary placeholder:text-text-placeholder focus:outline-none focus:border-primary transition-colors resize-none"
            />
          </div>

          {errorMsg && (
            <p className="text-xs font-semibold text-red-500 m-0 bg-red-500/10 p-2.5 rounded-lg border border-red-500/20">
              {errorMsg}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-border-theme bg-black/[0.02] dark:bg-white/[0.02]">
          <button
            type="button"
            onClick={handleClose}
            disabled={submitting}
            className="px-4 py-2 text-xs font-semibold text-text-secondary hover:text-text-primary transition-colors cursor-pointer rounded-lg"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-primary hover:bg-primary-hover rounded-xl shadow-xs transition-colors cursor-pointer disabled:opacity-50"
          >
            {submitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            <span>{submitting ? "Submitting..." : "Submit Feedback"}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default FeedbackModal;
