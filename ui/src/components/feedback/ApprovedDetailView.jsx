import React, { useState, useEffect } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  HelpCircle,
  Bot,
  ShieldCheck,
  Database,
  Cpu,
  Building2,
  Ship,
  User,
  Loader2,
  FileEdit,
  Save,
  Trash2,
  Check,
  AlertTriangle,
  Eye,
  Edit3,
} from "lucide-react";

import { sanitizeMarkdown } from "../chat/ChatWindow";
import { updateApprovedFeedback, deleteApprovedFeedback, formatErrorMessage } from "../../api/feedbackApi";

const ApprovedDetailView = ({
  item,
  loading = false,
  onBack,
  onActionComplete,
  reviewerId = "admin",
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [preferredResponse, setPreferredResponse] = useState("");
  const [question, setQuestion] = useState("");
  const [adminComment, setAdminComment] = useState("");
  const [editorTab, setEditorTab] = useState(0); // 0: Edit, 1: Preview
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  useEffect(() => {
    if (item) {
      setPreferredResponse(item.preferred_response || item.original_response || "");
      setQuestion(item.question || "");
      setAdminComment(item.admin_comment || "");
      setIsEditing(false);
      setErrorMsg("");
      setSuccessMsg("");
    }
  }, [item]);

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
          Approved record not found.
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

  const handleSaveUpdate = async () => {
    if (!preferredResponse.trim()) {
      setErrorMsg("Preferred response cannot be empty.");
      return;
    }
    try {
      setSaving(true);
      setErrorMsg("");
      setSuccessMsg("");
      await updateApprovedFeedback(item.feedback_id, {
        preferredResponse: preferredResponse.trim(),
        question: question.trim() || item.question,
        reviewerId: reviewerId || "admin",
        adminComment: adminComment.trim() || null,
      });
      setSaving(false);
      setIsEditing(false);
      setSuccessMsg("✨ Approved response updated and vector memory refreshed successfully!");
      if (onActionComplete) {
        onActionComplete("updated", item.feedback_id);
      }
    } catch (err) {
      console.error("Failed to update approved feedback:", err);
      setErrorMsg(formatErrorMessage(err, "Failed to update approved feedback."));
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm("Are you sure you want to delete this approved response and purge it from vector memory?")) {
      return;
    }
    try {
      setDeleting(true);
      setErrorMsg("");
      await deleteApprovedFeedback(item.feedback_id);
      setDeleting(false);
      if (onActionComplete) {
        onActionComplete("deleted", item.feedback_id);
      } else {
        onBack();
      }
    } catch (err) {
      console.error("Failed to delete approved feedback:", err);
      setErrorMsg(formatErrorMessage(err, "Failed to delete approved feedback."));
      setDeleting(false);
    }
  };

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
          Back to Approved List
        </button>

        <div className="flex items-center gap-2 flex-wrap">
          <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-lg bg-primary/15 text-primary">
            <Database className="w-3.5 h-3.5" />
            Active in RAG Vector Store
          </span>
          <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-lg bg-purple-500/15 text-purple-600 dark:text-purple-400">
            <Cpu className="w-3.5 h-3.5" />
            DPO Dataset Ready
          </span>
          <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-lg bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Approved
          </span>
        </div>
      </div>

      {errorMsg && (
        <div className="flex items-center gap-2 p-3.5 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/50 text-red-600 dark:text-red-400 text-xs font-medium">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div className="flex items-center gap-2 p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/50 text-emerald-700 dark:text-emerald-300 text-xs font-medium">
          <Check className="w-4 h-4 flex-shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* LEFT COLUMN: Original Question & Feedback Context */}
        <div className="space-y-5">
          {/* 1. User Question Card */}
          <div className="p-5 rounded-2xl bg-bg-paper border border-border-theme shadow-sm">
            <div className="flex items-center justify-between gap-2 mb-3">
              <div className="flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-primary" />
                <h4 className="font-bold text-sm text-text-primary">
                  User Question / RAG Trigger
                </h4>
              </div>
              {isEditing && (
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-primary/15 text-primary">
                  Editing
                </span>
              )}
            </div>
            {isEditing ? (
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Question trigger for vector memory lookup..."
                className="w-full p-2.5 text-xs rounded-xl bg-bg-default border border-primary focus:ring-1 focus:ring-primary focus:outline-hidden font-medium text-text-primary"
              />
            ) : (
              <div className="p-3.5 rounded-xl bg-sky-50/60 dark:bg-sky-950/20 text-text-primary font-medium text-xs border-l-4 border-primary">
                {question || item.question}
              </div>
            )}
          </div>

          {/* 2. Feedback & Approval Metadata Card */}
          <div className="p-5 rounded-2xl bg-bg-paper border border-border-theme shadow-sm">
            <h4 className="font-bold text-sm text-text-primary mb-3">
              Review & Governance Metadata
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
              <div className="col-span-2">
                <span className="text-text-secondary block mb-1">Approved By:</span>
                <div className="flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-500" />
                  <span className="font-bold text-text-primary">
                    {item.reviewed_by || "Administrator"}
                  </span>
                </div>
              </div>

              <div className="col-span-2">
                <span className="text-text-secondary block mb-1">Approved Date:</span>
                <span className="font-medium text-text-primary">
                  {item.reviewed_at ? new Date(item.reviewed_at).toLocaleString() : "-"}
                </span>
              </div>

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
                  <span>Original User:</span>
                </div>
                <span className="font-mono text-text-primary text-[11px] truncate block">
                  {item.user_id || "anonymous"}
                </span>
              </div>

              <div>
                <span className="text-text-secondary block mb-0.5">Feedback Type:</span>
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border border-border-theme text-text-secondary capitalize">
                  {item.feedback_type}
                </span>
              </div>

              {item.admin_comment && (
                <div className="col-span-2 sm:col-span-4 pt-2 border-t border-border-theme">
                  <span className="text-text-secondary block mb-1">Admin Review Note:</span>
                  <div className="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/60 italic text-text-primary">
                    "{item.admin_comment}"
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* 3. Exact Original Dolphin AI Response Card */}
          <div className="p-5 rounded-2xl bg-bg-paper border border-border-theme shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <Bot className="w-4 h-4 text-red-500" />
              <h4 className="font-bold text-sm text-text-primary">
                Exact Original Response (Rejected in DPO)
              </h4>
            </div>
            <div
              className="p-3.5 rounded-xl bg-bg-default border border-border-theme max-h-[340px] overflow-y-auto opacity-80 text-xs text-text-primary prose dark:prose-invert max-w-none"
              dangerouslySetInnerHTML={{
                __html: sanitizeMarkdown(item.original_response),
              }}
            />
          </div>
        </div>

        {/* RIGHT COLUMN: Approved Preferred Response & Actions */}
        <div className="flex flex-col">
          <div className="p-5 rounded-2xl bg-bg-paper border-2 border-emerald-500/50 shadow-sm flex flex-col h-full space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-500" />
                <h4 className="font-bold text-sm text-emerald-600 dark:text-emerald-400">
                  Approved Preferred / Corrected Response
                </h4>
              </div>

              <div className="flex items-center gap-2">
                {!isEditing ? (
                  <>
                    <button
                      type="button"
                      onClick={() => setIsEditing(true)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-primary text-primary hover:bg-primary/10 text-xs font-semibold transition-colors cursor-pointer"
                    >
                      <FileEdit className="w-3.5 h-3.5" />
                      <span>Edit & Update</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleDelete}
                      disabled={deleting}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl border border-red-300 dark:border-red-800 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/40 text-xs font-semibold transition-colors cursor-pointer"
                    >
                      {deleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                      <span className="hidden sm:inline">Delete</span>
                    </button>
                  </>
                ) : (
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => setEditorTab(0)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1 ${
                        editorTab === 0
                          ? "bg-primary text-white"
                          : "bg-slate-100 dark:bg-slate-800 text-text-secondary"
                      }`}
                    >
                      <Edit3 className="w-3 h-3" />
                      <span>Edit</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditorTab(1)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1 ${
                        editorTab === 1
                          ? "bg-primary text-white"
                          : "bg-slate-100 dark:bg-slate-800 text-text-secondary"
                      }`}
                    >
                      <Eye className="w-3 h-3" />
                      <span>Preview</span>
                    </button>
                  </div>
                )}
              </div>
            </div>

            <p className="text-xs text-text-secondary">
              This verified standard is indexed in 3072-dimensional vector memory to serve future similar questions from this company.
            </p>

            {isEditing ? (
              <div className="flex-1 flex flex-col space-y-3 min-h-[380px]">
                {editorTab === 0 ? (
                  <textarea
                    rows={18}
                    value={preferredResponse}
                    onChange={(e) => setPreferredResponse(e.target.value)}
                    placeholder="Enter corrected procedural response with exact markdown formatting..."
                    className="w-full flex-1 p-3.5 text-xs rounded-xl bg-bg-default border border-border-theme focus:ring-1 focus:ring-primary focus:outline-hidden font-mono resize-none text-text-primary leading-relaxed"
                  />
                ) : (
                  <div
                    className="flex-1 min-h-[380px] max-h-[600px] overflow-y-auto p-4 rounded-xl bg-bg-default border border-border-theme text-xs text-text-primary prose dark:prose-invert max-w-none"
                    dangerouslySetInnerHTML={{
                      __html: sanitizeMarkdown(preferredResponse || "*Empty response.*"),
                    }}
                  />
                )}

                <div className="flex items-center justify-end gap-2 pt-2 border-t border-border-theme">
                  <button
                    type="button"
                    onClick={() => {
                      setIsEditing(false);
                      setPreferredResponse(item.preferred_response || "");
                      setQuestion(item.question || "");
                    }}
                    disabled={saving}
                    className="px-3.5 py-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary rounded-xl border border-border-theme"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveUpdate}
                    disabled={saving}
                    className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl shadow-xs transition-colors cursor-pointer"
                  >
                    {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                    <span>Save & Update Memory</span>
                  </button>
                </div>
              </div>
            ) : (
              <div
                className="flex-1 min-h-[380px] max-h-[680px] overflow-y-auto p-4 rounded-xl bg-bg-default border border-border-theme text-xs text-text-primary prose dark:prose-invert max-w-none"
                dangerouslySetInnerHTML={{
                  __html: sanitizeMarkdown(preferredResponse || "*No preferred response recorded.*"),
                }}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default React.memo(ApprovedDetailView);
