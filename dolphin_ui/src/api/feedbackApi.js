import axios from "axios";
import { APP_URL } from "./config";

const feedbackClient = axios.create({
  baseURL: `${APP_URL}/feedback`,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

/**
 * Safely format error messages from API responses, preventing object rendering crashes in React.
 */
export const formatErrorMessage = (err, fallback = "An error occurred.") => {
  if (!err) return fallback;
  if (typeof err === "string") return err;
  const detail = err.response?.data?.detail ?? err.message ?? err.detail;
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return (
      detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object") {
            return item.msg || item.message || JSON.stringify(item);
          }
          return String(item);
        })
        .filter(Boolean)
        .join(", ") || fallback
    );
  }
  if (typeof detail === "object") {
    return detail.msg || detail.message || JSON.stringify(detail);
  }
  return String(detail);
};

/**
 * Submit user feedback (positive or negative)
 */
export const submitFeedback = async (feedbackData) => {
  const response = await feedbackClient.post("", feedbackData);
  return response.data;
};

/**
 * Delete feedback item by ID
 */
export const deleteFeedback = async (feedbackId) => {
  const response = await feedbackClient.delete(`/${feedbackId}`);
  return response.data;
};

/**
 * Delete feedback item by session ID and message ID
 */
export const deleteFeedbackByMessage = async (sessionId, messageId, userId = null) => {
  const params = userId ? { user_id: userId } : {};
  const response = await feedbackClient.delete(`/session/${sessionId}/message/${messageId}`, { params });
  return response.data;
};

/**
 * Get dynamic feedback statistics (Pending, Approved, Rejected counts)
 */
export const fetchFeedbackStats = async (companyId = null) => {
  const response = await feedbackClient.get("/stats", {
    params: companyId ? { company_id: companyId } : {},
  });
  return response.data;
};

/**
 * Fetch aggregated Feedback Dashboard metrics and analytics
 */
export const fetchFeedbackDashboard = async (filters = {}) => {
  let params = {};
  if (typeof filters === "string") {
    params.date_range = filters;
  } else if (filters && typeof filters === "object") {
    const {
      fromDate = null,
      toDate = null,
      from_date = null,
      to_date = null,
      dateRange = null,
      date_range = "30d",
      companyId = null,
      company_id = null,
      shipType = null,
      ship_type = null,
      status = null,
      feedbackType = null,
      feedback_type = null,
      reviewerId = null,
      reviewer_id = null,
    } = filters;

    const startD = fromDate || from_date;
    const endD = toDate || to_date;
    const dRange = dateRange || date_range || "30d";
    const cId = companyId || company_id;
    const sType = shipType || ship_type;
    const fbType = feedbackType || feedback_type;
    const revId = reviewerId || reviewer_id;

    if (startD) params.from_date = startD;
    if (endD) params.to_date = endD;
    if (dRange) params.date_range = dRange;
    if (cId && cId !== "all") params.company_id = cId;
    if (sType && sType !== "all") params.ship_type = sType;
    if (status && status !== "all") params.status = status;
    if (fbType && fbType !== "all") params.feedback_type = fbType;
    if (revId && revId !== "all") params.reviewer_id = revId;
  }

  const response = await feedbackClient.get("/dashboard", { params });
  return response.data;
};

/**
 * List pending feedback items
 */
export const fetchPendingFeedback = async (options = {}) => {
  const {
    companyId = null,
    company_id = null,
    shipType = null,
    ship_type = null,
    feedbackType = null,
    feedback_type = null,
    search = "",
    limit = 50,
    offset = 0,
  } = options;

  const params = { limit, offset };
  const cId = companyId || company_id;
  const sType = shipType || ship_type;
  const fbType = feedbackType || feedback_type;

  if (cId && cId !== "all") params.company_id = cId;
  if (sType && sType !== "all") params.ship_type = sType;
  if (fbType && fbType !== "all") params.feedback_type = fbType;
  if (search) params.search = search;

  const response = await feedbackClient.get("/pending", { params });
  return response.data;
};

/**
 * List approved feedback items
 */
export const fetchApprovedFeedback = async (options = {}) => {
  const {
    companyId = null,
    company_id = null,
    shipType = null,
    ship_type = null,
    search = "",
    limit = 50,
    offset = 0,
  } = options;

  const params = { limit, offset };
  const cId = companyId || company_id;
  const sType = shipType || ship_type;

  if (cId && cId !== "all") params.company_id = cId;
  if (sType && sType !== "all") params.ship_type = sType;
  if (search) params.search = search;

  const response = await feedbackClient.get("/approved", { params });
  return response.data;
};

/**
 * Get single feedback item details
 */
export const fetchFeedbackDetail = async (feedbackId) => {
  const response = await feedbackClient.get(`/${feedbackId}`);
  return response.data;
};

/**
 * Approve feedback item (with preferred response and optional edited question)
 */
export const approveFeedback = async (feedbackId, options = {}) => {
  const {
    preferredResponse,
    preferred_response,
    question = null,
    reviewerId = "admin",
    reviewer_id = "admin",
    adminComment = "",
    admin_comment = "",
    companyId = null,
    company_id = null,
    shipType = null,
    ship_type = null,
  } = options;

  const payload = {
    preferred_response: preferredResponse || preferred_response,
    reviewer_id: reviewerId || reviewer_id || "admin",
    admin_comment: adminComment || admin_comment || null,
    company_id: companyId || company_id || null,
    ship_type: shipType || ship_type || null,
  };
  if (question && typeof question === "string" && question.trim()) {
    payload.question = question.trim();
  }
  const response = await feedbackClient.post(`/${feedbackId}/approve`, payload);
  return response.data;
};

/**
 * Update an existing approved feedback response
 */
export const updateApprovedFeedback = async (feedbackId, options = {}) => {
  const {
    preferredResponse,
    preferred_response,
    question = null,
    reviewerId = "admin",
    reviewer_id = "admin",
    adminComment = "",
    admin_comment = "",
    companyId = null,
    company_id = null,
    shipType = null,
    ship_type = null,
  } = options;

  const payload = {
    preferred_response: preferredResponse || preferred_response,
    reviewer_id: reviewerId || reviewer_id || "admin",
    admin_comment: adminComment || admin_comment || null,
    company_id: companyId || company_id || null,
    ship_type: shipType || ship_type || null,
  };
  if (question && typeof question === "string" && question.trim()) {
    payload.question = question.trim();
  }
  const response = await feedbackClient.put(`/${feedbackId}/approved`, payload);
  return response.data;
};

/**
 * Delete an approved feedback item from vector memory and database
 */
export const deleteApprovedFeedback = async (feedbackId) => {
  const response = await feedbackClient.delete(`/${feedbackId}/approved`);
  return response.data;
};

/**
 * Regenerate preferred response using AI based on admin reference topic / course content
 */
export const regenerateFeedbackResponse = async (feedbackId, options = {}) => {
  const {
    topic,
    referenceText = null,
    reference_text = null,
    reviewerInstructions = null,
    reviewer_instructions = null,
    companyId = null,
    company_id = null,
    shipType = null,
    ship_type = null,
  } = options;

  const response = await feedbackClient.post(`/${feedbackId}/regenerate`, {
    topic,
    reference_text: referenceText || reference_text || null,
    reviewer_instructions: reviewerInstructions || reviewer_instructions || null,
    company_id: companyId || company_id || null,
    ship_type: shipType || ship_type || null,
  });
  return response.data;
};

/**
 * Search reference topics from Course Content and Company Documents
 */
export const searchReferenceTopics = async (query = "", companyId = null) => {
  const params = { query };
  if (companyId) params.company_id = companyId;
  const response = await feedbackClient.get("/topics/search", { params });
  return response.data;
};

/**
 * Reject feedback item (with mandatory rejection reason)
 */
export const rejectFeedback = async (feedbackId, options = {}) => {
  const {
    rejectionReason,
    rejection_reason,
    reviewerId = "admin",
    reviewer_id = "admin",
    adminComment = "",
    admin_comment = "",
  } = options;

  const response = await feedbackClient.post(`/${feedbackId}/reject`, {
    rejection_reason: rejectionReason || rejection_reason,
    reviewer_id: reviewerId || reviewer_id || "admin",
    admin_comment: adminComment || admin_comment || null,
  });
  return response.data;
};

/**
 * Fetch DPO dataset preview
 */
export const fetchDpoDataset = async ({ companyId = null, status = null, limit = 500 } = {}) => {
  const params = { limit };
  if (companyId) params.company_id = companyId;
  if (status) params.status = status;

  const response = await feedbackClient.get("/dpo/dataset", { params });
  return response.data;
};

/**
 * Trigger offline DPO training job
 */
export const createDpoJob = async ({ baseModel = "gpt-4o-mini", datasetVersion = null, companyId = null } = {}) => {
  const response = await feedbackClient.post("/dpo/jobs", {
    base_model: baseModel,
    dataset_version: datasetVersion,
    company_id: companyId,
  });
  return response.data;
};

/**
 * List DPO training jobs
 */
export const fetchDpoJobs = async (limit = 50) => {
  const response = await feedbackClient.get("/dpo/jobs", { params: { limit } });
  return response.data;
};

/**
 * Get single DPO job status
 */
export const fetchDpoJobDetail = async (jobId) => {
  const response = await feedbackClient.get(`/dpo/jobs/${jobId}`);
  return response.data;
};

/**
 * Unified feedbackApi Object Export with Full Named & Aliased Method Support
 */
export const feedbackApi = {
  // Submission & Deletion
  submitFeedback,
  deleteFeedback,
  deleteFeedbackByMessage,

  // Stats & Dashboard
  getStats: fetchFeedbackStats,
  fetchFeedbackStats,
  getDashboardAnalytics: fetchFeedbackDashboard,
  fetchFeedbackDashboard,

  // Pending & Approved Lists
  getPendingFeedback: fetchPendingFeedback,
  fetchPendingFeedback,
  getApprovedFeedback: fetchApprovedFeedback,
  fetchApprovedFeedback,

  // Single Ticket Detail & Actions
  getFeedbackDetail: fetchFeedbackDetail,
  fetchFeedbackDetail,
  approveFeedback,
  updateApprovedFeedback,
  deleteApprovedFeedback,

  // AI Regeneration & Topics
  regeneratePreferredResponse: regenerateFeedbackResponse,
  regenerateFeedbackResponse,
  searchTopics: searchReferenceTopics,
  searchReferenceTopics,
  rejectFeedback,

  // DPO Datasets & Fine-Tuning
  exportDpoDataset: fetchDpoDataset,
  fetchDpoDataset,
  createDpoJob,
  listDpoJobs: fetchDpoJobs,
  fetchDpoJobs,
  getDpoJobDetail: fetchDpoJobDetail,
  fetchDpoJobDetail,

  // Error formatting
  formatErrorMessage,
};

export default feedbackApi;
