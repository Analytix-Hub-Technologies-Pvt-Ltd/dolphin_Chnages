import React, { useState } from "react";
import { ThumbsUp, ThumbsDown, CheckCircle2, AlertCircle } from "lucide-react";
import { submitFeedback, formatErrorMessage } from "../../api/feedbackApi";
import FeedbackModal from "./FeedbackModal";

const FeedbackRatingButtons = ({
  question,
  originalResponse,
  sessionId,
  messageId,
  userProfile,
  sourceMetadata = null,
}) => {
  const [rating, setRating] = useState(null); // 'positive' | 'negative' | null
  const [modalOpen, setModalOpen] = useState(false);
  const [toast, setToast] = useState(null); // { message, type: 'success' | 'error' }

  const showToast = (message, type = "success") => {
    setToast({ message, type });
    setTimeout(() => {
      setToast(null);
    }, 4000);
  };

  const handlePositiveFeedback = async () => {
    if (rating === "positive") return;
    setRating("positive");
    try {
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
        feedback_type: "positive",
        feedback_comment: "User rated helpful 👍",
        user_id: String(currentUserId),
        conversation_id: sessionId ? String(sessionId) : null,
        message_id: messageId ? String(messageId) : null,
        company_id: companyId ? String(companyId) : null,
        ship_type: shipType ? String(shipType) : null,
        source_metadata:
          sourceMetadata && typeof sourceMetadata === "object" ? sourceMetadata : {},
      });
      showToast("Thank you for your feedback!", "success");
    } catch (error) {
      console.error("Error submitting positive feedback:", error);
      showToast(formatErrorMessage(error, "Failed to submit feedback."), "error");
      setRating(null);
    }
  };

  const handleNegativeClick = () => {
    setModalOpen(true);
  };

  const handleModalSubmitSuccess = () => {
    setRating("negative");
    setModalOpen(false);
    showToast("Thank you. Your feedback has been submitted for review.", "success");
  };

  return (
    <div className="inline-flex items-center gap-1.5 mt-2 pt-1 border-t border-dashed border-border-theme relative">
      <button
        type="button"
        title="Helpful response"
        onClick={handlePositiveFeedback}
        className={`p-1.5 rounded-lg transition-all cursor-pointer ${
          rating === "positive"
            ? "text-primary bg-primary/10"
            : "text-text-secondary hover:text-primary hover:bg-black/5 dark:hover:bg-white/5"
        }`}
      >
        <ThumbsUp
          className={`w-3.5 h-3.5 transition-transform ${
            rating === "positive" ? "fill-primary scale-110" : "hover:scale-110"
          }`}
        />
      </button>

      <button
        type="button"
        title="Report an issue or suggest improvement"
        onClick={handleNegativeClick}
        className={`p-1.5 rounded-lg transition-all cursor-pointer ${
          rating === "negative"
            ? "text-red-500 bg-red-500/10"
            : "text-text-secondary hover:text-red-500 hover:bg-black/5 dark:hover:bg-white/5"
        }`}
      >
        <ThumbsDown
          className={`w-3.5 h-3.5 transition-transform ${
            rating === "negative" ? "fill-red-500 scale-110" : "hover:scale-110"
          }`}
        />
      </button>

      <FeedbackModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmitSuccess={handleModalSubmitSuccess}
        question={question}
        originalResponse={originalResponse}
        sessionId={sessionId}
        messageId={messageId}
        userProfile={userProfile}
        sourceMetadata={sourceMetadata}
      />

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 px-4 py-2.5 rounded-xl shadow-lg bg-bg-paper border border-border-theme text-xs font-semibold animate-fade-in">
          {toast.type === "success" ? (
            <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />
          )}
          <span className="text-text-primary">{toast.message}</span>
        </div>
      )}
    </div>
  );
};

export default React.memo(FeedbackRatingButtons);
