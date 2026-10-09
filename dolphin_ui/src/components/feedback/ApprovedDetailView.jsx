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
      setPreferredResponse(item.preferred_response || item.edited_response || item.original_response || "");
      setQuestion(item.question || "");
      setAdminComment(item.admin_comment || item.reviewer_notes || "");
      setIsEditing(false);
      setErrorMsg("");
      setSuccessMsg("");
    }
  }, [item]);

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
          Approved record not found.
        </h3>
        <button
          type="button"
          onClick={onBack}
          className="fb-btn-primary"
        >
          <ArrowLeft style={{ width: 16, height: 16 }} />
          <span>Back to List</span>
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
    <div className="fb-detail-container" style={{ width: "100%", display: "flex", flexDirection: "column", gap: 20, paddingBottom: 40, boxSizing: "border-box" }}>
      {/* Top Header with Back Navigation & Badges */}
      <div className="fb-detail-top-bar" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12, width: "100%" }}>
        <button
          type="button"
          onClick={onBack}
          className="fb-back-btn"
          style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 12, border: "1px solid var(--fb-border)", backgroundColor: "var(--fb-bg-paper)", color: "var(--fb-text-primary)", fontSize: 12, fontWeight: 600, cursor: "pointer", boxShadow: "0 1px 2px rgba(0,0,0,0.05)" }}
        >
          <ArrowLeft style={{ width: 16, height: 16 }} />
          <span>Back to Approved List</span>
        </button>

        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, fontWeight: 700, padding: "4px 10px", borderRadius: 9999, backgroundColor: "rgba(16, 107, 163, 0.12)", color: "var(--fb-primary)" }}>
            <Database style={{ width: 12, height: 12 }} />
            Active in Vector Store
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, fontWeight: 700, padding: "4px 10px", borderRadius: 9999, backgroundColor: "rgba(147, 51, 234, 0.12)", color: "#9333ea" }}>
            <Cpu style={{ width: 12, height: 12 }} />
            DPO Ready
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, fontWeight: 700, padding: "4px 10px", borderRadius: 9999, backgroundColor: "rgba(22, 163, 74, 0.12)", color: "var(--fb-success)" }}>
            <CheckCircle2 style={{ width: 12, height: 12 }} />
            Approved
          </span>
        </div>
      </div>

      {errorMsg && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderRadius: 12, backgroundColor: "rgba(220, 38, 38, 0.08)", border: "1px solid rgba(220, 38, 38, 0.3)", color: "var(--fb-danger)", fontSize: 12, fontWeight: 600 }}>
          <AlertTriangle style={{ width: 16, height: 16, flexShrink: 0 }} />
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderRadius: 12, backgroundColor: "rgba(22, 163, 74, 0.08)", border: "1px solid rgba(22, 163, 74, 0.3)", color: "var(--fb-success)", fontSize: 12, fontWeight: 600 }}>
          <Check style={{ width: 16, height: 16, flexShrink: 0 }} />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Main Split View */}
      <div className="fb-detail-2col" style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 20, width: "100%", boxSizing: "border-box" }}>
        {/* LEFT COLUMN: Original Question & Feedback Context */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20, width: "100%" }}>
          {/* 1. User Question Card */}
          <div className="fb-card" style={{ padding: 20, borderRadius: 16, backgroundColor: "var(--fb-bg-paper)", border: "1px solid var(--fb-border)", boxShadow: "0 1px 3px rgba(0,0,0,0.05)", margin: 0 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <HelpCircle style={{ width: 16, height: 16, color: "var(--fb-primary)" }} />
                <h4 style={{ fontSize: 14, fontWeight: 700, color: "var(--fb-text-primary)", margin: 0 }}>
                  User Question / RAG Trigger
                </h4>
              </div>
              {isEditing && (
                <span style={{ fontSize: 10, textTransform: "uppercase", fontWeight: 700, padding: "2px 8px", borderRadius: 9999, backgroundColor: "rgba(16, 107, 163, 0.15)", color: "var(--fb-primary)" }}>
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
                style={{ width: "100%", padding: 10, fontSize: 12, borderRadius: 10, border: "1px solid var(--fb-primary)", outline: "none", boxSizing: "border-box", fontWeight: 600 }}
              />
            ) : (
              <div style={{ padding: 12, borderRadius: 10, backgroundColor: "rgba(16, 107, 163, 0.06)", borderLeft: "4px solid var(--fb-primary)", color: "var(--fb-text-primary)", fontSize: 13, fontWeight: 600 }}>
                {question || item.question}
              </div>
            )}
          </div>

          {/* 2. Feedback & Approval Metadata Card */}
          <div className="fb-card" style={{ padding: 20, borderRadius: 16, backgroundColor: "var(--fb-bg-paper)", border: "1px solid var(--fb-border)", boxShadow: "0 1px 3px rgba(0,0,0,0.05)", margin: 0 }}>
            <h4 style={{ fontSize: 14, fontWeight: 700, color: "var(--fb-text-primary)", margin: "0 0 14px 0" }}>
              Review & Governance Metadata
            </h4>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 14, fontSize: 12 }}>
              <div>
                <span style={{ color: "var(--fb-text-secondary)", display: "block", marginBottom: 4, fontSize: 11, fontWeight: 600, textTransform: "uppercase" }}>Approved By:</span>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <ShieldCheck style={{ width: 16, height: 16, color: "var(--fb-success)" }} />
                  <span style={{ fontWeight: 700, color: "var(--fb-text-primary)" }}>
                    {item.reviewed_by_name || item.reviewed_by || "Administrator"}
                  </span>
                </div>
              </div>

              <div>
                <span style={{ color: "var(--fb-text-secondary)", display: "block", marginBottom: 4, fontSize: 11, fontWeight: 600, textTransform: "uppercase" }}>Approved Date:</span>
                <span style={{ fontWeight: 600, color: "var(--fb-text-primary)" }}>
                  {(item.reviewed_at || item.resolved_at || item.updated_at)
                    ? new Date(item.reviewed_at || item.resolved_at || item.updated_at).toLocaleString()
                    : "-"}
                </span>
              </div>

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
                  <span>Original User:</span>
                </div>
                <span style={{ fontFamily: "monospace", color: "var(--fb-text-primary)", fontSize: 11 }}>
                  {item.user_id || "anonymous"}
                </span>
              </div>

              <div>
                <span style={{ color: "var(--fb-text-secondary)", display: "block", marginBottom: 2, fontSize: 11, fontWeight: 600, textTransform: "uppercase" }}>Feedback Type:</span>
                <span style={{ display: "inline-flex", alignItems: "center", padding: "2px 8px", borderRadius: 9999, fontSize: 11, fontWeight: 600, border: "1px solid var(--fb-border)", color: "var(--fb-text-secondary)", textTransform: "capitalize" }}>
                  {item.feedback_type?.replace(/_/g, " ")}
                </span>
              </div>

              {(item.admin_comment || item.reviewer_notes) && (
                <div style={{ gridColumn: "span 2", paddingTop: 8, borderTop: "1px solid var(--fb-border)" }}>
                  <span style={{ color: "var(--fb-text-secondary)", display: "block", marginBottom: 4, fontSize: 11, fontWeight: 600, textTransform: "uppercase" }}>Admin Review Note:</span>
                  <div style={{ padding: 10, borderRadius: 10, backgroundColor: "var(--fb-bg-default)", fontStyle: "italic", color: "var(--fb-text-primary)", border: "1px solid var(--fb-border)" }}>
                    "{item.admin_comment || item.reviewer_notes}"
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* 3. Exact Original Dolphin AI Response Card */}
          <div className="fb-card" style={{ padding: 20, borderRadius: 16, backgroundColor: "var(--fb-bg-paper)", border: "1px solid var(--fb-border)", boxShadow: "0 1px 3px rgba(0,0,0,0.05)", margin: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <Bot style={{ width: 16, height: 16, color: "var(--fb-danger)" }} />
              <h4 style={{ fontSize: 14, fontWeight: 700, color: "var(--fb-text-primary)", margin: 0 }}>
                Exact Original Response (Rejected in DPO)
              </h4>
            </div>
            <div
              style={{ padding: 14, borderRadius: 12, backgroundColor: "var(--fb-bg-default)", border: "1px solid var(--fb-border)", maxHeight: 320, overflowY: "auto", fontSize: 12, color: "var(--fb-text-secondary)", lineHeight: 1.6 }}
              dangerouslySetInnerHTML={{
                __html: sanitizeMarkdown(item.original_response),
              }}
            />
          </div>
        </div>

        {/* RIGHT COLUMN: Approved Preferred Response & Actions */}
        <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
          <div className="fb-card" style={{ padding: 20, borderRadius: 16, backgroundColor: "var(--fb-bg-paper)", border: "2px solid rgba(22, 163, 74, 0.5)", boxShadow: "0 1px 3px rgba(0,0,0,0.05)", margin: 0, display: "flex", flexDirection: "column", height: "100%", boxSizing: "border-box" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <ShieldCheck style={{ width: 18, height: 18, color: "var(--fb-success)" }} />
                <h4 style={{ fontSize: 14, fontWeight: 700, color: "var(--fb-success)", margin: 0 }}>
                  Approved Preferred / Corrected Response
                </h4>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {!isEditing ? (
                  <>
                    <button
                      type="button"
                      onClick={() => setIsEditing(true)}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 4,
                        padding: "6px 12px",
                        borderRadius: 10,
                        border: "1px solid var(--fb-primary)",
                        color: "var(--fb-primary)",
                        backgroundColor: "transparent",
                        fontSize: 11,
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                    >
                      <FileEdit style={{ width: 14, height: 14 }} />
                      <span>Edit & Update</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleDelete}
                      disabled={deleting}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 4,
                        padding: "6px 10px",
                        borderRadius: 10,
                        border: "1px solid rgba(220, 38, 38, 0.3)",
                        color: "var(--fb-danger)",
                        backgroundColor: "transparent",
                        fontSize: 11,
                        fontWeight: 600,
                        cursor: deleting ? "not-allowed" : "pointer",
                      }}
                    >
                      {deleting ? <Loader2 style={{ width: 14, height: 14, animation: "spin 1s linear infinite" }} /> : <Trash2 style={{ width: 14, height: 14 }} />}
                      <span>Delete</span>
                    </button>
                  </>
                ) : (
                  <div style={{ display: "flex", alignItems: "center", backgroundColor: "var(--fb-bg-default)", borderRadius: 10, padding: 3 }}>
                    <button
                      type="button"
                      onClick={() => setEditorTab(0)}
                      style={{
                        padding: "4px 10px",
                        borderRadius: 8,
                        fontSize: 11,
                        fontWeight: 700,
                        border: "none",
                        cursor: "pointer",
                        backgroundColor: editorTab === 0 ? "var(--fb-bg-paper)" : "transparent",
                        color: editorTab === 0 ? "var(--fb-primary)" : "var(--fb-text-secondary)",
                        boxShadow: editorTab === 0 ? "0 1px 2px rgba(0,0,0,0.08)" : "none",
                      }}
                    >
                      <Edit3 style={{ width: 12, height: 12, display: "inline", marginRight: 4 }} />
                      <span>Edit</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditorTab(1)}
                      style={{
                        padding: "4px 10px",
                        borderRadius: 8,
                        fontSize: 11,
                        fontWeight: 700,
                        border: "none",
                        cursor: "pointer",
                        backgroundColor: editorTab === 1 ? "var(--fb-bg-paper)" : "transparent",
                        color: editorTab === 1 ? "var(--fb-primary)" : "var(--fb-text-secondary)",
                        boxShadow: editorTab === 1 ? "0 1px 2px rgba(0,0,0,0.08)" : "none",
                      }}
                    >
                      <Eye style={{ width: 12, height: 12, display: "inline", marginRight: 4 }} />
                      <span>Preview</span>
                    </button>
                  </div>
                )}
              </div>
            </div>

            <p style={{ fontSize: 12, color: "var(--fb-text-secondary)", margin: "0 0 12px 0", lineHeight: 1.4 }}>
              This verified standard is indexed in 3072-dimensional vector memory to serve future similar questions from this company.
            </p>

            {isEditing ? (
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 12 }}>
                {editorTab === 0 ? (
                  <textarea
                    rows={18}
                    value={preferredResponse}
                    onChange={(e) => setPreferredResponse(e.target.value)}
                    placeholder="Enter corrected procedural response with exact markdown formatting..."
                    style={{
                      width: "100%",
                      flex: 1,
                      minHeight: 340,
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
                      resize: "vertical",
                    }}
                  />
                ) : (
                  <div
                    style={{
                      flex: 1,
                      minHeight: 340,
                      maxHeight: 500,
                      overflowY: "auto",
                      padding: 14,
                      borderRadius: 12,
                      backgroundColor: "var(--fb-bg-default)",
                      border: "1px solid var(--fb-border)",
                      fontSize: 12,
                      color: "var(--fb-text-primary)",
                      lineHeight: 1.6,
                    }}
                    dangerouslySetInnerHTML={{
                      __html: sanitizeMarkdown(preferredResponse || "*Empty response.*"),
                    }}
                  />
                )}

                <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 10, paddingTop: 10, borderTop: "1px solid var(--fb-border)" }}>
                  <button
                    type="button"
                    onClick={() => {
                      setIsEditing(false);
                      setPreferredResponse(item.preferred_response || item.edited_response || "");
                      setQuestion(item.question || "");
                    }}
                    disabled={saving}
                    style={{ padding: "8px 14px", fontSize: 12, fontWeight: 600, color: "var(--fb-text-secondary)", borderRadius: 10, border: "1px solid #cbd5e1", backgroundColor: "var(--fb-bg-paper)", cursor: "pointer" }}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveUpdate}
                    disabled={saving}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "8px 16px",
                      fontSize: 12,
                      fontWeight: 700,
                      color: "#ffffff",
                      backgroundColor: "var(--fb-success)",
                      borderRadius: 10,
                      border: "none",
                      cursor: saving ? "not-allowed" : "pointer",
                      boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
                    }}
                  >
                    {saving ? <Loader2 style={{ width: 14, height: 14, animation: "spin 1s linear infinite" }} /> : <Save style={{ width: 14, height: 14 }} />}
                    <span>Save & Update Memory</span>
                  </button>
                </div>
              </div>
            ) : (
              <div
                style={{
                  flex: 1,
                  minHeight: 340,
                  maxHeight: 600,
                  overflowY: "auto",
                  padding: 16,
                  borderRadius: 12,
                  backgroundColor: "var(--fb-bg-default)",
                  border: "1px solid var(--fb-border)",
                  fontSize: 12,
                  color: "var(--fb-text-primary)",
                  lineHeight: 1.6,
                }}
                dangerouslySetInnerHTML={{
                  __html: sanitizeMarkdown(preferredResponse || item.edited_response || item.preferred_response || "*No preferred response recorded.*"),
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
