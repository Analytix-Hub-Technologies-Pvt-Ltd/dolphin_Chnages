import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { X } from "lucide-react";

import FeedbackHeader from "../../components/feedback/FeedbackHeader";
import FeedbackSidebar from "../../components/feedback/FeedbackSidebar";
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

const FeedbackPage = ({ onNavigateToChat, userProfile, onLogout }) => {
  const navigate = useNavigate();
  const handleNavChat = onNavigateToChat || (() => navigate("/"));

  // Tab state: 0 -> Dashboard, 1 -> Pending, 2 -> Approved
  const [activeTab, setActiveTab] = useState(0);

  // Subview selection
  const [selectedId, setSelectedId] = useState(null);
  const [selectedDetail, setSelectedDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Stats for badge counts
  const [stats, setStats] = useState({ pending_count: 0, approved_count: 0 });

  // List states
  const [pendingItems, setPendingItems] = useState([]);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [pendingSearch, setPendingSearch] = useState("");
  const [pendingPage, setPendingPage] = useState(0);
  const [pendingRowsPerPage, setPendingRowsPerPage] = useState(25);

  const [approvedItems, setApprovedItems] = useState([]);
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
      setPendingItems(data || []);
    } catch (err) {
      console.error("Failed to load pending feedback:", err);
      setPendingItems([]);
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
      setApprovedItems(data || []);
    } catch (err) {
      console.error("Failed to load approved feedback:", err);
      setApprovedItems([]);
    } finally {
      setApprovedLoading(false);
    }
  }, [userProfile?.company_id, approvedSearch, approvedPage, approvedRowsPerPage]);

  const handleSelectItem = useCallback(async (feedbackId, statusHint = null) => {
    try {
      setSelectedId(feedbackId);
      setDetailLoading(true);

      const isApproved = statusHint === "approved" || activeTab === 2;
      const targetTab = isApproved ? 2 : 1;
      setActiveTab(targetTab);

      const prefix = isApproved ? "/feedback/approved/" : "/feedback/pending/";
      window.history.pushState(null, "", `${prefix}${feedbackId}`);

      const detail = await fetchFeedbackDetail(feedbackId);
      setSelectedDetail(detail);
    } catch (err) {
      console.error("Failed to load feedback detail:", err);
      setToast({
        open: true,
        message: "Failed to load feedback details.",
        severity: "error",
      });
    } finally {
      setDetailLoading(false);
    }
  }, [activeTab]);

  // Initial load and URL parsing
  useEffect(() => {
    loadStats();
    const path = window.location.pathname;

    if (path.includes("/feedback/approved")) {
      setActiveTab(2);
      const match = path.match(/\/feedback\/approved\/([^/?#]+)/);
      if (match && match[1]) {
        handleSelectItem(match[1], "approved");
      }
    } else if (path.includes("/feedback/pending")) {
      setActiveTab(1);
      const match = path.match(/\/feedback\/pending\/([^/?#]+)/);
      if (match && match[1]) {
        handleSelectItem(match[1], "pending");
      }
    } else {
      setActiveTab(0);
    }
  }, [loadStats, handleSelectItem]);

  // Reload lists when tabs/search change
  useEffect(() => {
    if (activeTab === 1) {
      loadPending();
    } else if (activeTab === 2) {
      loadApproved();
    }
  }, [activeTab, loadPending, loadApproved]);

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
    setActiveTab(newIndex);
    setSelectedId(null);
    setSelectedDetail(null);

    let targetPath = newPath;
    if (!targetPath) {
      if (newIndex === 0) targetPath = "/feedback/dashboard";
      else if (newIndex === 1) targetPath = "/feedback/pending";
      else if (newIndex === 2) targetPath = "/feedback/approved";
    }
    window.history.pushState(null, "", targetPath);
  };

  const handleBackToList = () => {
    setSelectedId(null);
    setSelectedDetail(null);
    const basePath = activeTab === 2 ? "/feedback/approved" : "/feedback/pending";
    window.history.pushState(null, "", basePath);
  };

  const handleActionComplete = (action, feedbackId) => {
    loadStats();
    loadPending();
    loadApproved();
    handleBackToList();

    if (action === "approved") {
      setToast({
        open: true,
        message: `Feedback ${feedbackId} approved! Stored in vector memory & DPO training dataset.`,
        severity: "success",
      });
    } else if (action === "rejected") {
      setToast({
        open: true,
        message: `Feedback ${feedbackId} rejected.`,
        severity: "info",
      });
    }
  };

  return (
    <div className="w-screen h-screen flex flex-col bg-bg-default overflow-hidden">
      {/* 1. Header */}
      <div className="h-16 flex-shrink-0 border-b border-border-theme bg-bg-header">
        <FeedbackHeader
          onNavigateToChat={handleNavChat}
          userProfile={userProfile}
          onLogout={onLogout}
        />
      </div>

      {/* 2. Main Content Container */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="max-w-7xl mx-auto h-full flex flex-col">
          <div className="flex flex-col md:flex-row gap-6 items-start min-h-full">
            {/* Left Feedback Navigation Sidebar (Dashboard, Pending, Approved) */}
            {!selectedId && (
              <FeedbackSidebar
                activeTab={activeTab}
                onTabChange={handleTabChange}
                stats={stats}
              />
            )}

            {/* Right Main Content Area */}
            <div className="flex-1 w-full min-w-0">
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
                    totalCount={stats.pending_count}
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
                  totalCount={stats.approved_count}
                />
              )}
            </div>
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
