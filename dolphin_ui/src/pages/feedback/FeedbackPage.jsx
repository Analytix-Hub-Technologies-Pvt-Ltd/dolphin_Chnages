import React, { useState, useEffect, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { X } from "lucide-react";

import FeedbackDashboard from "../../components/feedback/FeedbackDashboard";
import PendingFeedbackList from "../../components/feedback/PendingFeedbackList";
import PendingDetailView from "../../components/feedback/PendingDetailView";
import ApprovedFeedbackList from "../../components/feedback/ApprovedFeedbackList";
import ApprovedDetailView from "../../components/feedback/ApprovedDetailView";

import {
  fetchFeedbackStats,
  fetchPendingFeedback,
  fetchApprovedFeedback,
  fetchFeedbackDetail,
} from "../../api/feedbackApi";
import { isFeedbackAuthorized, getCurrentUserEmail, getCurrentUserRole } from "../../utils/feedbackAuth";

const FeedbackPage = ({ userProfile }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const basePath = location.pathname.startsWith("/admin/") ? "/admin/feedback" : "/feedback";
  const [section, detailId] = location.pathname.slice(basePath.length).split("/").filter(Boolean);
  const activeTab = section === "pending" ? 1 : section === "approved" ? 2 : 0;
  const selectedId = activeTab > 0 ? detailId : null;
  const isAuthorized = isFeedbackAuthorized(userProfile?.email || getCurrentUserEmail(), getCurrentUserRole());

  useEffect(() => {
    if (!isAuthorized) {
      navigate("/", { replace: true });
    }
  }, [isAuthorized, navigate]);

  const [selectedDetail, setSelectedDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Stats for badge counts
  const [stats, setStats] = useState({ pending_count: 0, approved_count: 0 });

  // List states
  const [pendingItems, setPendingItems] = useState([]);
  const [pendingTotal, setPendingTotal] = useState(0);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [pendingSearch, setPendingSearch] = useState("");
  const [pendingPage, setPendingPage] = useState(0);
  const [pendingRowsPerPage, setPendingRowsPerPage] = useState(25);

  const [approvedItems, setApprovedItems] = useState([]);
  const [approvedTotal, setApprovedTotal] = useState(0);
  const [approvedLoading, setApprovedLoading] = useState(false);
  const [approvedSearch, setApprovedSearch] = useState("");
  const [approvedPage, setApprovedPage] = useState(0);
  const [approvedRowsPerPage, setApprovedRowsPerPage] = useState(25);

  // Toast notifications
  const [toast, setToast] = useState({ open: false, message: "", severity: "success" });

  // Load stats
  const loadStats = useCallback(async () => {
    try {
      const data = await fetchFeedbackStats(userProfile?.company_id || null);
      setStats({
        pending_count: data.pending_count || 0,
        approved_count: data.approved_count || 0,
      });
    } catch (err) {
      console.error("Failed to load feedback stats:", err);
    }
  }, [userProfile?.company_id]);

  // Load Pending list
  const loadPending = useCallback(async () => {
    try {
      setPendingLoading(true);
      const data = await fetchPendingFeedback({
        companyId: userProfile?.company_id || null,
        search: pendingSearch,
        limit: pendingRowsPerPage,
        offset: pendingPage * pendingRowsPerPage,
      });
      const items = Array.isArray(data) ? data : data?.items || [];
      const total = typeof data?.total === "number" ? data.total : items.length;
      setPendingItems(items);
      setPendingTotal(total);
    } catch (err) {
      console.error("Failed to load pending feedback:", err);
      setPendingItems([]);
      setPendingTotal(0);
    } finally {
      setPendingLoading(false);
    }
  }, [userProfile?.company_id, pendingSearch, pendingPage, pendingRowsPerPage]);

  // Load Approved list
  const loadApproved = useCallback(async () => {
    try {
      setApprovedLoading(true);
      const data = await fetchApprovedFeedback({
        companyId: userProfile?.company_id || null,
        search: approvedSearch,
        limit: approvedRowsPerPage,
        offset: approvedPage * approvedRowsPerPage,
      });
      const items = Array.isArray(data) ? data : data?.items || [];
      const total = typeof data?.total === "number" ? data.total : items.length;
      setApprovedItems(items);
      setApprovedTotal(total);
    } catch (err) {
      console.error("Failed to load approved feedback:", err);
      setApprovedItems([]);
      setApprovedTotal(0);
    } finally {
      setApprovedLoading(false);
    }
  }, [userProfile?.company_id, approvedSearch, approvedPage, approvedRowsPerPage]);

  const handleSelectItem = (feedbackId, statusHint = null) => {
    const target = statusHint === "approved" || (statusHint !== "pending" && activeTab === 2)
      ? "approved" : "pending";
    navigate(`${basePath}/${target}/${encodeURIComponent(feedbackId)}`);
  };

  useEffect(() => {
    if (isAuthorized) loadStats();
  }, [isAuthorized, loadStats]);

  useEffect(() => {
    let cancelled = false;
    setSelectedDetail(null);
    if (!isAuthorized || !selectedId) {
      setDetailLoading(false);
      return;
    }
    setDetailLoading(true);
    fetchFeedbackDetail(decodeURIComponent(selectedId))
      .then((detail) => { if (!cancelled) setSelectedDetail(detail); })
      .catch(() => {
        if (!cancelled) setToast({ open: true, message: "Failed to load feedback details.", severity: "error" });
      })
      .finally(() => { if (!cancelled) setDetailLoading(false); });
    return () => { cancelled = true; };
  }, [isAuthorized, selectedId, activeTab]);

  // Reload lists when tabs/search change
  useEffect(() => {
    if (!isAuthorized) return;
    if (activeTab === 1) {
      loadPending();
    } else if (activeTab === 2) {
      loadApproved();
    }
  }, [isAuthorized, activeTab, loadPending, loadApproved]);

  // Dismiss toast after 4.5s
  useEffect(() => {
    if (toast.open) {
      const timer = setTimeout(() => {
        setToast((prev) => ({ ...prev, open: false }));
      }, 4500);
      return () => clearTimeout(timer);
    }
  }, [toast.open]);

  const handleTabChange = (newIndex, newPath = null) => {
    const section = ["dashboard", "pending", "approved"][newIndex] || "dashboard";
    const query = newPath?.includes("?") ? newPath.slice(newPath.indexOf("?")) : "";
    navigate(`${basePath}/${section}${query}`);
  };

  const handleBackToList = () => {
    navigate(`${basePath}/${activeTab === 2 ? "approved" : "pending"}`);
  };

  const handleActionComplete = (action, feedbackId) => {
    loadStats();
    loadPending();
    loadApproved();

    if (action === "approved") {
      setToast({
        open: true,
        message: `Feedback ${feedbackId} approved! Stored in vector memory & DPO training dataset.`,
        severity: "success",
      });
      // Directly show the approved response in the Approved Detail View
      handleSelectItem(feedbackId, "approved");
    } else if (action === "updated") {
      setToast({
        open: true,
        message: `Approved feedback updated and re-indexed in vector memory.`,
        severity: "success",
      });
      fetchFeedbackDetail(feedbackId).then(setSelectedDetail).catch(() => {
        setToast({ open: true, message: "Unable to refresh feedback details.", severity: "error" });
      });
    } else if (action === "deleted") {
      handleBackToList();
      setToast({
        open: true,
        message: `Approved feedback record deleted and purged from vector memory.`,
        severity: "info",
      });
    } else if (action === "rejected") {
      handleBackToList();
      setToast({
        open: true,
        message: `Feedback ${feedbackId} rejected.`,
        severity: "info",
      });
    } else {
      handleBackToList();
    }
  };

  if (!isAuthorized) {
    return null;
  }

  return (
    <div className="fb-page-container">
      <div className="fb-main-body" style={{ flex: 1, padding: "24px", boxSizing: "border-box" }}>
        <div className="fb-content-wrapper" style={{ maxWidth: 1400, margin: "0 auto", width: "100%", boxSizing: "border-box" }}>
          {/* Right Main Content Area */}
          <div className="fb-main-area" style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 20, width: "100%", boxSizing: "border-box" }}>
            {activeTab === 0 ? (
              <FeedbackDashboard
                onNavigateTab={handleTabChange}
                onSelectItem={handleSelectItem}
                userProfile={userProfile}
              />
            ) : activeTab === 1 ? (
                selectedId ? (
                  <PendingDetailView
                    item={selectedDetail}
                    loading={detailLoading}
                    onBack={handleBackToList}
                    onActionComplete={handleActionComplete}
                    reviewerId={userProfile?.name || "admin"}
                  />
                ) : (
                  <PendingFeedbackList
                    items={pendingItems}
                    loading={pendingLoading}
                    onSelectItem={handleSelectItem}
                    onRefresh={() => {
                      loadStats();
                      loadPending();
                    }}
                    searchTerm={pendingSearch}
                    onSearchChange={(val) => {
                      setPendingSearch(val);
                      setPendingPage(0);
                    }}
                    page={pendingPage}
                    rowsPerPage={pendingRowsPerPage}
                    onPageChange={(newPage) => setPendingPage(newPage)}
                    onRowsPerPageChange={(newLimit) => {
                      setPendingRowsPerPage(newLimit);
                      setPendingPage(0);
                    }}
                    totalCount={pendingTotal || stats.pending_count}
                  />
                )
              ) : selectedId ? (
                <ApprovedDetailView
                  item={selectedDetail}
                  loading={detailLoading}
                  onBack={handleBackToList}
                  onActionComplete={handleActionComplete}
                  reviewerId={userProfile?.name || "admin"}
                />
              ) : (
                <ApprovedFeedbackList
                  items={approvedItems}
                  loading={approvedLoading}
                  onSelectItem={handleSelectItem}
                  onRefresh={() => {
                    loadStats();
                    loadApproved();
                  }}
                  searchTerm={approvedSearch}
                  onSearchChange={(val) => {
                    setApprovedSearch(val);
                    setApprovedPage(0);
                  }}
                  page={approvedPage}
                  rowsPerPage={approvedRowsPerPage}
                  onPageChange={(newPage) => setApprovedPage(newPage)}
                  onRowsPerPageChange={(newLimit) => {
                    setApprovedRowsPerPage(newLimit);
                    setApprovedPage(0);
                  }}
                  totalCount={approvedTotal || stats.approved_count}
                />
              )}
            </div>
          </div>
        </div>

      {/* Toast Notification */}
      {toast.open && (
        <div
          className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-2xl text-xs font-semibold text-white animate-in fade-in duration-200 ${
            toast.severity === "error"
              ? "bg-red-600"
              : toast.severity === "info"
              ? "bg-slate-800"
              : "bg-emerald-600"
          }`}
        >
          <span>{toast.message}</span>
          <button
            type="button"
            onClick={() => setToast((prev) => ({ ...prev, open: false }))}
            className="p-1 hover:opacity-80 rounded"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};

export default React.memo(FeedbackPage);
