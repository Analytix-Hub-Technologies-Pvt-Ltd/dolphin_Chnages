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
  FileText,
  Search,
  Check,
  RefreshCw,
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
      setPreferredResponse(item.preferred_response || item.original_response || "");
      setAdminComment(item.admin_comment || "");
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
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!item) {
    return (
      <div className="p-8 text-center space-y-4">
        <h3 className="text-base font-bold text-text-primary">
          Feedback record not found.
        </h3>
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl bg-primary text-white"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to List
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

      if (result && result.generated_response) {
        setPreferredResponse(result.generated_response);
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
    <div className="w-full pb-10 space-y-5">
      {/* Top Header with Back Navigation */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-border-theme text-xs font-semibold text-text-primary hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors shadow-2xs"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Pending List
        </button>

        <div className="flex items-center gap-2">
          <span className="font-mono text-xs px-2.5 py-1 rounded-lg border border-border-theme text-text-secondary bg-bg-paper">
            ID: {item.feedback_id}
          </span>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-amber-500/15 text-amber-600 dark:text-amber-400">
            Pending Admin Review
          </span>
        </div>
      </div>

      {errorMessage && (
        <div className="flex items-center gap-2 p-3.5 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/50 text-red-600 dark:text-red-400 text-xs font-medium">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {successBanner && (
        <div className="flex items-center gap-2 p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/50 text-emerald-700 dark:text-emerald-300 text-xs font-medium">
          <Check className="w-4 h-4 flex-shrink-0" />
          <span>{successBanner}</span>
        </div>
      )}

      {/* TOP FEATURE: AI-Assisted Response Generator from Reference Topic */}
      <div className="p-5 rounded-2xl bg-gradient-to-br from-sky-50/70 via-indigo-50/40 to-purple-50/50 dark:from-sky-950/30 dark:via-indigo-950/20 dark:to-purple-950/30 border border-sky-200/80 dark:border-sky-800/40 shadow-sm space-y-4">
        <div className="flex items-start justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-primary/10 text-primary">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-text-primary flex items-center gap-2">
                AI-Assisted Resolution from Reference Topic / Course Content
                {isIrrelevantOrIncorrect && (
                  <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-primary text-white">
                    Recommended for {item.feedback_type.replace(/_/g, " ")}
                  </span>
                )}
              </h3>
              <p className="text-xs text-text-secondary mt-0.5">
                Instead of editing the entire answer manually, provide the reference topic from company SMS documents or course curriculum. Dolphin AI will synthesize an authoritative, structured response for your review.
              </p>
            </div>
          </div>
        </div>

        {/* Input Fields */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3.5 pt-1">
          {/* Reference Topic Input with Autocomplete Dropdown */}
          <div className="md:col-span-8 relative" ref={dropdownRef}>
            <label className="block text-xs font-semibold text-text-primary mb-1.5 flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5 text-primary" />
              <span>Reference Topic / SOP / Course Content Title:</span>
              <span className="text-red-500">*</span>
            </label>
            <div className="relative">
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
                className="w-full pl-9 pr-8 py-2.5 text-xs rounded-xl bg-bg-paper border border-border-theme focus:ring-2 focus:ring-primary/20 focus:border-primary focus:outline-hidden transition-all shadow-2xs font-medium"
              />
              <Search className="w-4 h-4 text-text-secondary absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              {searchLoading && (
                <Loader2 className="w-3.5 h-3.5 text-primary animate-spin absolute right-3 top-1/2 -translate-y-1/2" />
              )}
            </div>

            {/* Suggestions Dropdown */}
            {showSuggestionsDropdown && topicSuggestions.length > 0 && (
              <div className="absolute z-20 left-0 right-0 mt-1.5 max-h-56 overflow-y-auto rounded-xl bg-bg-paper border border-border-theme shadow-lg py-1 text-xs divide-y divide-border-theme/40">
                <div className="px-3 py-1 text-[11px] font-semibold text-text-secondary bg-slate-50 dark:bg-slate-800/40">
                  Matching Course & Document Topics:
                </div>
                {topicSuggestions.map((sug, sIdx) => (
                  <button
                    key={sIdx}
                    type="button"
                    onClick={() => handleSelectTopicSuggestion(sug.title)}
                    className="w-full text-left px-3.5 py-2 hover:bg-primary/10 transition-colors flex items-center justify-between gap-2"
                  >
                    <div>
                      <div className="font-semibold text-text-primary">{sug.title}</div>
                      <div className="text-[11px] text-text-secondary">{sug.subtitle}</div>
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-text-secondary font-medium">
                      {sug.source}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Generate Button */}
          <div className="md:col-span-4 flex items-end">
            <button
              type="button"
              onClick={handleRegenerate}
              disabled={regenerating || submitting || !topic.trim()}
              className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-primary hover:bg-primary-hover text-white text-xs font-bold shadow-sm transition-all disabled:opacity-50 h-[38px]"
            >
              {regenerating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4 text-amber-300" />
              )}
              {regenerating ? "Synthesizing AI Response..." : "Generate AI Response"}
            </button>
          </div>
        </div>

        {/* Quick Suggestion Pills */}
        <div className="space-y-1.5">
          <span className="text-[11px] font-semibold text-text-secondary">
            Quick Topics:
          </span>
          <div className="flex flex-wrap gap-1.5">
            {SUGGESTED_QUICK_TOPICS.map((qTopic, qIdx) => (
              <button
                key={qIdx}
                type="button"
                onClick={() => setTopic(qTopic)}
                className="text-[11px] px-2.5 py-1 rounded-lg border border-border-theme bg-bg-paper hover:border-primary hover:text-primary transition-all font-medium"
              >
                {qTopic}
              </button>
            ))}
          </div>
        </div>

        {/* Collapsible Advanced Reference & Guidelines Box */}
        <div className="pt-1">
          <button
            type="button"
            onClick={() => setShowAdvancedInputs(!showAdvancedInputs)}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline"
          >
            {showAdvancedInputs ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            <span>{showAdvancedInputs ? "Hide Optional Reference Excerpts & Instructions" : "+ Add Reference Manual Text or Specific Instructions (Optional)"}</span>
          </button>

          {showAdvancedInputs && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 mt-3 pt-3 border-t border-border-theme/60">
              <div>
                <label className="block text-xs font-semibold text-text-primary mb-1">
                  Reference Manual Excerpt / Guidelines (Optional):
                </label>
                <textarea
                  rows={3}
                  value={referenceText}
                  onChange={(e) => setReferenceText(e.target.value)}
                  placeholder="Paste relevant SMS section clauses, checklist requirements, or limits..."
                  className="w-full p-2.5 text-xs rounded-xl bg-bg-paper border border-border-theme focus:ring-1 focus:ring-primary focus:outline-hidden font-mono resize-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-primary mb-1">
                  Additional Reviewer Instructions (Optional):
                </label>
                <textarea
                  rows={3}
                  value={reviewerInstructions}
                  onChange={(e) => setReviewerInstructions(e.target.value)}
                  placeholder="e.g. 'Format with a step-by-step table and highlight required PPE'..."
                  className="w-full p-2.5 text-xs rounded-xl bg-bg-paper border border-border-theme focus:ring-1 focus:ring-primary focus:outline-hidden resize-none"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* LEFT COLUMN: Original Query & Response Details */}
        <div className="space-y-5">
          {/* 1. Original User Question Card */}
          <div className="p-5 rounded-2xl bg-bg-paper border border-border-theme shadow-sm">
            <div className="flex items-center justify-between gap-2 mb-3">
              <div className="flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-primary" />
                <h4 className="font-bold text-sm text-text-primary">
                  Original User Question / RAG Trigger
                </h4>
              </div>
              <button
                type="button"
                onClick={() => setIsEditingQuestion(!isEditingQuestion)}
                className="text-[11px] font-semibold text-primary hover:underline flex items-center gap-1 cursor-pointer"
              >
                <FileEdit className="w-3 h-3" />
                <span>{isEditingQuestion ? "Cancel Edit" : "Edit Trigger Question"}</span>
              </button>
            </div>
            {isEditingQuestion ? (
              <div className="space-y-2">
                <input
                  type="text"
                  value={editQuestion}
                  onChange={(e) => setEditQuestion(e.target.value)}
                  placeholder="Enter refined question trigger for RAG matching..."
                  className="w-full p-2.5 text-xs rounded-xl bg-bg-paper border border-primary focus:ring-1 focus:ring-primary focus:outline-hidden font-medium text-text-primary"
                />
                <span className="text-[11px] text-text-secondary block">
                  💡 This query text will be indexed in 3072-dimensional vector memory to trigger this approved response.
                </span>
              </div>
            ) : (
              <div className="p-3.5 rounded-xl bg-sky-50/60 dark:bg-sky-950/20 text-text-primary font-medium text-xs border-l-4 border-primary flex items-center justify-between">
                <span>{editQuestion || item.question}</span>
                {editQuestion !== item.question && (
                  <span className="text-[10px] bg-primary/10 text-primary font-bold px-2 py-0.5 rounded-full">
                    Customized
                  </span>
                )}
              </div>
            )}
          </div>

          {/* 2. User Feedback & Metadata Card */}
          <div className="p-5 rounded-2xl bg-bg-paper border border-border-theme shadow-sm">
            <h4 className="font-bold text-sm text-text-primary mb-3">
              User Feedback & Context
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
              <div className="col-span-2">
                <span className="text-text-secondary block mb-1">Feedback Category:</span>
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded-full font-semibold capitalize ${
                    item.feedback_type === "positive"
                      ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                      : "bg-red-500/15 text-red-600 dark:text-red-400"
                  }`}
                >
                  {item.feedback_type?.replace(/_/g, " ")}
                </span>
              </div>

              <div className="col-span-2">
                <span className="text-text-secondary block mb-1">Submitted At:</span>
                <span className="font-medium text-text-primary">
                  {item.created_at ? new Date(item.created_at).toLocaleString() : "-"}
                </span>
              </div>

              {item.feedback_comment && (
                <div className="col-span-2 sm:col-span-4">
                  <span className="text-text-secondary block mb-1">User Comment:</span>
                  <div className="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/60 italic text-text-primary">
                    "{item.feedback_comment}"
                  </div>
                </div>
              )}

              <div>
                <div className="flex items-center gap-1 text-text-secondary mb-0.5">
                  <Building2 className="w-3.5 h-3.5" />
                  <span>Company:</span>
                </div>
                <span className="font-semibold text-text-primary">
                  {item.company_id || "Global"}
                </span>
              </div>

              <div>
                <div className="flex items-center gap-1 text-text-secondary mb-0.5">
                  <Ship className="w-3.5 h-3.5" />
                  <span>Ship Type:</span>
                </div>
                <span className="font-semibold text-text-primary">
                  {item.ship_type || "N/A"}
                </span>
              </div>

              <div>
                <div className="flex items-center gap-1 text-text-secondary mb-0.5">
                  <User className="w-3.5 h-3.5" />
                  <span>User ID:</span>
                </div>
                <span className="font-mono text-text-primary text-[11px] truncate block">
                  {item.user_id || "anonymous"}
                </span>
              </div>

              <div>
                <div className="flex items-center gap-1 text-text-secondary mb-0.5">
                  <FileCode className="w-3.5 h-3.5" />
                  <span>Session:</span>
                </div>
                <span className="font-mono text-text-primary text-[11px]">
                  {item.conversation_id ? item.conversation_id.slice(0, 8) + "..." : "-"}
                </span>
              </div>
            </div>
          </div>

          {/* 3. Exact Original Dolphin AI Response Card */}
          <div className="p-5 rounded-2xl bg-bg-paper border border-border-theme shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <Bot className="w-4 h-4 text-primary" />
              <h4 className="font-bold text-sm text-text-primary">
                Exact Original Dolphin AI Response (Flagged)
              </h4>
            </div>
            <div
              className="p-3.5 rounded-xl bg-bg-default border border-border-theme max-h-[340px] overflow-y-auto text-xs text-text-primary prose dark:prose-invert max-w-none"
              dangerouslySetInnerHTML={{
                __html: sanitizeMarkdown(item.original_response),
              }}
            />
          </div>
        </div>

        {/* RIGHT COLUMN: Preferred / Corrected Response Editor & Preview */}
        <div className="flex flex-col">
          <div className="p-5 rounded-2xl bg-bg-paper border border-border-theme shadow-sm flex flex-col h-full">
            <div className="flex justify-between items-center mb-2 flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <FileEdit className="w-4 h-4 text-primary" />
                <h4 className="font-bold text-sm text-text-primary">
                  Preferred / Corrected Response
                </h4>
                {lastGeneratedTopic && (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                    <Sparkles className="w-3 h-3" />
                    Generated via Topic
                  </span>
                )}
              </div>
              <div className="flex items-center bg-slate-100 dark:bg-slate-800 rounded-lg p-0.5 text-xs">
                <button
                  type="button"
                  onClick={() => setEditorTab(0)}
                  className={`px-3 py-1 rounded-md font-semibold transition-all ${
                    editorTab === 0
                      ? "bg-bg-paper text-primary shadow-2xs"
                      : "text-text-secondary hover:text-text-primary"
                  }`}
                >
                  Edit Response
                </button>
                <button
                  type="button"
                  onClick={() => setEditorTab(1)}
                  className={`px-3 py-1 rounded-md font-semibold transition-all ${
                    editorTab === 1
                      ? "bg-bg-paper text-primary shadow-2xs"
                      : "text-text-secondary hover:text-text-primary"
                  }`}
                >
                  Preview Markdown
                </button>
              </div>
            </div>

            <p className="text-xs text-text-secondary mb-3">
              Review or adjust the authoritative response below. Once approved, this response is saved to vector memory to instantly correct future queries, and added to the DPO dataset for background training.
            </p>

            {editorTab === 0 ? (
              <textarea
                rows={14}
                placeholder="Enter or refine the preferred authoritative response..."
                value={preferredResponse}
                onChange={(e) => setPreferredResponse(e.target.value)}
                disabled={submitting || regenerating}
                className="w-full p-3.5 text-xs rounded-xl bg-bg-default border border-border-theme focus:ring-1 focus:ring-primary focus:outline-hidden font-mono flex-1 mb-4 resize-none transition-all"
              />
            ) : (
              <div
                className="flex-1 min-h-[300px] max-h-[420px] overflow-y-auto p-4 mb-4 rounded-xl bg-bg-default border border-border-theme text-xs text-text-primary prose dark:prose-invert max-w-none shadow-inner"
                dangerouslySetInnerHTML={{
                  __html: sanitizeMarkdown(preferredResponse || "*No response text entered.*"),
                }}
              />
            )}

            <label className="block text-xs font-semibold text-text-primary mb-1">
              Admin Note / Review Comment (Optional):
            </label>
            <input
              type="text"
              placeholder="Internal notes regarding this review (e.g. 'Verified against SMS Section 4.2')..."
              value={adminComment}
              onChange={(e) => setAdminComment(e.target.value)}
              disabled={submitting || regenerating}
              className="w-full px-3 py-2 text-xs rounded-xl bg-bg-default border border-border-theme focus:ring-1 focus:ring-primary focus:outline-hidden mb-5 transition-all"
            />

            <hr className="border-border-theme mb-4 mt-auto" />

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setRejectModalOpen(true)}
                disabled={submitting || regenerating}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-red-500/30 text-red-600 dark:text-red-400 hover:bg-red-500/10 text-xs font-semibold transition-colors disabled:opacity-50"
              >
                <XCircle className="w-4 h-4" />
                Reject Feedback
              </button>

              <button
                type="button"
                onClick={handleApprove}
                disabled={submitting || regenerating || !preferredResponse.trim()}
                className="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl bg-primary hover:bg-primary-hover text-white text-xs font-bold shadow-xs transition-colors disabled:opacity-50"
              >
                {submitting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="w-4 h-4" />
                )}
                {submitting ? "Approving..." : "Agree & Approve"}
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
