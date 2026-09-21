import React, { useState, useEffect, useCallback } from "react";
import { RefreshCw, AlertTriangle, X } from "lucide-react";

import DashboardHeader from "./DashboardHeader";
import DashboardKpiCards from "./DashboardKpiCards";
import FeedbackTrendChart from "./FeedbackTrendChart";
import IssueCategoryChart from "./IssueCategoryChart";
import ResolutionStatusChart from "./ResolutionStatusChart";
import ReviewerResolutionTable from "./ReviewerResolutionTable";
import PendingAgingTable from "./PendingAgingTable";
import RecentFeedbackActivity from "./RecentFeedbackActivity";
import CompanyAnalyticsTable from "./CompanyAnalyticsTable";
import ShipTypeAnalyticsTable from "./ShipTypeAnalyticsTable";

import { fetchFeedbackDashboard, formatErrorMessage } from "../../api/feedbackApi";

const FeedbackDashboard = ({
  onNavigateTab,
  onSelectItem,
  userProfile,
}) => {
  // Filter state
  const [filters, setFilters] = useState({
    dateRange: "30d",
    fromDate: "",
    toDate: "",
    companyId: userProfile?.company_id || "all",
    shipType: "all",
    status: "all",
    feedbackType: "all",
  });

  // Dashboard state
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Toast notifications
  const [toast, setToast] = useState({ open: false, message: "", severity: "info" });

  const loadDashboard = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchFeedbackDashboard({
        dateRange: filters.dateRange,
        fromDate: filters.fromDate || null,
        toDate: filters.toDate || null,
        companyId: filters.companyId !== "all" ? filters.companyId : null,
        shipType: filters.shipType !== "all" ? filters.shipType : null,
        status: filters.status !== "all" ? filters.status : null,
        feedbackType: filters.feedbackType !== "all" ? filters.feedbackType : null,
      });
      setDashboardData(data);
    } catch (err) {
      console.error("Failed to fetch dashboard data:", err);
      setError(formatErrorMessage(err, "Unable to load feedback analytics."));
      setToast({
        open: true,
        message: "Failed to load feedback analytics.",
        severity: "error",
      });
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  // Auto-dismiss toast
  useEffect(() => {
    if (toast.open) {
      const timer = setTimeout(() => {
        setToast((prev) => ({ ...prev, open: false }));
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [toast.open]);

  const handleCategoryDrilldown = (categoryId) => {
    if (onNavigateTab) {
      onNavigateTab(1, `/feedback/pending?feedback_type=${encodeURIComponent(categoryId)}`);
    }
  };

  const handleAgingDrilldown = () => {
    if (onNavigateTab) {
      onNavigateTab(1, `/feedback/pending`);
    }
  };

  const handleViewAllPending = () => {
    if (onNavigateTab) {
      onNavigateTab(1, "/feedback/pending");
    }
  };

  const summary = dashboardData?.summary || {};
  const trend = dashboardData?.trend || [];
  const categories = dashboardData?.categories || [];
  const reviewerResolution = dashboardData?.reviewer_resolution || [];
  const aging = dashboardData?.aging || [];
  const recentFeedback = dashboardData?.recent_feedback || [];
  const companySummary = dashboardData?.company_summary || [];
  const shipTypeSummary = dashboardData?.ship_type_summary || [];
  const resolutionData = dashboardData?.resolution_status || [];
  const filterOptions = dashboardData?.filter_options || {};

  const dateRangeLabel =
    filters.dateRange === "today"
      ? "Today"
      : filters.dateRange === "7d"
      ? "Last 7 Days"
      : filters.dateRange === "30d"
      ? "Last 30 Days"
      : filters.dateRange === "90d"
      ? "Last 90 Days"
      : "Selected Period";

  return (
    <div className="w-full pb-10 space-y-6">
      {/* 1. Header & Filters */}
      <DashboardHeader
        filters={filters}
        onFilterChange={setFilters}
        onRefresh={loadDashboard}
        loading={loading}
        filterOptions={filterOptions}
      />

      {/* Global Error Alert with Retry */}
      {error && (
        <div className="flex items-center justify-between p-4 rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400 text-xs">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={loadDashboard}
            className="inline-flex items-center gap-1 font-semibold px-2.5 py-1 rounded-lg border border-red-300 dark:border-red-800 hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry
          </button>
        </div>
      )}

      {/* 2. Top 6 KPI Cards */}
      <DashboardKpiCards summary={summary} loading={loading} />

      {/* 3. Charts & Analytics Grid */}
      <div className="space-y-6">
        {/* Row 1: Trend Chart */}
        <div>
          <FeedbackTrendChart
            trendData={trend}
            loading={loading}
            error={error}
            onRetry={loadDashboard}
            dateRangeLabel={dateRangeLabel}
          />
        </div>

        {/* Row 2: Issue Categories & Resolution Status (or Aging) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <IssueCategoryChart
            categories={categories}
            loading={loading}
            onCategoryClick={handleCategoryDrilldown}
          />

          {resolutionData.length > 0 ? (
            <ResolutionStatusChart
              resolutionData={resolutionData}
              loading={loading}
              onNavigateTab={onNavigateTab}
            />
          ) : (
            <PendingAgingTable
              agingData={aging}
              loading={loading}
              onAgingBucketClick={handleAgingDrilldown}
            />
          )}
        </div>

        {/* Row 3: Issues Resolved by SMEs & Aging Table (if resolution shown above) or Company Breakdown */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {resolutionData.length > 0 ? (
            <PendingAgingTable
              agingData={aging}
              loading={loading}
              onAgingBucketClick={handleAgingDrilldown}
            />
          ) : (
            <ReviewerResolutionTable
              reviewerData={reviewerResolution}
              loading={loading}
            />
          )}

          <CompanyAnalyticsTable
            companyData={companySummary}
            loading={loading}
          />
        </div>

        {/* Row 4: Reviewer Resolution (if resolutionData displayed above) */}
        {resolutionData.length > 0 && reviewerResolution.length > 0 && (
          <div>
            <ReviewerResolutionTable
              reviewerData={reviewerResolution}
              loading={loading}
            />
          </div>
        )}

        {/* Row 5: Ship Type Analytics */}
        {shipTypeSummary.length > 0 && (
          <div>
            <ShipTypeAnalyticsTable
              shipTypeData={shipTypeSummary}
              loading={loading}
            />
          </div>
        )}

        {/* Row 6: Recent Feedback Activity */}
        <div>
          <RecentFeedbackActivity
            recentItems={recentFeedback}
            loading={loading}
            onSelectItem={onSelectItem}
            onViewAllPending={handleViewAllPending}
          />
        </div>
      </div>

      {/* Toast Notification */}
      {toast.open && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 px-4 py-2.5 rounded-xl shadow-lg bg-slate-900 text-white text-xs font-medium animate-in fade-in duration-200">
          <span>{toast.message}</span>
          <button
            type="button"
            onClick={() => setToast((prev) => ({ ...prev, open: false }))}
            className="p-1 text-slate-400 hover:text-white"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};

export default React.memo(FeedbackDashboard);
