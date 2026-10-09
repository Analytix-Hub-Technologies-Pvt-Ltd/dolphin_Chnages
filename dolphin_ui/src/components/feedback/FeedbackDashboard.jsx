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

  const rawSummary = dashboardData?.summary || dashboardData?.kpis || {};
  const summary = {
    total_feedback: rawSummary.total_feedback ?? rawSummary.total_count ?? 0,
    positive_feedback: rawSummary.positive_feedback ?? rawSummary.positive_count ?? 0,
    negative_feedback: rawSummary.negative_feedback ?? rawSummary.negative_count ?? 0,
    pending_issues: rawSummary.pending_issues ?? rawSummary.pending_count ?? 0,
    approved_issues: rawSummary.approved_issues ?? rawSummary.approved_count ?? 0,
    rejected_issues: rawSummary.rejected_issues ?? rawSummary.rejected_count ?? 0,
    satisfaction_rate: rawSummary.satisfaction_rate ?? 0,
  };

  const trend = dashboardData?.trend || [];

  const rawCategories = dashboardData?.categories || dashboardData?.category_breakdown || [];
  const categories = Array.isArray(rawCategories)
    ? rawCategories.map((c) => ({
        id: c.id || c.category,
        label: c.label || (c.category ? c.category.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase()) : "Other"),
        count: c.count || 0,
        percentage: c.percentage || 0,
      }))
    : [];

  const rawResolution = dashboardData?.resolution_status;
  const resolutionData = Array.isArray(rawResolution)
    ? rawResolution
    : rawResolution && typeof rawResolution === "object"
    ? Object.entries(rawResolution).map(([status, count]) => ({
        status,
        count: Number(count) || 0,
        percentage: summary.total_feedback > 0 ? ((Number(count) / summary.total_feedback) * 100).toFixed(1) : "0",
      }))
    : [];

  const rawAging = dashboardData?.aging || dashboardData?.aging_buckets;
  const aging = Array.isArray(rawAging)
    ? rawAging
    : rawAging && typeof rawAging === "object"
    ? [
        { bucket: "< 24 Hours", count: rawAging.under_24h || 0, is_oldest: false },
        { bucket: "1 - 3 Days", count: rawAging.days_1_3 || 0, is_oldest: false },
        { bucket: "4 - 7 Days", count: rawAging.days_4_7 || 0, is_oldest: false },
        { bucket: "> 7 Days", count: rawAging.over_7d || 0, is_oldest: true },
      ]
    : [];

  const rawReviewers = dashboardData?.reviewer_resolution || dashboardData?.reviewer_stats || [];
  const reviewerResolution = Array.isArray(rawReviewers)
    ? rawReviewers.map((r) => ({
        reviewer: r.reviewer || r.reviewed_by || "Admin",
        approved: r.approved || 0,
        rejected: r.rejected || 0,
        total_resolved: r.total_resolved || r.total || (r.approved || 0) + (r.rejected || 0),
      }))
    : [];

  const recentFeedback = dashboardData?.recent_feedback || dashboardData?.recent_activity || [];

  const rawCompany = dashboardData?.company_summary || dashboardData?.company_analytics || [];
  const companySummary = Array.isArray(rawCompany)
    ? rawCompany.map((c) => ({
        company_id: c.company_id || c.company || "Global",
        total: c.total || 0,
        positive: c.positive || 0,
        negative: c.negative || ((c.pending || 0) + (c.approved || 0) + (c.rejected || 0)),
        pending: c.pending || 0,
        approved: c.approved || 0,
        satisfaction_rate: c.total > 0 ? Math.round(((c.positive || 0) / c.total) * 100) : 100,
      }))
    : [];

  const rawShip = dashboardData?.ship_type_summary || dashboardData?.ship_analytics || [];
  const shipTypeSummary = Array.isArray(rawShip)
    ? rawShip.map((s) => ({
        ship_type: s.ship_type || "General",
        total: s.total || 0,
        positive: s.positive || 0,
        negative: s.negative || ((s.pending || 0) + (s.approved || 0)),
        pending: s.pending || 0,
        approved: s.approved || 0,
        satisfaction_rate: s.total > 0 ? Math.round(((s.positive || 0) / s.total) * 100) : 100,
      }))
    : [];

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
    <div style={{ width: "100%", paddingBottom: 40, display: "flex", flexDirection: "column" }}>
      {/* 1. Header & Filters */}
      <DashboardHeader
        filters={filters}
        onFilterChange={setFilters}
        onRefresh={loadDashboard}
        loading={loading}
        availableCompanies={filterOptions.companies || []}
        availableShipTypes={filterOptions.ship_types || []}
      />

      {/* Global Error Alert with Retry */}
      {error && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "12px 16px",
            borderRadius: 12,
            border: "1px solid rgba(220, 38, 38, 0.3)",
            backgroundColor: "rgba(220, 38, 38, 0.08)",
            color: "var(--fb-danger)",
            fontSize: 12,
            marginBottom: 20,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <AlertTriangle style={{ width: 16, height: 16, flexShrink: 0 }} />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={loadDashboard}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontWeight: 600,
              padding: "4px 10px",
              borderRadius: 8,
              border: "1px solid rgba(220, 38, 38, 0.3)",
              backgroundColor: "transparent",
              color: "var(--fb-danger)",
              cursor: "pointer",
            }}
          >
            <RefreshCw style={{ width: 14, height: 14 }} />
            Retry
          </button>
        </div>
      )}

      {/* 2. Top 6 KPI Cards (3x2 Grid) */}
      <DashboardKpiCards summary={summary} loading={loading} />

      {/* 3. Charts & Analytics Grid */}
      <div style={{ display: "flex", flexDirection: "column", gap: 0, width: "100%" }}>
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

        {/* Row 2: Issue Categories & Resolution Status (or Aging) in 2 Equal Columns */}
        <div
          className="fb-2col-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
            gap: 20,
            marginBottom: 20,
            width: "100%",
            boxSizing: "border-box",
          }}
        >
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
        <div
          className="fb-2col-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
            gap: 20,
            marginBottom: 20,
            width: "100%",
            boxSizing: "border-box",
          }}
        >
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
          <div style={{ marginBottom: 20 }}>
            <ReviewerResolutionTable
              reviewerData={reviewerResolution}
              loading={loading}
            />
          </div>
        )}

        {/* Row 5: Ship Type Analytics */}
        {shipTypeSummary.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <ShipTypeAnalyticsTable
              shipTypeData={shipTypeSummary}
              loading={loading}
            />
          </div>
        )}

        {/* Row 6: Recent Feedback Activity */}
        <div style={{ marginBottom: 20 }}>
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
