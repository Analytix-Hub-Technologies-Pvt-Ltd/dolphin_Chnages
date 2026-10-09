import React, { useState, useEffect, useRef } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Bot,
  FileEdit,
  Building2,
  Ship,
  User,
  FileCode,
  Loader2,
  AlertTriangle,
  Sparkles,
  BookOpen,
  Search,
  Check,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

import { sanitizeMarkdown } from "../chat/ChatWindow";
import RejectReasonModal from "./RejectReasonModal";
import {
  approveFeedback,
  rejectFeedback,
  regenerateFeedbackResponse,
  searchReferenceTopics,
  formatErrorMessage,
} from "../../api/feedbackApi";

const SUGGESTED_QUICK_TOPICS = [
  "Enclosed Space Entry Safety & Gas Testing",
  "Hot Work Permit & Fire Watch Procedures",
  "Bunkering Safety Checklist & Spill Prevention",
  "Lifeboat & Rescue Boat Drill Operations",
  "MARPOL Annex VI SOx & NOx Regulations",
  "STCW Navigational Watchkeeping Standards",
  "SOLAS LSA & FFA Maintenance Intervals",
  "Oil Record Book Part I Entry Guidelines",
];

const PendingDetailView = ({
  item,
  loading = false,
  onBack,
  onActionComplete,
  reviewerId = "admin",
}) => {
  const [preferredResponse, setPreferredResponse] = useState("");
  const [adminComment, setAdminComment] = useState("");
  const [editQuestion, setEditQuestion] = useState("");
  const [isEditingQuestion, setIsEditingQuestion] = useState(false);
  const [editorTab, setEditorTab] = useState(0); // 0: Edit, 1: Preview
  const [submitting, setSubmitting] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successBanner, setSuccessBanner] = useState("");

  // AI-Assisted Regeneration State
  const [topic, setTopic] = useState("");
  const [referenceText, setReferenceText] = useState("");
  const [reviewerInstructions, setReviewerInstructions] = useState("");
  const [showAdvancedInputs, setShowAdvancedInputs] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [topicSuggestions, setTopicSuggestions] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [showSuggestionsDropdown, setShowSuggestionsDropdown] = useState(false);
  const [lastGeneratedTopic, setLastGeneratedTopic] = useState("");

  const dropdownRef = useRef(null);

  useEffect(() => {
    if (item) {
      setPreferredResponse(item.preferred_response || item.edited_response || item.original_response || "");
      setAdminComment(item.admin_comment || item.reviewer_notes || "");
      setEditQuestion(item.question || "");
      setIsEditingQuestion(false);
      setErrorMessage("");
      setSuccessBanner("");
      setLastGeneratedTopic("");
      setTopic("");
      setReferenceText("");
      setReviewerInstructions("");
    }
  }, [item]);

  // Topic search debounce
  useEffect(() => {
    let active = true;
    if (!topic || topic.trim().length < 2) {
      setTopicSuggestions([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        setSearchLoading(true);
        const data = await searchReferenceTopics(topic.trim(), item?.company_id || null);
        if (active && data && data.results) {
          setTopicSuggestions(data.results);
        }
      } catch (err) {
        console.warn("Topic suggestion error:", err);
      } finally {
        if (active) setSearchLoading(false);
      }
    }, 300);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [topic, item?.company_id]);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowSuggestionsDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 380 }}>
        <Loader2 style={{ width: 32, height: 32, color: "var(--fb-primary)", animation: "spin 1s linear infinite" }} />
      </div>
    );
  }

  if (!item) {
    return (
      <div style={{ padding: 32, textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: "var(--fb-text-primary)", margin: 0 }}>
          Feedback record not found.
        </h3>
        <button
          type="button"
          onClick={onBack}
          className="fb-btn-primary"
        >
          <ArrowLeft style={{ width: 16, height: 16 }} />
          <span>Back to Pending List</span>
        </button>
      </div>
    );
  }

  const handleSelectTopicSuggestion = (selectedTitle) => {
    setTopic(selectedTitle);
    setShowSuggestionsDropdown(false);
  };

  const handleRegenerate = async () => {
    const cleanTopic = topic.trim();
    if (!cleanTopic) {
      setErrorMessage("Please enter or select a Reference Topic / SOP / Course Content title.");
      return;
    }

    try {
      setRegenerating(true);
      setErrorMessage("");
      setSuccessBanner("");

      const result = await regenerateFeedbackResponse(item.feedback_id, {
        topic: cleanTopic,
        referenceText: referenceText.trim() || null,
        reviewerInstructions: reviewerInstructions.trim() || null,
        companyId: item.company_id || null,
        shipType: item.ship_type || null,
      });

      const genText =
        result?.generated_preferred_response ||
        result?.generated_response ||
        result?.preferred_response ||
        result?.response;

      if (genText && typeof genText === "string" && genText.trim()) {
        setPreferredResponse(genText.trim());
        setLastGeneratedTopic(cleanTopic);
        setEditorTab(1); // switch to Markdown Preview so admin can see formatted answer
        setSuccessBanner(
          `✨ AI Response generated based on "${cleanTopic}"! Review the formatted response below and click "Agree & Approve".`
        );
      } else {
        setErrorMessage("AI generation returned an empty response. Please try again.");
      }
      setRegenerating(false);
    } catch (err) {
      console.error("Failed to regenerate response:", err);
      setErrorMessage(formatErrorMessage(err, "Failed to generate AI response from reference."));
      setRegenerating(false);
    }
  };

  const handleApprove = async () => {
    if (!preferredResponse.trim()) {
      setErrorMessage("Preferred / Corrected Response cannot be empty for approval.");
      return;
    }

    try {
      setSubmitting(true);
      setErrorMessage("");
      await approveFeedback(item.feedback_id, {
        preferredResponse: preferredResponse.trim(),
        question: editQuestion.trim() || item.question,
        reviewerId: reviewerId || "admin",
        adminComment: adminComment.trim() || null,
      });
      setSubmitting(false);
      onActionComplete("approved", item.feedback_id);
    } catch (err) {
      console.error("Failed to approve feedback:", err);
      setErrorMessage(formatErrorMessage(err, "Failed to approve feedback."));
      setSubmitting(false);
    }
  };

  const handleConfirmReject = async (rejectionReason) => {
    try {
      setSubmitting(true);
      setErrorMessage("");
      await rejectFeedback(item.feedback_id, {
        rejectionReason: rejectionReason,
        reviewerId: reviewerId || "admin",
      });
      setSubmitting(false);
      setRejectModalOpen(false);
      onActionComplete("rejected", item.feedback_id);
    } catch (err) {
      console.error("Failed to reject feedback:", err);
      setErrorMessage(formatErrorMessage(err, "Failed to reject feedback."));
      setSubmitting(false);
    }
  };

  const isIrrelevantOrIncorrect =
    item.feedback_type === "irrelevant_answer" ||
    item.feedback_type === "incorrect_information" ||
    item.feedback_type === "does_not_match_procedure" ||
    item.feedback_type === "did_not_answer_question";

  return (
    <div className="fb-detail-container" style={{ width: "100%", display: "flex", flexDirection: "column", gap: 20, paddingBottom: 40, boxSizing: "border-box" }}>
      {/* 1. Top Header with Back Navigation & Badges */}
      <div className="fb-detail-top-bar" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12, width: "100%" }}>
        <button
          type="button"
          onClick={onBack}
          className="fb-back-btn"
          style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 12, border: "1px solid var(--fb-border)", backgroundColor: "var(--fb-bg-paper)", color: "var(--fb-text-primary)", fontSize: 12, fontWeight: 600, cursor: "pointer", boxShadow: "0 1px 2px rgba(0,0,0,0.05)" }}
        >
          <ArrowLeft style={{ width: 16, height: 16 }} />
          <span>Back to Pending List</span>
        </button>

        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontFamily: "monospace", fontSize: 12, padding: "4px 10px", borderRadius: 8, border: "1px solid var(--fb-border)", backgroundColor: "var(--fb-bg-paper)", color: "var(--fb-text-secondary)" }}>
            ID: {item.feedback_id}
          </span>
          <span style={{ fontSize: 12, fontWeight: 700, padding: "4px 10px", borderRadius: 9999, backgroundColor: "rgba(217, 119, 6, 0.15)", color: "var(--fb-warning)" }}>
            Pending Admin Review
          </span>
        </div>
      </div>

      {/* Error Message */}
      {errorMessage && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderRadius: 12, backgroundColor: "rgba(220, 38, 38, 0.08)", border: "1px solid rgba(220, 38, 38, 0.3)", color: "var(--fb-danger)", fontSize: 12, fontWeight: 600 }}>
          <AlertTriangle style={{ width: 16, height: 16, flexShrink: 0 }} />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Success Banner */}
      {successBanner && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderRadius: 12, backgroundColor: "rgba(22, 163, 74, 0.08)", border: "1px solid rgba(22, 163, 74, 0.3)", color: "var(--fb-success)", fontSize: 12, fontWeight: 600 }}>
          <Check style={{ width: 16, height: 16, flexShrink: 0 }} />
          <span>{successBanner}</span>
        </div>
      )}

      {/* 2. TOP FEATURE: AI-Assisted Response Generator from Reference Topic */}
      <div
        className="fb-ai-banner"
        style={{
          padding: 20,
          borderRadius: 16,
          background: "linear-gradient(135deg, rgba(16, 107, 163, 0.08) 0%, rgba(99, 102, 241, 0.05) 50%, rgba(147, 51, 234, 0.06) 100%)",
          border: "1px solid rgba(16, 107, 163, 0.25)",
          boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          display: "flex",
          flexDirection: "column",
          gap: 14,
          boxSizing: "border-box",
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
          <div style={{ width: 38, height: 38, borderRadius: 10, backgroundColor: "rgba(16, 107, 163, 0.15)", color: "var(--fb-primary)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <Sparkles style={{ width: 20, height: 20 }} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--fb-text-primary)", margin: 0 }}>
                AI-Assisted Resolution from Reference Topic / Course Content
              </h3>
              {isIrrelevantOrIncorrect && (
                <span style={{ fontSize: 10, textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em", padding: "2px 8px", borderRadius: 9999, backgroundColor: "var(--fb-primary)", color: "#ffffff" }}>
                  Recommended for {item.feedback_type?.replace(/_/g, " ")}
                </span>
              )}
            </div>
            <p style={{ fontSize: 12, color: "var(--fb-text-secondary)", margin: "4px 0 0 0", lineHeight: 1.4 }}>
              Instead of editing the entire answer manually, provide the reference topic from company SMS documents or course curriculum. Dolphin AI will synthesize an authoritative, structured response for your review.
            </p>
          </div>
        </div>

        {/* Input Fields Row */}
        <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
          {/* Reference Topic Input with Autocomplete Dropdown */}
          <div style={{ flex: "1 1 360px", position: "relative" }} ref={dropdownRef}>
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600, color: "var(--fb-text-primary)", marginBottom: 6 }}>
              <BookOpen style={{ width: 14, height: 14, color: "var(--fb-primary)" }} />
              <span>Reference Topic / SOP / Course Content Title:</span>
              <span style={{ color: "var(--fb-danger)" }}>*</span>
            </label>
            <div style={{ position: "relative", width: "100%" }}>
              <Search style={{ width: 16, height: 16, position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--fb-text-secondary)", pointerEvents: "none" }} />
              <input
                type="text"
                value={topic}
                onChange={(e) => {
                  setTopic(e.target.value);
                  setShowSuggestionsDropdown(true);
                }}
                onFocus={() => setShowSuggestionsDropdown(true)}
                placeholder="e.g. Enclosed Space Entry Safety, Hot Work Procedures, STCW Navigation..."
                disabled={regenerating || submitting}
                style={{
                  width: "100%",
                  paddingLeft: 36,
                  paddingRight: searchLoading ? 36 : 14,
                  paddingTop: 10,
                  paddingBottom: 10,
                  fontSize: 12,
                  fontWeight: 500,
                  borderRadius: 10,
                  backgroundColor: "var(--fb-bg-paper)",
                  border: "1px solid #cbd5e1",
                  color: "var(--fb-text-primary)",
                  outline: "none",
                  boxSizing: "border-box",
                }}
              />
              {searchLoading && (
                <Loader2 style={{ width: 16, height: 16, position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)", color: "var(--fb-primary)", animation: "spin 1s linear infinite" }} />
              )}
            </div>

            {/* Suggestions Dropdown */}
            {showSuggestionsDropdown && topicSuggestions.length > 0 && (
              <div style={{ position: "absolute", left: 0, right: 0, top: "100%", marginTop: 6, maxHeight: 220, overflowY: "auto", borderRadius: 12, backgroundColor: "var(--fb-bg-paper)", border: "1px solid var(--fb-border)", boxShadow: "0 10px 15px -3px rgba(0,0,0,0.1)", zIndex: 30, padding: 4 }}>
                <div style={{ padding: "6px 10px", fontSize: 11, fontWeight: 700, color: "var(--fb-text-secondary)", backgroundColor: "var(--fb-bg-default)", borderRadius: 6, marginBottom: 4 }}>
                  Matching Course & Document Topics:
                </div>
                {topicSuggestions.map((sug, sIdx) => (
                  <button
                    key={sIdx}
                    type="button"
                    onClick={() => handleSelectTopicSuggestion(sug.title)}
                    style={{ width: "100%", textAlign: "left", padding: "8px 10px", border: "none", backgroundColor: "transparent", borderRadius: 8, cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = "rgba(16,107,163,0.08)"}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = "transparent"}
                  >
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--fb-text-primary)" }}>{sug.title}</div>
                      <div style={{ fontSize: 11, color: "var(--fb-text-secondary)" }}>{sug.subtitle}</div>
                    </div>
                    <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, backgroundColor: "var(--fb-bg-default)", color: "var(--fb-text-secondary)" }}>
                      {sug.source}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Generate Button */}
          <button
            type="button"
            onClick={handleRegenerate}
            disabled={regenerating || submitting || !topic.trim()}
            style={{
              flex: "0 0 210px",
              height: 40,
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              padding: "0 16px",
              borderRadius: 10,
              backgroundColor: "var(--fb-primary)",
              color: "#ffffff",
              fontSize: 12,
              fontWeight: 700,
              border: "none",
              cursor: (regenerating || submitting || !topic.trim()) ? "not-allowed" : "pointer",
              opacity: (regenerating || submitting || !topic.trim()) ? 0.6 : 1,
              boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
            }}
          >
            {regenerating ? (
              <Loader2 style={{ width: 16, height: 16, animation: "spin 1s linear infinite" }} />
            ) : (
              <Sparkles style={{ width: 16, height: 16, color: "#fef08a" }} />
            )}
            <span>{regenerating ? "Synthesizing AI..." : "Generate AI Response"}</span>
          </button>
        </div>

        {/* Quick Suggestion Pills */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: "var(--fb-text-secondary)" }}>
            Quick Topics:
          </span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {SUGGESTED_QUICK_TOPICS.map((qTopic, qIdx) => (
              <button
                key={qIdx}
                type="button"
                onClick={() => setTopic(qTopic)}
                style={{
                  fontSize: 11,
                  padding: "4px 10px",
                  borderRadius: 8,
                  border: "1px solid #cbd5e1",
                  backgroundColor: "var(--fb-bg-paper)",
                  color: "var(--fb-text-primary)",
                  cursor: "pointer",
                  fontWeight: 500,
                  transition: "all 0.2s ease",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "var(--fb-primary)";
                  e.currentTarget.style.color = "var(--fb-primary)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "#cbd5e1";
                  e.currentTarget.style.color = "var(--fb-text-primary)";
                }}
              >
                {qTopic}
              </button>
            ))}
          </div>
        </div>

        {/* Collapsible Advanced Reference & Guidelines Box */}
        <div style={{ paddingTop: 4 }}>
          <button
            type="button"
            onClick={() => setShowAdvancedInputs(!showAdvancedInputs)}
            style={{ display: "inline-flex", alignItems: "center", gap: 4, background: "none", border: "none", color: "var(--fb-primary)", fontSize: 12, fontWeight: 600, cursor: "pointer", padding: 0 }}
          >
            {showAdvancedInputs ? <ChevronUp style={{ width: 14, height: 14 }} /> : <ChevronDown style={{ width: 14, height: 14 }} />}
            <span>{showAdvancedInputs ? "Hide Optional Reference Excerpts & Instructions" : "+ Add Reference Manual Text or Specific Instructions (Optional)"}</span>
          </button>

          {showAdvancedInputs && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 12, paddingTop: 12, borderTop: "1px solid rgba(16,107,163,0.15)" }}>
              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--fb-text-primary)", marginBottom: 6 }}>
                  Reference Manual Excerpt / Guidelines (Optional):
                </label>
                <textarea
                  rows={3}
                  value={referenceText}
                  onChange={(e) => setReferenceText(e.target.value)}
                  placeholder="Paste relevant SMS section clauses, checklist requirements, or limits..."
                  style={{ width: "100%", padding: 10, fontSize: 12, borderRadius: 10, border: "1px solid #cbd5e1", backgroundColor: "var(--fb-bg-paper)", outline: "none", boxSizing: "border-box", fontFamily: "monospace", resize: "none" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--fb-text-primary)", marginBottom: 6 }}>
                  Additional Reviewer Instructions (Optional):
                </label>
                <textarea
                  rows={3}
                  value={reviewerInstructions}
                  onChange={(e) => setReviewerInstructions(e.target.value)}
                  placeholder="e.g. 'Format with a step-by-step table and highlight required PPE'..."
                  style={{ width: "100%", padding: 10, fontSize: 12, borderRadius: 10, border: "1px solid #cbd5e1", backgroundColor: "var(--fb-bg-paper)", outline: "none", boxSizing: "border-box", resize: "none" }}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 3. Main Split View: 2 Equal Columns (Left: Context & Original, Right: Preferred Editor) */}
      <div className="fb-detail-2col" style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 20, width: "100%", boxSizing: "border-box" }}>
        {/* LEFT COLUMN: Original Query & Response Details */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20, width: "100%" }}>
          {/* 1. Original User Question Card */}
          <div className="fb-card" style={{ padding: 20, borderRadius: 16, backgroundColor: "var(--fb-bg-paper)", border: "1px solid var(--fb-border)", boxShadow: "0 1px 3px rgba(0,0,0,0.05)", margin: 0 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <HelpCircle style={{ width: 16, height: 16, color: "var(--fb-primary)" }} />
                <h4 style={{ fontSize: 14, fontWeight: 700, color: "var(--fb-text-primary)", margin: 0 }}>
                  Original User Question / RAG Trigger
                </h4>
              </div>
              <button
                type="button"
                onClick={() => setIsEditingQuestion(!isEditingQuestion)}
                style={{ fontSize: 11, fontWeight: 600, color: "var(--fb-primary)", background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}
              >
                <FileEdit style={{ width: 12, height: 12 }} />
                <span>{isEditingQuestion ? "Cancel Edit" : "Edit Trigger Question"}</span>
              </button>
            </div>

            {isEditingQuestion ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <input
                  type="text"
                  value={editQuestion}
                  onChange={(e) => setEditQuestion(e.target.value)}
                  placeholder="Enter refined question trigger for RAG matching..."
                  style={{ width: "100%", padding: 10, fontSize: 12, borderRadius: 10, border: "1px solid var(--fb-primary)", outline: "none", boxSizing: "border-box", fontWeight: 600 }}
                />
                <span style={{ fontSize: 11, color: "var(--fb-text-secondary)" }}>
                  💡 This query text will be indexed in 3072-dimensional vector memory to trigger this approved response.
                </span>
              </div>
            ) : (
              <div style={{ padding: 12, borderRadius: 10, backgroundColor: "rgba(16, 107, 163, 0.06)", borderLeft: "4px solid var(--fb-primary)", color: "var(--fb-text-primary)", fontSize: 13, fontWeight: 600, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span>{editQuestion || item.question}</span>
                {editQuestion !== item.question && (
                  <span style={{ fontSize: 10, backgroundColor: "rgba(16, 107, 163, 0.15)", color: "var(--fb-primary)", fontWeight: 700, padding: "2px 8px", borderRadius: 9999 }}>
                    Customized
                  </span>
                )}
              </div>
            )}
          </div>

          {/* 2. User Feedback & Metadata Card */}
          <div className="fb-card" style={{ padding: 20, borderRadius: 16, backgroundColor: "var(--fb-bg-paper)", border: "1px solid var(--fb-border)", boxShadow: "0 1px 3px rgba(0,0,0,0.05)", margin: 0 }}>
            <h4 style={{ fontSize: 14, fontWeight: 700, color: "var(--fb-text-primary)", margin: "0 0 14px 0" }}>
              User Feedback & Context
            </h4>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 14, fontSize: 12 }}>
              <div>
                <span style={{ color: "var(--fb-text-secondary)", display: "block", marginBottom: 4, fontSize: 11, fontWeight: 600, textTransform: "uppercase" }}>Feedback Category:</span>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    padding: "2px 10px",
                    borderRadius: 9999,
                    fontSize: 11,
                    fontWeight: 700,
                    backgroundColor: item.feedback_type === "positive" ? "rgba(22, 163, 74, 0.12)" : "rgba(220, 38, 38, 0.12)",
                    color: item.feedback_type === "positive" ? "var(--fb-success)" : "var(--fb-danger)",
                    textTransform: "capitalize",
                  }}
                >
                  {item.feedback_type?.replace(/_/g, " ")}
                </span>
              </div>

              <div>
                <span style={{ color: "var(--fb-text-secondary)", display: "block", marginBottom: 4, fontSize: 11, fontWeight: 600, textTransform: "uppercase" }}>Submitted At:</span>
                <span style={{ fontWeight: 600, color: "var(--fb-text-primary)" }}>
                  {item.created_at ? new Date(item.created_at).toLocaleString() : "-"}
                </span>
              </div>

              {item.feedback_comment && (
                <div style={{ gridColumn: "span 2" }}>
                  <span style={{ color: "var(--fb-text-secondary)", display: "block", marginBottom: 4, fontSize: 11, fontWeight: 600, textTransform: "uppercase" }}>User Comment:</span>
                  <div style={{ padding: 10, borderRadius: 10, backgroundColor: "var(--fb-bg-default)", fontStyle: "italic", color: "var(--fb-text-primary)", border: "1px solid var(--fb-border)" }}>
                    "{item.feedback_comment}"
                  </div>
                </div>
              )}

              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--fb-text-secondary)", marginBottom: 2, fontSize: 11, fontWeight: 600, textTransform: "uppercase" }}>
                  <Building2 style={{ width: 14, height: 14 }} />
                  <span>Company:</span>
                </div>
                <span style={{ fontWeight: 700, color: "var(--fb-text-primary)" }}>
                  {item.company_id || "Global"}
                </span>
              </div>

              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--fb-text-secondary)", marginBottom: 2, fontSize: 11, fontWeight: 600, textTransform: "uppercase" }}>
                  <Ship style={{ width: 14, height: 14 }} />
                  <span>Ship Type:</span>
                </div>
                <span style={{ fontWeight: 700, color: "var(--fb-text-primary)" }}>
                  {item.ship_type || "General"}
                </span>
              </div>

              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--fb-text-secondary)", marginBottom: 2, fontSize: 11, fontWeight: 600, textTransform: "uppercase" }}>
                  <User style={{ width: 14, height: 14 }} />
                  <span>User ID:</span>
                </div>
                <span style={{ fontFamily: "monospace", color: "var(--fb-text-primary)", fontSize: 11 }}>
                  {item.user_id || "anonymous"}
                </span>
              </div>

              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--fb-text-secondary)", marginBottom: 2, fontSize: 11, fontWeight: 600, textTransform: "uppercase" }}>
                  <FileCode style={{ width: 14, height: 14 }} />
                  <span>Session:</span>
                </div>
                <span style={{ fontFamily: "monospace", color: "var(--fb-text-primary)", fontSize: 11 }}>
                  {item.conversation_id ? item.conversation_id.slice(0, 12) + "..." : "-"}
                </span>
              </div>
            </div>
          </div>

          {/* 3. Exact Original Dolphin AI Response Card */}
          <div className="fb-card" style={{ padding: 20, borderRadius: 16, backgroundColor: "var(--fb-bg-paper)", border: "1px solid var(--fb-border)", boxShadow: "0 1px 3px rgba(0,0,0,0.05)", margin: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <Bot style={{ width: 16, height: 16, color: "var(--fb-primary)" }} />
              <h4 style={{ fontSize: 14, fontWeight: 700, color: "var(--fb-text-primary)", margin: 0 }}>
                Exact Original Dolphin AI Response (Flagged)
              </h4>
            </div>
            <div
              style={{ padding: 14, borderRadius: 12, backgroundColor: "var(--fb-bg-default)", border: "1px solid var(--fb-border)", maxHeight: 320, overflowY: "auto", fontSize: 12, color: "var(--fb-text-primary)", lineHeight: 1.6 }}
              dangerouslySetInnerHTML={{
                __html: sanitizeMarkdown(item.original_response),
              }}
            />
          </div>
        </div>

        {/* RIGHT COLUMN: Preferred / Corrected Response Editor & Preview */}
        <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
          <div className="fb-card" style={{ padding: 20, borderRadius: 16, backgroundColor: "var(--fb-bg-paper)", border: "1px solid var(--fb-border)", boxShadow: "0 1px 3px rgba(0,0,0,0.05)", margin: 0, display: "flex", flexDirection: "column", height: "100%", boxSizing: "border-box" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <FileEdit style={{ width: 16, height: 16, color: "var(--fb-primary)" }} />
                <h4 style={{ fontSize: 14, fontWeight: 700, color: "var(--fb-text-primary)", margin: 0 }}>
                  Preferred / Corrected Response
                </h4>
                {lastGeneratedTopic && (
                  <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 9999, backgroundColor: "rgba(22, 163, 74, 0.12)", color: "var(--fb-success)", display: "inline-flex", alignItems: "center", gap: 4 }}>
                    <Sparkles style={{ width: 12, height: 12 }} />
                    Generated
                  </span>
                )}
              </div>

              {/* Tab switch */}
              <div style={{ display: "flex", alignItems: "center", backgroundColor: "var(--fb-bg-default)", borderRadius: 10, padding: 3 }}>
                <button
                  type="button"
                  onClick={() => setEditorTab(0)}
                  style={{
                    padding: "4px 12px",
                    borderRadius: 8,
                    fontSize: 11,
                    fontWeight: 700,
                    border: "none",
                    cursor: "pointer",
                    backgroundColor: editorTab === 0 ? "var(--fb-bg-paper)" : "transparent",
                    color: editorTab === 0 ? "var(--fb-primary)" : "var(--fb-text-secondary)",
                    boxShadow: editorTab === 0 ? "0 1px 2px rgba(0,0,0,0.08)" : "none",
                    transition: "all 0.2s ease",
                  }}
                >
                  Edit Response
                </button>
                <button
                  type="button"
                  onClick={() => setEditorTab(1)}
                  style={{
                    padding: "4px 12px",
                    borderRadius: 8,
                    fontSize: 11,
                    fontWeight: 700,
                    border: "none",
                    cursor: "pointer",
                    backgroundColor: editorTab === 1 ? "var(--fb-bg-paper)" : "transparent",
                    color: editorTab === 1 ? "var(--fb-primary)" : "var(--fb-text-secondary)",
                    boxShadow: editorTab === 1 ? "0 1px 2px rgba(0,0,0,0.08)" : "none",
                    transition: "all 0.2s ease",
                  }}
                >
                  Preview Markdown
                </button>
              </div>
            </div>

            <p style={{ fontSize: 12, color: "var(--fb-text-secondary)", margin: "0 0 12px 0", lineHeight: 1.4 }}>
              Review or adjust the authoritative response below. Once approved, this response is saved to vector memory to instantly correct future queries, and added to the DPO dataset for background training.
            </p>

            {editorTab === 0 ? (
              <textarea
                rows={14}
                placeholder="Enter or refine the preferred authoritative response..."
                value={preferredResponse}
                onChange={(e) => setPreferredResponse(e.target.value)}
                disabled={submitting || regenerating}
                style={{
                  width: "100%",
                  flex: 1,
                  minHeight: 280,
                  padding: 14,
                  fontSize: 12,
                  borderRadius: 12,
                  backgroundColor: "var(--fb-bg-default)",
                  border: "1px solid #cbd5e1",
                  color: "var(--fb-text-primary)",
                  fontFamily: "monospace",
                  lineHeight: 1.5,
                  outline: "none",
                  boxSizing: "border-box",
                  marginBottom: 14,
                  resize: "vertical",
                }}
              />
            ) : (
              <div
                style={{
                  flex: 1,
                  minHeight: 280,
                  maxHeight: 400,
                  overflowY: "auto",
                  padding: 14,
                  marginBottom: 14,
                  borderRadius: 12,
                  backgroundColor: "var(--fb-bg-default)",
                  border: "1px solid var(--fb-border)",
                  fontSize: 12,
                  color: "var(--fb-text-primary)",
                  lineHeight: 1.6,
                }}
                dangerouslySetInnerHTML={{
                  __html: sanitizeMarkdown(preferredResponse || "*No response text entered.*"),
                }}
              />
            )}

            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--fb-text-primary)", marginBottom: 6 }}>
              Admin Note / Review Comment (Optional):
            </label>
            <input
              type="text"
              placeholder="Internal notes regarding this review (e.g. 'Verified against SMS Section 4.2')..."
              value={adminComment}
              onChange={(e) => setAdminComment(e.target.value)}
              disabled={submitting || regenerating}
              style={{
                width: "100%",
                padding: "8px 12px",
                fontSize: 12,
                borderRadius: 10,
                backgroundColor: "var(--fb-bg-default)",
                border: "1px solid #cbd5e1",
                color: "var(--fb-text-primary)",
                outline: "none",
                boxSizing: "border-box",
                marginBottom: 18,
              }}
            />

            <hr style={{ border: "none", borderTop: "1px solid var(--fb-border)", margin: "auto 0 16px 0" }} />

            {/* Action Buttons */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 12 }}>
              <button
                type="button"
                onClick={() => setRejectModalOpen(true)}
                disabled={submitting || regenerating}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "8px 16px",
                  borderRadius: 10,
                  border: "1px solid rgba(220, 38, 38, 0.3)",
                  backgroundColor: "transparent",
                  color: "var(--fb-danger)",
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: (submitting || regenerating) ? "not-allowed" : "pointer",
                  transition: "all 0.2s ease",
                }}
              >
                <XCircle style={{ width: 16, height: 16 }} />
                <span>Reject Feedback</span>
              </button>

              <button
                type="button"
                onClick={handleApprove}
                disabled={submitting || regenerating || !preferredResponse.trim()}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "8px 20px",
                  borderRadius: 10,
                  backgroundColor: "var(--fb-primary)",
                  color: "#ffffff",
                  fontSize: 12,
                  fontWeight: 700,
                  border: "none",
                  cursor: (submitting || regenerating || !preferredResponse.trim()) ? "not-allowed" : "pointer",
                  opacity: (submitting || regenerating || !preferredResponse.trim()) ? 0.6 : 1,
                  boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
                  transition: "all 0.2s ease",
                }}
              >
                {submitting ? (
                  <Loader2 style={{ width: 16, height: 16, animation: "spin 1s linear infinite" }} />
                ) : (
                  <CheckCircle2 style={{ width: 16, height: 16 }} />
                )}
                <span>{submitting ? "Approving..." : "Agree & Approve"}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Reject Modal */}
      <RejectReasonModal
        open={rejectModalOpen}
        onClose={() => setRejectModalOpen(false)}
        onConfirmReject={handleConfirmReject}
        loading={submitting}
      />
    </div>
  );
};

export default React.memo(PendingDetailView);
