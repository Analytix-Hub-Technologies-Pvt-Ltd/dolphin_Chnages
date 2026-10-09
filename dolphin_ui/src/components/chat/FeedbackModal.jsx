import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  IconButton,
  Button,
  RadioGroup,
  FormControlLabel,
  Radio,
  TextField,
  Box,
  CircularProgress,
  Alert,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import ReportProblemOutlinedIcon from "@mui/icons-material/ReportProblemOutlined";
import { feedbackApi } from "../../api/feedbackApi";

const FEEDBACK_CATEGORIES = [
  { value: "irrelevant_answer", label: "Irrelevant answer" },
  { value: "incorrect_information", label: "Incorrect information" },
  { value: "does_not_match_procedure", label: "Doesn't match company procedure" },
  { value: "incomplete_answer", label: "Incomplete answer" },
  { value: "did_not_answer_question", label: "Didn't answer my question" },
  { value: "other", label: "Other" },
];

const FeedbackModal = ({
  open,
  onClose,
  onSuccess,
  question,
  originalResponse,
  conversationId,
  messageId,
  companyId,
  shipType,
  sourceMetadata,
}) => {
  const [selectedCategory, setSelectedCategory] = useState("incorrect_information");
  const [commentText, setCommentText] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const userId = localStorage.getItem("userId") || localStorage.getItem("user_id") || "anonymous";

  const handleSubmit = async () => {
    if (!selectedCategory) {
      setErrorMsg("Please select an issue category");
      return;
    }

    setLoading(true);
    setErrorMsg("");

    try {
      const categoryObj = FEEDBACK_CATEGORIES.find((c) => c.value === selectedCategory);
      const categoryLabel = categoryObj ? categoryObj.label : selectedCategory;

      const res = await feedbackApi.submitFeedback({
        question: question || "User Question",
        original_response: originalResponse || "",
        feedback_type: "negative",
        rating: "negative",
        category: categoryLabel,
        comment: commentText.trim() || null,
        feedback_comment: commentText.trim() || null,
        conversation_id: conversationId,
        session_id: conversationId,
        message_id: messageId ? parseInt(messageId, 10) || null : null,
        user_id: userId,
        company_id: companyId || null,
        ship_type: shipType || null,
        source_metadata: sourceMetadata || {},
      });

      onClose();
      if (onSuccess) onSuccess(res);
      // Reset state
      setCommentText("");
      setSelectedCategory("incorrect_information");
    } catch (err) {
      console.error("Failed to submit negative feedback:", err);
      setErrorMsg(err.message || "Failed to submit feedback. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={loading ? undefined : onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 3,
          bgcolor: "background.paper",
          p: 1,
        },
      }}
    >
      <DialogTitle
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          pb: 1.5,
          borderBottom: "1px solid",
          borderColor: "divider",
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <ReportProblemOutlinedIcon color="error" />
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            What was wrong with this answer?
          </Typography>
        </Box>
        <IconButton
          onClick={onClose}
          size="small"
          disabled={loading}
          sx={{ color: "text.secondary" }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ mt: 2 }}>
        {errorMsg && (
          <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>
            {errorMsg}
          </Alert>
        )}

        <Typography variant="body2" sx={{ color: "text.secondary", mb: 1.5 }}>
          Select the reason that best describes the issue. Your feedback feeds into the SME moderation queue for correction.
        </Typography>

        <RadioGroup
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          sx={{ mb: 2 }}
        >
          {FEEDBACK_CATEGORIES.map((cat) => (
            <FormControlLabel
              key={cat.value}
              value={cat.value}
              control={<Radio size="small" color="primary" />}
              label={<Typography variant="body2" sx={{ fontWeight: 500 }}>{cat.label}</Typography>}
              sx={{
                py: 0.3,
                px: 1,
                borderRadius: 1.5,
                "&:hover": { bgcolor: "action.hover" },
              }}
            />
          ))}
        </RadioGroup>

        <Typography variant="caption" sx={{ fontWeight: 600, color: "text.secondary", display: "block", mb: 0.5 }}>
          Optional explanation or correct procedure details:
        </Typography>
        <TextField
          multiline
          rows={3}
          fullWidth
          variant="outlined"
          placeholder="e.g., According to company SMS procedure section 4.2, the safety checklist must include..."
          value={commentText}
          onChange={(e) => setCommentText(e.target.value)}
          disabled={loading}
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: 2,
              backgroundColor: "background.light",
              fontSize: "0.875rem",
            },
          }}
        />
      </DialogContent>

      <DialogActions sx={{ p: 2, pt: 1, gap: 1 }}>
        <Button
          onClick={onClose}
          variant="outlined"
          disabled={loading}
          sx={{
            textTransform: "none",
            borderRadius: 2,
            px: 2.5,
          }}
        >
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading}
          startIcon={loading ? <CircularProgress size={16} color="inherit" /> : null}
          sx={{
            textTransform: "none",
            borderRadius: 2,
            px: 3,
            bgcolor: "primary.main",
            "&:hover": { bgcolor: "primary.dark" },
          }}
        >
          {loading ? "Submitting..." : "Submit Feedback"}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default FeedbackModal;
