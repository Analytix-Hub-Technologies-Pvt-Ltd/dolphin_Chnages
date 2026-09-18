import React, { useState, useEffect } from "react";
import { Eye, X, Loader2, ChevronLeft, ChevronRight, CheckCircle2, AlertCircle } from "lucide-react";
import { apiGet } from "../api/client";
import DolphinIconW from "../assets/images/dolphin_w.png";

const ROWS_PER_PAGE = 10;

const MainLoader = () => (
  <div className="flex-1 flex flex-col justify-center items-center gap-4 min-h-[280px]">
    <img
      src={DolphinIconW}
      alt="Loading..."
      className="w-20 h-20 animate-swim"
    />
    <p className="text-text-secondary font-semibold animate-pulse text-sm">
      Loading chat history...
    </p>
  </div>
);

const ChatHistoryAdmin = () => {
  const [sessionDate, setSessionDate] = useState("");
  const [studentName, setStudentName] = useState("");
  const [chatRows, setChatRows] = useState([]);
  const [totalRows, setTotalRows] = useState(0);
  const [loading, setLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);

  const [snackbarMessage, setSnackbarMessage] = useState("");
  const [snackbarSeverity, setSnackbarSeverity] = useState("success");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [sessionDetails, setSessionDetails] = useState(null);
  const [sessionLoading, setSessionLoading] = useState(false);

  useEffect(() => {
    const timer = setTimeout(async () => {
      let isMounted = true;
      const fetchChatHistory = async () => {
        setLoading(true);

        try {
          const query = {
            limit: ROWS_PER_PAGE,
            offset: (currentPage - 1) * ROWS_PER_PAGE,
          };

          if (sessionDate) query.session_date = sessionDate;
          if (studentName) query.student_name = studentName;

          const data = await apiGet("/sessions/", { query });

          if (!isMounted) return;

          if (Array.isArray(data)) {
            setChatRows(data);
            setTotalRows(data.length);
          } else if (data && typeof data === "object") {
            setChatRows(data.data || data.results || data.items || []);
            setTotalRows(data.total || data.total_count || data.count || 0);
          } else {
            setChatRows([]);
            setTotalRows(0);
          }
        } catch (err) {
          if (!isMounted) return;
          setChatRows([]);
          setTotalRows(0);
          setSnackbarMessage(err.message || "Failed to load chat history");
          setSnackbarSeverity("error");
        } finally {
          if (isMounted) {
            setLoading(false);
          }
        }
      };

      fetchChatHistory();

      return () => {
        isMounted = false;
      };
    }, 400);

    return () => clearTimeout(timer);
  }, [sessionDate, studentName, currentPage]);

  useEffect(() => {
    if (!snackbarMessage) return;
    const timer = setTimeout(() => {
      setSnackbarMessage("");
    }, 4000);
    return () => clearTimeout(timer);
  }, [snackbarMessage]);

  const totalPages = Math.ceil(totalRows / ROWS_PER_PAGE);

  const handleReset = () => {
    setSessionDate("");
    setStudentName("");
    setCurrentPage(1);
  };

  const handleCloseSnackbar = () => {
    setSnackbarMessage("");
  };

  const handleViewChat = (row) => {
    setDrawerOpen(true);
    setSessionLoading(true);
    setSessionDetails(null);

    setTimeout(async () => {
      try {
        const url = row.id
          ? `/sessions/${row.session_id}?user_id=${row.id}`
          : `/sessions/${row.session_id}`;

        const data = await apiGet(url);
        setSessionDetails(data);
      } catch (err) {
        setSnackbarMessage(err.message || "Failed to load session details");
        setSnackbarSeverity("error");
      } finally {
        setSessionLoading(false);
      }
    }, 0);
  };

  const renderPaginationButtons = () => {
    if (totalPages <= 1) return null;
    const pages = [];
    const maxVisiblePages = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);

    if (endPage - startPage + 1 < maxVisiblePages) {
      startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }

    return (
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
          disabled={currentPage === 1}
          className="p-2 rounded-lg border border-border-default bg-bg-paper text-text-primary hover:bg-bg-light disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
          aria-label="Previous page"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        {startPage > 1 && (
          <>
            <button
              type="button"
              onClick={() => setCurrentPage(1)}
              className="w-9 h-9 rounded-lg text-sm font-medium border border-border-default bg-bg-paper text-text-primary hover:bg-bg-light transition-colors cursor-pointer"
            >
              1
            </button>
            {startPage > 2 && <span className="px-1 text-text-secondary">...</span>}
          </>
        )}

        {Array.from({ length: endPage - startPage + 1 }, (_, i) => startPage + i).map((page) => (
          <button
            key={page}
            type="button"
            onClick={() => setCurrentPage(page)}
            className={`w-9 h-9 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
              currentPage === page
                ? "bg-primary text-white shadow-xs font-semibold"
                : "border border-border-default bg-bg-paper text-text-primary hover:bg-bg-light"
            }`}
          >
            {page}
          </button>
        ))}

        {endPage < totalPages && (
          <>
            {endPage < totalPages - 1 && <span className="px-1 text-text-secondary">...</span>}
            <button
              type="button"
              onClick={() => setCurrentPage(totalPages)}
              className="w-9 h-9 rounded-lg text-sm font-medium border border-border-default bg-bg-paper text-text-primary hover:bg-bg-light transition-colors cursor-pointer"
            >
              {totalPages}
            </button>
          </>
        )}

        <button
          type="button"
          onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
          disabled={currentPage === totalPages}
          className="p-2 rounded-lg border border-border-default bg-bg-paper text-text-primary hover:bg-bg-light disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
          aria-label="Next page"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    );
  };

  return (
    <div className="min-h-full w-full max-w-full overflow-x-hidden bg-bg-default py-6">
      <div className="w-full max-w-full px-4 sm:px-6 lg:px-8">
        {/* Filter Card */}
        <div className="bg-bg-paper p-6 mb-6 rounded-xl border border-border-default shadow-xs">
          <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-end">
            <div className="flex flex-col gap-1.5 min-w-full md:min-w-[220px]">
              <label className="text-xs font-medium text-text-secondary">
                Session Date
              </label>
              <input
                type="date"
                value={sessionDate}
                onChange={(e) => {
                  setSessionDate(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full px-3 py-2 border border-border-default rounded-lg bg-bg-default text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all"
              />
            </div>

            <div className="flex flex-col gap-1.5 min-w-full md:min-w-[220px]">
              <label className="text-xs font-medium text-text-secondary">
                Student Name
              </label>
              <input
                type="text"
                value={studentName}
                onChange={(e) => {
                  setStudentName(e.target.value);
                  setCurrentPage(1);
                }}
                placeholder="Enter student name"
                className="w-full px-3 py-2 border border-border-default rounded-lg bg-bg-default text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all placeholder:text-text-secondary/60"
              />
            </div>

            <button
              type="button"
              onClick={handleReset}
              className="px-6 py-2 rounded-lg border border-primary text-primary hover:bg-primary/10 transition-colors font-medium text-sm cursor-pointer self-stretch md:self-auto"
            >
              Reset
            </button>
          </div>

          <p className="mt-4 text-xs text-text-secondary">
            {!loading &&
              `Showing ${
                chatRows.length > 0 ? (currentPage - 1) * ROWS_PER_PAGE + 1 : 0
              }-${Math.min(currentPage * ROWS_PER_PAGE, totalRows)} of ${totalRows} results`}
          </p>
        </div>

        {/* Table Container */}
        <div className="bg-bg-paper rounded-xl border border-border-default overflow-hidden w-full max-w-full shadow-xs">
          {loading ? (
            <MainLoader />
          ) : (
            <div className="w-full max-w-full overflow-x-auto">
              <table className="w-full text-left border-collapse min-w-[600px]">
                <thead>
                  <tr className="bg-bg-lightblue1 dark:bg-bg-light border-b border-border-default">
                    <th className="py-3 px-4 text-sm font-semibold text-text-primary">
                      Student Name
                    </th>
                    <th className="py-3 px-4 text-sm font-semibold text-text-primary">
                      Date
                    </th>
                    <th className="py-3 px-4 text-sm font-semibold text-text-primary">
                      Chat Title
                    </th>
                    <th className="py-3 px-4 text-sm font-semibold text-text-primary text-center w-20">
                      Action
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-default">
                  {chatRows.length > 0 ? (
                    chatRows.map((row, idx) => (
                      <tr
                        key={row.session_id || idx}
                        className={`transition-colors hover:bg-bg-lightblue1 dark:hover:bg-bg-light ${
                          idx % 2 === 1
                            ? "bg-bg-light/30 dark:bg-transparent"
                            : "bg-transparent"
                        }`}
                      >
                        <td className="py-3 px-4 text-sm text-text-primary font-medium">
                          {row.username || "-"}
                        </td>
                        <td className="py-3 px-4 text-sm text-text-secondary">
                          {row.time
                            ? new Date(row.time).toLocaleDateString("en-US", {
                                year: "numeric",
                                month: "short",
                                day: "numeric",
                              })
                            : "-"}
                        </td>
                        <td className="py-3 px-4 text-sm text-text-primary">
                          {row.chat_title || "-"}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <button
                            type="button"
                            onClick={() => handleViewChat(row)}
                            title="View chat"
                            aria-label="View chat"
                            className="p-1.5 rounded-lg text-primary hover:bg-primary/10 transition-colors inline-flex items-center justify-center cursor-pointer"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} className="py-12 text-center text-sm text-text-secondary">
                        No chat history found
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex justify-center items-center mt-6">
            {renderPaginationButtons()}
          </div>
        )}
      </div>

      {/* Slide-in Drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
            onClick={() => setDrawerOpen(false)}
          />

          {/* Drawer panel */}
          <aside className="relative z-10 w-full sm:w-[400px] md:w-[500px] h-full bg-bg-default border-l border-border-default shadow-2xl flex flex-col">
            {/* Header */}
            <div className="p-4 flex items-center justify-between border-b border-border-default bg-bg-paper">
              <h2 className="text-lg font-semibold text-text-primary truncate pr-2">
                {sessionDetails?.title || "Chat History"}
              </h2>
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                aria-label="Close drawer"
                className="p-1.5 rounded-lg text-text-primary hover:bg-bg-light transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Messages Body */}
            <div className="p-4 flex-1 overflow-y-auto flex flex-col gap-3 bg-bg-default">
              {sessionLoading && (
                <div className="flex justify-center items-center h-48">
                  <Loader2 className="w-8 h-8 text-primary animate-spin" />
                </div>
              )}

              {!sessionLoading &&
                sessionDetails?.messages?.map((msg) => {
                  const isAssistant = msg.role === "assistant";
                  const msgDate = new Date(msg.timestamp);
                  const today = new Date();
                  const isToday =
                    msgDate.getDate() === today.getDate() &&
                    msgDate.getMonth() === today.getMonth() &&
                    msgDate.getFullYear() === today.getFullYear();
                  const timeStr = msgDate.toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  });
                  const dateStr = msgDate.toLocaleDateString([], {
                    month: "short",
                    day: "numeric",
                    year:
                      msgDate.getFullYear() !== today.getFullYear()
                        ? "numeric"
                        : undefined,
                  });
                  const displayTime = isToday ? timeStr : `${dateStr}, ${timeStr}`;

                  return (
                    <div
                      key={msg.message_id || msg.timestamp}
                      className={`flex ${
                        isAssistant ? "justify-end" : "justify-start"
                      }`}
                    >
                      <div
                        className={`max-w-[85%] px-2 py-1 sm:px-2.5 sm:py-1 rounded-xl shadow-xs text-xs sm:text-[13px] ${
                          isAssistant
                            ? "bg-primary text-white rounded-tr-xs"
                            : "bg-[#e2e8f0] dark:bg-bg-paper text-text-primary rounded-tl-xs border border-black/[0.04] dark:border-white/[0.06]"
                        }`}
                      >
                        <p className="whitespace-pre-wrap leading-snug m-0">
                          {msg.content}
                        </p>
                        <span
                          className={`block mt-0.5 text-[10px] opacity-70 ${
                            isAssistant ? "text-right" : "text-left"
                          }`}
                        >
                          {displayTime}
                        </span>
                      </div>
                    </div>
                  );
                })}

              {!sessionLoading &&
                (!sessionDetails?.messages ||
                  sessionDetails.messages.length === 0) && (
                  <p className="text-center text-sm text-text-secondary my-12">
                    No messages found.
                  </p>
                )}
            </div>
          </aside>
        </div>
      )}

      {/* Snackbar Toast */}
      {snackbarMessage && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2.5 px-4 py-3 rounded-xl shadow-lg border text-sm font-medium bg-bg-paper text-text-primary border-border-default">
          {snackbarSeverity === "error" ? (
            <AlertCircle className="w-5 h-5 text-red-500 shrink-0" />
          ) : (
            <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
          )}
          <span>{snackbarMessage}</span>
          <button
            type="button"
            onClick={handleCloseSnackbar}
            className="ml-2 p-1 text-text-secondary hover:text-text-primary rounded-md cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
};

export default ChatHistoryAdmin;
