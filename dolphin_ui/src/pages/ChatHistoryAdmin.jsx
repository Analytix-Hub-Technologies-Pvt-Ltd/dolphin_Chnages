import React, { useState, useRef, useEffect } from "react";
import {
  Box,
  Container,
  Typography,
  Button,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Stack,
  Pagination,
  useTheme,
  useMediaQuery,
  IconButton,
  Drawer,
  CircularProgress,
  Snackbar,
  Alert,
} from "@mui/material";
import VisibilityIcon from "@mui/icons-material/Visibility";
import ArrowBackIosNewIcon from "@mui/icons-material/ArrowBackIosNew";
import CloseIcon from "@mui/icons-material/Close";
import { useNavigate } from "react-router-dom";
import { getChatHistory, getChatSession, clearChatHistoryCache } from "../api/chatHistoryCache";
import DolphinIconW from "../assets/images/dolphin_w.png";
import DolphinIconB from "../assets/images/dolphin_b.png";

const ROWS_PER_PAGE = 10;

const MainLoader = () => (
  <Box
    sx={{
      flex: 1,
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      alignItems: "center",
      gap: 2,
      minHeight: 280,
    }}
  >
    <Box
      component="img"
      src={DolphinIconW}
      alt="Loading..."
      sx={{
        width: 80,
        height: 80,
        animation: "swimCenter 2s ease-in-out infinite",
        "@keyframes swimCenter": {
          "0%": { transform: "translateY(0px) rotate(0deg)" },
          "25%": { transform: "translateY(-15px) rotate(-10deg)" },
          "50%": { transform: "translateY(0px) rotate(0deg)" },
          "75%": { transform: "translateY(15px) rotate(10deg)" },
          "100%": { transform: "translateY(0px) rotate(0deg)" },
        },
      }}
    />
    <Typography
      variant="body1"
      sx={{
        color: "text.secondary",
        fontWeight: 600,
        animation: "pulseText 2s infinite ease-in-out",
        "@keyframes pulseText": {
          "0%, 100%": { opacity: 0.5 },
          "50%": { opacity: 1 },
        },
      }}
    >
      Loading chat history...
    </Typography>
  </Box>
);

const ChatHistoryAdmin = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));

  const [sessionDate, setSessionDate] = useState("");
  const [studentName, setStudentName] = useState("");
  const [chatRows, setChatRows] = useState([]);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const detailRequest = useRef(0);
  useEffect(() => () => { detailRequest.current += 1; }, []);
  const [totalRows, setTotalRows] = useState(0);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);

  const [snackbarMessage, setSnackbarMessage] = useState("");
  const [snackbarSeverity, setSnackbarSeverity] = useState("success");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [sessionDetails, setSessionDetails] = useState(null);
  const [sessionLoading, setSessionLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const timer = setTimeout(async () => {
      const fetchChatHistory = async () => {
        setLoading(true);

        try {
          const query = {
            limit: ROWS_PER_PAGE,
            offset: (currentPage - 1) * ROWS_PER_PAGE,
          };

          if (sessionDate) query.session_date = sessionDate;
          if (studentName) query.student_name = studentName;

          const data = await getChatHistory(query);

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

    }, 400);

    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [sessionDate, studentName, currentPage, refreshVersion]);

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
    setSelectedSessionId(row.session_id);
    setDrawerOpen(true);
    setSessionLoading(true);
    setSessionDetails(null);

    const requestId = ++detailRequest.current;
    getChatSession(row).then((data) => {
      if (requestId === detailRequest.current) setSessionDetails(data);
    }).catch((err) => {
      if (requestId !== detailRequest.current) return;
      setSnackbarMessage(err.message || "Failed to load session details");
      setSnackbarSeverity("error");
    }).finally(() => {
      if (requestId === detailRequest.current) setSessionLoading(false);
    });
  };

  const handlePageChange = (event, value) => {
    setCurrentPage(value);
  };

  return (
    <Box
      sx={{
        minHeight: "100%",
        bgcolor: theme.palette.background.default,
        py: 3,
      }}
    >
      <Container maxWidth="lg">
        <Paper
          elevation={0}
          sx={{
            bgcolor: theme.palette.background.paper,
            p: 3,
            mb: 3,
            borderRadius: 2,
            border: `1px solid ${theme.palette.divider || theme.palette.background.grey}`,
          }}
        >
          <Stack
            direction={isMobile ? "column" : "row"}
            spacing={2}
            alignItems={isMobile ? "stretch" : "flex-end"}
          >
            <TextField
              label="Session Date"
              type="date"
              value={sessionDate}
              onChange={(e) => {
                setSessionDate(e.target.value);
                setCurrentPage(1);
              }}
              InputLabelProps={{ shrink: true }}
              sx={{ minWidth: isMobile ? "100%" : 220 }}
            />

            <TextField
              label="Student Name"
              value={studentName}
              onChange={(e) => {
                setStudentName(e.target.value);
                setCurrentPage(1);
              }}
              placeholder="Enter student name"
              sx={{ minWidth: isMobile ? "100%" : 220 }}
            />

            <Button
              variant="outlined"
              onClick={handleReset}
              sx={{
                borderRadius: 1,
                textTransform: "none",
                px: 3,
              }}
            >
              Reset
            </Button>
            <Button
              variant="outlined"
              disabled={loading}
              onClick={() => {
                clearChatHistoryCache();
                setChatRows([]);
                setRefreshVersion((value) => value + 1);
              }}
              sx={{ textTransform: "none" }}
            >
              Refresh
            </Button>
          </Stack>

          <Typography
            variant="body2"
            sx={{
              mt: 2,
              color: theme.palette.text.secondary,
            }}
          >
            {!loading && `Showing ${chatRows.length > 0 ? (currentPage - 1) * ROWS_PER_PAGE + 1 : 0}-${Math.min(currentPage * ROWS_PER_PAGE, totalRows)} of ${totalRows} results`}
          </Typography>
        </Paper>

        <Paper
          elevation={0}
          sx={{
            bgcolor: theme.palette.background.paper,
            borderRadius: 2,
            border: `1px solid ${theme.palette.divider || theme.palette.background.grey}`,
            overflow: "hidden",
          }}
        >
          {loading ? (
            <MainLoader />
          ) : (
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow
                    sx={{
                      bgcolor: theme.palette.mode === "dark"
                        ? theme.palette.background.light
                        : theme.palette.background.lightblue1,
                    }}
                  >
                    <TableCell sx={{ fontWeight: 600, color: theme.palette.text.primary }}>
                      Student Name
                    </TableCell>
                    <TableCell sx={{ fontWeight: 600, color: theme.palette.text.primary }}>
                      Date
                    </TableCell>
                    <TableCell sx={{ fontWeight: 600, color: theme.palette.text.primary }}>
                      Chat Title
                    </TableCell>
                    <TableCell
                      align="center"
                      sx={{ fontWeight: 600, color: theme.palette.text.primary }}
                    >
                      Action
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {chatRows.length > 0 ? (
                    chatRows.map((row) => (
                      <TableRow
                        key={row.session_id}
                        sx={{
                          "&:nth-of-type(odd)": {
                            bgcolor: theme.palette.mode === "dark"
                              ? "transparent"
                              : theme.palette.background.light,
                          },
                          "&:hover": {
                            bgcolor: theme.palette.mode === "dark"
                              ? theme.palette.background.light
                              : theme.palette.background.lightblue1,
                          },
                          borderBottom: `1px solid ${theme.palette.divider || theme.palette.background.grey}`,
                        }}
                      >
                        <TableCell sx={{ color: theme.palette.text.primary }}>
                          {row.username}
                        </TableCell>
                        <TableCell sx={{ color: theme.palette.text.secondary }}>
                          {row.time ? new Date(row.time).toLocaleDateString("en-US", {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                          }) : "-"}
                        </TableCell>
                        <TableCell sx={{ color: theme.palette.text.primary }}>
                          {row.chat_title || "-"}
                        </TableCell>
                        <TableCell align="center">
                          <IconButton
                            size="small"
                            onClick={() => handleViewChat(row)}
                            sx={{
                              color: theme.palette.primary.main,
                              "&:hover": {
                                bgcolor: theme.palette.action?.hover || "rgba(16, 107, 163, 0.08)",
                              },
                            }}
                            title="View chat"
                          >
                            <VisibilityIcon fontSize="small" />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={4} align="center" sx={{ py: 4 }}>
                        <Typography variant="body2" color="text.secondary">
                          No chat history found
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>

        {totalPages > 1 && (
          <Box
            sx={{
              width: "100%",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              flexDirection: "column",
              mt: 3,
            }}
          >
            <Pagination
              count={totalPages}
              page={currentPage - 1}
              onChange={(event, value) => handlePageChange(event, value + 1)}
              color="primary"
              shape="rounded"
              sx={{
                display: "flex",
                justifyContent: "center",
                "& ul": {
                  flexDirection: "row",
                },
              }}
            />
          </Box>
        )}
      </Container>

      <Drawer
        anchor="right"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        PaperProps={{
          sx: {
            width: { xs: "100%", sm: 400, md: 500 },
            bgcolor: theme.palette.background.default,
            borderLeft: `1px solid ${theme.palette.divider || theme.palette.background.grey || "#ccc"}`,
          }
        }}
      >
        <Box sx={{ p: 2, display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: `1px solid ${theme.palette.divider || theme.palette.background.grey || "#ccc"}`, bgcolor: theme.palette.background.paper }}>
          <Typography variant="h6" sx={{ color: theme.palette.text.primary, fontWeight: 600 }}>
            {sessionDetails?.title || "Chat History"}
          </Typography>
          <IconButton onClick={() => setDrawerOpen(false)} sx={{ color: theme.palette.text.primary }}>
            <CloseIcon />
          </IconButton>
        </Box>

        <Box sx={{ p: 2, flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 2, bgcolor: theme.palette.background.default }}>
          {sessionLoading && (
            <Box sx={{ display: "flex", justifyContent: "center", mt: 4 }}>
              <CircularProgress />
            </Box>
          )}
          {!sessionLoading && sessionDetails?.messages?.map((msg) => {
            const isAssistant = msg.role === "assistant";
            const msgDate = new Date(msg.timestamp);
            const today = new Date();
            const isToday = msgDate.getDate() === today.getDate() &&
              msgDate.getMonth() === today.getMonth() &&
              msgDate.getFullYear() === today.getFullYear();
            const timeStr = msgDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const dateStr = msgDate.toLocaleDateString([], { month: 'short', day: 'numeric', year: msgDate.getFullYear() !== today.getFullYear() ? 'numeric' : undefined });
            const displayTime = isToday ? timeStr : `${dateStr}, ${timeStr}`;

            return (
              <Box
                key={msg.message_id}
                sx={{
                  display: "flex",
                  justifyContent: isAssistant ? "flex-end" : "flex-start",
                }}
              >
                <Box
                  sx={{
                    maxWidth: "80%",
                    p: 2,
                    borderRadius: 2,
                    bgcolor: isAssistant
                      ? theme.palette.primary.main
                      : theme.palette.mode === "dark" ? theme.palette.background.paper : "#e0e0e0",
                    color: isAssistant
                      ? theme.palette.primary.contrastText || "#fff"
                      : theme.palette.text.primary,
                    borderTopRightRadius: isAssistant ? 0 : undefined,
                    borderTopLeftRadius: !isAssistant ? 0 : undefined,
                  }}
                >
                  <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
                    {msg.content}
                  </Typography>
                  <Typography variant="caption" sx={{ display: "block", mt: 1, opacity: 0.7, textAlign: isAssistant ? "right" : "left" }}>
                    {displayTime}
                  </Typography>
                </Box>
              </Box>
            );
          })}
          {!sessionLoading && (!sessionDetails?.messages || sessionDetails.messages.length === 0) && (
            <Typography align="center" color="text.secondary" sx={{ mt: 4 }}>
              No messages found.
            </Typography>
          )}
        </Box>
      </Drawer>

      <Snackbar
        open={!!snackbarMessage}
        autoHideDuration={4000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbarSeverity} sx={{ width: '100%' }}>
          {snackbarMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ChatHistoryAdmin;
