import axios from "axios";
import APP_URL from "../config/apiConfig";

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
export const fetchFeedbackDashboard = async ({
  fromDate = null,
  toDate = null,
  dateRange = "30d",
  companyId = null,
  shipType = null,
  status = null,
  feedbackType = null,
  reviewerId = null,
} = {}) => {
  const params = {};
  if (fromDate) params.from_date = fromDate;
  if (toDate) params.to_date = toDate;
  if (dateRange) params.date_range = dateRange;
  if (companyId) params.company_id = companyId;
  if (shipType) params.ship_type = shipType;
  if (status && status !== "all") params.status = status;
  if (feedbackType && feedbackType !== "all") params.feedback_type = feedbackType;
  if (reviewerId && reviewerId !== "all") params.reviewer_id = reviewerId;

  const response = await feedbackClient.get("/dashboard", { params });
  return response.data;
};

/**
 * List pending feedback items
 */
export const fetchPendingFeedback = async ({
  companyId = null,
  search = "",
  limit = 50,
  offset = 0,
} = {}) => {
  const params = { limit, offset };
  if (companyId) params.company_id = companyId;
  if (search) params.search = search;

  const response = await feedbackClient.get("/pending", { params });
  return response.data;
};

/**
 * List approved feedback items
 */
export const fetchApprovedFeedback = async ({
  companyId = null,
  search = "",
  limit = 50,
  offset = 0,
} = {}) => {
  const params = { limit, offset };
  if (companyId) params.company_id = companyId;
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
export const approveFeedback = async (
  feedbackId,
  { preferredResponse, question = null, reviewerId = "admin", adminComment = "" }
) => {
  const payload = {
    preferred_response: preferredResponse,
    reviewer_id: reviewerId,
    admin_comment: adminComment,
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
export const updateApprovedFeedback = async (
  feedbackId,
  { preferredResponse, question = null, reviewerId = "admin", adminComment = "" }
) => {
  const payload = {
    preferred_response: preferredResponse,
    reviewer_id: reviewerId,
    admin_comment: adminComment,
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
export const regenerateFeedbackResponse = async (
  feedbackId,
  { topic, referenceText = null, reviewerInstructions = null, companyId = null, shipType = null }
) => {
  const response = await feedbackClient.post(`/${feedbackId}/regenerate`, {
    topic,
    reference_text: referenceText,
    reviewer_instructions: reviewerInstructions,
    company_id: companyId,
    ship_type: shipType,
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
export const rejectFeedback = async (
  feedbackId,
  { rejectionReason, reviewerId = "admin" }
) => {
  const response = await feedbackClient.post(`/${feedbackId}/reject`, {
    rejection_reason: rejectionReason,
    reviewer_id: reviewerId,
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
