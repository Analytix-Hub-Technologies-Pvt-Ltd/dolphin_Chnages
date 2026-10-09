import React, { useState, useEffect } from "react";
import { Box, IconButton, Tooltip, Snackbar, Alert } from "@mui/material";
import ThumbUpOffAltIcon from "@mui/icons-material/ThumbUpOffAlt";
import ThumbUpAltIcon from "@mui/icons-material/ThumbUpAlt";
import ThumbDownOffAltIcon from "@mui/icons-material/ThumbDownOffAlt";
import ThumbDownAltIcon from "@mui/icons-material/ThumbDownAlt";
import FeedbackModal from "./FeedbackModal";
import { feedbackApi } from "../../api/feedbackApi";
import { submitMessageFeedback } from "../../api/fetchApi";

const FeedbackRatingButtons = ({
  question,
  originalResponse,
  conversationId,
  messageId,
  companyId,
  shipType,
  sourceMetadata,
  initialRating,
}) => {
  const [ratingState, setRatingState] = useState(initialRating || null); // 'positive' | 'negative' | null
  const [feedbackId, setFeedbackId] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [toast, setToast] = useState({ open: false, message: "", severity: "success" });

  useEffect(() => {
    if (initialRating !== undefined) {
      setRatingState(initialRating);
    }
  }, [initialRating]);

  const userId = localStorage.getItem("userId") || localStorage.getItem("user_id") || "anonymous";

  const handlePositiveClick = async () => {
    // ── Toggle Off: if already positive, undo/revert feedback back to normal ──
    if (ratingState === "positive") {
      try {
        setRatingState(null);
        if (feedbackId) {
          await feedbackApi.deleteFeedback(feedbackId).catch(() => {});
          setFeedbackId(null);
        }
        if (conversationId && messageId) {
          await feedbackApi.deleteFeedbackByMessage(conversationId, messageId, userId).catch(() => {});
          await submitMessageFeedback({
            session_id: conversationId,
            message_id: messageId ? parseInt(messageId, 10) || null : null,
            user_id: userId,
            like: null,
          }).catch(() => {});
        }

        setToast({
          open: true,
          message: "Feedback removed",
          severity: "info",
        });
      } catch (error) {
        console.error("Failed to remove feedback:", error);
      }
      return;
    }

    // If previously negative, clear previous negative feedback first
    if (ratingState === "negative") {
      if (feedbackId) {
        await feedbackApi.deleteFeedback(feedbackId).catch(() => {});
        setFeedbackId(null);
      }
      if (conversationId && messageId) {
        await feedbackApi.deleteFeedbackByMessage(conversationId, messageId, userId).catch(() => {});
      }
    }

    // ── Submit Positive Feedback ──
    try {
      setRatingState("positive");
      const res = await feedbackApi.submitFeedback({
        question: question || "User Question",
        original_response: originalResponse || "",
        feedback_type: "positive",
        rating: "positive",
        conversation_id: conversationId,
        session_id: conversationId,
        message_id: messageId ? parseInt(messageId, 10) || null : null,
        user_id: userId,
        company_id: companyId || null,
        ship_type: shipType || null,
        source_metadata: sourceMetadata || {},
      });

      if (res && res.feedback_id) {
        setFeedbackId(res.feedback_id);
      }

      if (conversationId && messageId) {
        await submitMessageFeedback({
          session_id: conversationId,
          message_id: messageId ? parseInt(messageId, 10) || null : null,
          user_id: userId,
          like: 1,
        }).catch(() => {});
      }

      setToast({
        open: true,
        message: "Thank you for your feedback!",
        severity: "success",
      });
    } catch (error) {
      console.error("Failed to submit positive feedback:", error);
      setRatingState(null);
      setToast({
        open: true,
        message: "Failed to record feedback. Please try again.",
        severity: "error",
      });
    }
  };

  const handleNegativeClick = async () => {
    // ── Toggle Off: if already negative, undo/revert feedback back to normal ──
    if (ratingState === "negative") {
      try {
        setRatingState(null);
        if (feedbackId) {
          await feedbackApi.deleteFeedback(feedbackId).catch(() => {});
          setFeedbackId(null);
        }
        if (conversationId && messageId) {
          await feedbackApi.deleteFeedbackByMessage(conversationId, messageId, userId).catch(() => {});
          await submitMessageFeedback({
            session_id: conversationId,
            message_id: messageId ? parseInt(messageId, 10) || null : null,
            user_id: userId,
            like: null,
          }).catch(() => {});
        }

        setToast({
          open: true,
          message: "Feedback removed",
          severity: "info",
        });
      } catch (error) {
        console.error("Failed to remove feedback:", error);
      }
      return;
    }

    // If previously positive, remove positive feedback first
    if (ratingState === "positive") {
      if (feedbackId) {
        await feedbackApi.deleteFeedback(feedbackId).catch(() => {});
        setFeedbackId(null);
      }
      if (conversationId && messageId) {
        await feedbackApi.deleteFeedbackByMessage(conversationId, messageId, userId).catch(() => {});
      }
    }

    setModalOpen(true);
  };

  const handleNegativeSubmitted = async (res) => {
    setRatingState("negative");
    if (res && res.feedback_id) {
      setFeedbackId(res.feedback_id);
    }
    if (conversationId && messageId) {
      await submitMessageFeedback({
        session_id: conversationId,
        message_id: messageId ? parseInt(messageId, 10) || null : null,
        user_id: userId,
        like: -1,
      }).catch(() => {});
    }
    setToast({
      open: true,
      message: "Feedback submitted to SME moderation queue. Thank you!",
      severity: "success",
    });
  };

  return (
    <>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 0.5,
          mt: 1,
          ml: 0.5,
          opacity: 0.7,
          transition: "opacity 0.2s ease",
          "&:hover": { opacity: 1 },
        }}
      >
        <Tooltip title={ratingState === "positive" ? "Click to remove feedback" : "Good answer"}>
          <span>
            <IconButton
              size="small"
              onClick={handlePositiveClick}
              sx={{
                p: 0.5,
                color: ratingState === "positive" ? "success.main" : "text.secondary",
                "&:hover": { color: "success.main", transform: "scale(1.1)" },
                transition: "all 0.15s ease",
              }}
            >
              {ratingState === "positive" ? (
                <ThumbUpAltIcon fontSize="small" />
              ) : (
                <ThumbUpOffAltIcon fontSize="small" />
              )}
            </IconButton>
          </span>
        </Tooltip>

        <Tooltip title={ratingState === "negative" ? "Click to remove feedback" : "Report an issue with this response"}>
          <span>
            <IconButton
              size="small"
              onClick={handleNegativeClick}
              sx={{
                p: 0.5,
                color: ratingState === "negative" ? "error.main" : "text.secondary",
                "&:hover": { color: "error.main", transform: "scale(1.1)" },
                transition: "all 0.15s ease",
              }}
            >
              {ratingState === "negative" ? (
                <ThumbDownAltIcon fontSize="small" />
              ) : (
                <ThumbDownOffAltIcon fontSize="small" />
              )}
            </IconButton>
          </span>
        </Tooltip>
      </Box>

      {/* Negative Feedback Modal */}
      <FeedbackModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSuccess={handleNegativeSubmitted}
        question={question}
        originalResponse={originalResponse}
        conversationId={conversationId}
        messageId={messageId}
        companyId={companyId}
        shipType={shipType}
        sourceMetadata={sourceMetadata}
      />

      {/* Toast Notification */}
      <Snackbar
        open={toast.open}
        autoHideDuration={3500}
        onClose={() => setToast((prev) => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          onClose={() => setToast((prev) => ({ ...prev, open: false }))}
          severity={toast.severity}
          variant="filled"
          sx={{ width: "100%", borderRadius: 2, boxShadow: 4 }}
        >
          {toast.message}
        </Alert>
      </Snackbar>
    </>
  );
};

export default FeedbackRatingButtons;
