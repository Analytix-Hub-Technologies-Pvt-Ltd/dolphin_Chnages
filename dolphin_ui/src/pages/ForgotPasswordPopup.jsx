import {
  Dialog,
  DialogContent,
  DialogTitle,
  TextField,
  Button,
  Typography,
  Box,
  Alert,
} from "@mui/material";
import { useState } from "react";
import axios from "axios";
import dolphinBlack from "../assets/images/dolphin_b.png";
import DolphinWhite from "../assets/images/dolphin_w.png";
import { useThemeMode } from "../context/ThemeModeContext";

const APP_URL = process.env.REACT_APP_BASE_URL || "http://localhost:8000";

export default function ForgotPasswordPopup({ open, handleClose }) {
  const [email, setEmail] = useState("");
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const { mode } = useThemeMode();

  const handleSubmit = async () => {
    setLoading(true);
    try {
      await axios.post(`${APP_URL}/forgot-password`, {
        email: email,
      });
      setSuccess(true);
    } catch (err) {
      setError(true);
      console.error(err);
    }
    setLoading(false);
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      PaperProps={{
        sx: {
          borderRadius: 5,
          padding: 2,
          minWidth: 400,
        },
      }}
    >
      <DialogTitle sx={{ fontWeight: 700, color: "#1f6fa8" }}>
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            gap: 2,
            alignItems: "center",
          }}
        >
          <Box
            component="img"
            src={mode === "dark" ? DolphinWhite : dolphinBlack}
            alt="dolphin"
            sx={{
              width: 50,
              height: 50,
            }}
          />
          <Typography variant="h3" fontWeight={700} color="text.main">
            Dolphin | AI
          </Typography>
        </Box>
        {!success && (
          <Typography mb={2} mt={1} variant="h6" px={5} color="text.heading1">
            Enter your email or user ID to receive your new password.
          </Typography>
        )}
      </DialogTitle>

      <DialogContent >
        {success ? (
          <Alert severity="success">
            New password has been sent to your email.
          </Alert>
        ) : (
          <>
            <TextField
              fullWidth
              label="Email or User ID"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              sx={{ mt: 2, mb: 3 }}
            />
            {error && (
              <Alert severity="error" sx={{ mb: 3 }}>
                Failed to send password. Please try again.
              </Alert>
            )}

            <Box display="flex" justifyContent="center">
              <Button
                variant="contained"
                onClick={handleSubmit}
                disabled={loading}
                sx={{
                  background: "#1f6fa8",
                  borderRadius: "8px",
                  px: 4,
                  width: "100%",
                }}
              >
                Send Password
              </Button>
            </Box>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
