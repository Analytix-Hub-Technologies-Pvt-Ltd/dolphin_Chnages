import {
  Box,
  Button,
  Paper,
  Stack,
  TextField,
  Typography,
  InputAdornment,
} from "@mui/material";
import { useState } from "react";
import { loginApi } from "../api/apiAuth";
import waveImg from "../assets/images/wave.png";
import dolphinImg from "../assets/images/dolphin_login.png";
import abstractBg from "../assets/images/abstract-login.png";
import dolphinBlack from "../assets/images/dolphin_b.png";
import DolphinWhite from "../assets/images/dolphin_w.png";
import LocalPostOfficeIcon from "@mui/icons-material/LocalPostOffice";
import HttpsIcon from "@mui/icons-material/Https";
import raindropImg from "../assets/images/Rain_drop.png";
import { useThemeMode } from "../context/ThemeModeContext";
import ForgotPasswordPopup from "./ForgotPasswordPopup";

export default function Login({ onLoginSuccess }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState({});
  const [openForgot, setOpenForgot] = useState(false);

  const { mode } = useThemeMode();

  const validate = () => {
    const newErrors = {};

    if (!email) newErrors.email = "Email is required";

    if (!password) newErrors.password = "Password is required";
    else if (password.length < 6)
      newErrors.password = "Password must be at least 6 characters";

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    try {
      const userId = await loginApi(email, password);
      onLoginSuccess(userId);
    } catch (error) {
      setErrors({
        form: error.message || "Something went wrong",
      });
    }
  };

  return (
    <Box
      sx={{
        height: "100vh",
        display: "flex",
        bgcolor: "background.default",
        overflow: "hidden",
        backgroundImage: `url(${abstractBg})`,
        backgroundRepeat: "no-repeat",
        backgroundPosition: "center",
        backgroundSize: "100% 100%",
      }}
    >
      <Box
        sx={{
          width: "50%",
          display: { xs: "none", md: "flex" },
          flexDirection: "column",
          justifyContent: "start",
          position: "relative",
        }}
      >
        <Box
          sx={{ display: "flex", gap: 1.5, alignItems: "center", ml: 3, mt: 3 }}
        >
          <Box
            component="img"
            src={mode === "dark" ? DolphinWhite : dolphinBlack}
            alt="dolphin"
            sx={{
              width: 80,
              height: 80,
            }}
          />
          <Typography variant="h1" fontWeight={700} color="text.main">
            Dolphin | AI
          </Typography>
        </Box>

        <Typography
          variant="signupPageh1"
          fontWeight={800}
          color="text.main"
          sx={{ ml: 3, lineHeight: "45px" }}
        >
          Your digital
          <br />
          shipmate –
        </Typography>

        <Typography
          variant="signupPageh2"
          color="text.main"
          sx={{ ml: 3, fontWeight: 500, lineHeight: "45px" }}
        >
          Intelligent guidance,
          <br />
          anytime, anywhere
        </Typography>

        <Box
          sx={{
            position: "absolute",
            bottom: "-100px",
            left: "-12%",
            width: "100%",
            height: 260,
            pointerEvents: "none",
            zIndex: 1,
            transform: "rotate(20deg)",
          }}
        >
          <Box
            component="img"
            src={dolphinImg}
            alt="dolphin"
            sx={{
              position: "absolute",
              width: 300,
              left: 0,
              bottom: 0,
            }}
          />

          <Box
            component="img"
            src={dolphinImg}
            alt="dolphin"
            sx={{
              position: "absolute",
              width: 160,
              left: 90,
              bottom: 20,
            }}
          />
        </Box>
      </Box>

      {/* ================= RIGHT SECTION ================= */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          width: { xs: "100%", md: "50%" },
          position: "relative",
          flexDirection: "column",
          justifyContent: "center",
        }}
      >
        <Box
          sx={{
            display: { xs: "flex", md: "none" },
            flexDirection: "column",
            alignItems: "center",
            mb: 3,
            textAlign: "center",
          }}
        >
          <Box sx={{ display: "flex", gap: 1.5, alignItems: "center", mt: 3 }}>
            <Box
              component="img"
              src={dolphinBlack}
              alt="dolphin"
              sx={{
                width: 60,
                height: 60,
              }}
            />
            <Typography variant="h4" fontWeight={700} color="text.main">
              Dolphin | AI
            </Typography>
          </Box>

          <Typography variant="h5" fontWeight={800} color="text.main">
            Your digital shipmate –
          </Typography>

          <Typography variant="body2" color="text.main" fontWeight={500}>
            Intelligent guidance, anytime, anywhere
          </Typography>
        </Box>
        <Paper
          sx={{
            width: { xs: "80%", sm: "70%", md: 400 },
            maxWidth: "100%",
            px: { xs: 2, sm: 3, md: 5 },
            pt: { xs: 2, sm: 3, md: 5 },
            pb: 1,
            borderRadius: 4,
            border: "1.5px solid",
            borderColor: "primary.main",
            position: "relative",
            zIndex: 2,
            mb: { xs: 8, md: "15%" },
            overflow: "visible",

            // marginBottom: "15%",
          }}
        >
          <Box
            component="img"
            src={raindropImg}
            alt="raindrop"
            sx={{
              position: "absolute",
              top: { xs: -60, md: -100 },
              left: { xs: -55, md: -95 },
              width: { xs: 120, md: 200 },
              pointerEvents: "none",
              zIndex: 3,
            }}
          />

          <Typography
            variant="h5"
            fontWeight={700}
            mb={1}
            sx={{ color: "text.main" }}
          >
            SIGN IN
          </Typography>

          <Typography
            variant="body2"
            sx={{ color: "text.smallheading" }}
            mb={{ sx: 1, md: 1.5 }}
            fontWeight={500}
          >
            Sign in to continue your smart conversations with our AI-powered
            chatbot.
          </Typography>

          <Box
            component="form"
            onSubmit={handleSubmit}
            sx={{ display: "flex", flexDirection: "column" }}
          >
            <Stack spacing={{ xs: 1, sm: 1.5 }}>
              <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}>
                <Typography
                  variant="body1"
                  sx={{
                    fontWeight: 600,
                    color: "text.heading1",
                  }}
                >
                  Email
                </Typography>
                <TextField
                  placeholder="Enter your email"
                  type="text"
                  fullWidth
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setErrors((prev) => ({ ...prev, form: null }));
                  }}
                  error={!!errors.email}
                  helperText={errors.email}
                  sx={{
                    height: { xs: 35, sm: 45 },
                    color: "text.placeholder1",
                    "& .MuiInputBase-root": {
                      height: { xs: 35, sm: 45 },
                      color: "text.placeholder1",
                    },
                    "& input": {
                      padding: "0px 0px",
                      fontSize: 14,
                      height: { xs: 35, sm: 45 },
                      bgcolor: "none",
                      color: "text.placeholder1",
                    },
                  }}
                  slotProps={{
                    input: {
                      startAdornment: (
                        <InputAdornment position="start">
                          <LocalPostOfficeIcon
                            sx={{ color: "text.placeholder1" }}
                          />
                        </InputAdornment>
                      ),
                    },
                  }}
                />
              </Box>

              <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}>
                <Typography
                  variant="body1"
                  sx={{ fontWeight: 600, color: "text.heading1" }}
                >
                  Password
                </Typography>
                <TextField
                  placeholder="Enter your password"
                  type="password"
                  fullWidth
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  error={!!errors.password}
                  helperText={errors.password}
                  sx={{
                    height: { xs: 35, sm: 45 },
                    color: "text.placeholder1",
                    "& .MuiInputBase-root": {
                      height: { xs: 35, sm: 45, color: "text.placeholder1" },
                    },
                    "& input": {
                      padding: "0px 0px",
                      fontSize: 14,
                      height: { xs: 35, sm: 45 },
                      color: "text.placeholder1",
                    },
                  }}
                  slotProps={{
                    input: {
                      startAdornment: (
                        <InputAdornment position="start">
                          <HttpsIcon sx={{ color: "text.placeholder1" }} />
                        </InputAdornment>
                      ),
                    },
                  }}
                />
              </Box>
            </Stack>

            <Box textAlign="right" my={1}>
              <Typography
                variant="h6"
                onClick={() => setOpenForgot(true)}
                sx={{
                  fontWeight: 600,
                  color: "primary.main",
                  cursor: "pointer",
                  "&:hover": {
                    textDecoration: "underline",
                  },
                }}
              >
                Forgot Password ?
              </Typography>
            </Box>

            {errors.form && (
              <Typography color="error" textAlign="center">
                {errors.form}
              </Typography>
            )}

            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="small"
              sx={{
                bgcolor: "text.main",
                py: 0.5,
                borderRadius: 2,
                mb: 1,
                color: "text.white",
              }}
            >
              SIGN IN
            </Button>

            <Typography
              variant="caption"
              sx={{
                color: "text.smallheading",
                textAlign: "center",
              }}
            >
              © 2025 Mariner Skills , LLC. All rights reserved
            </Typography>
          </Box>
        </Paper>
      </Box>

      <Box
        sx={{
          position: "absolute",
          bottom: 0,
          width: "100%",
          height: "200px",
          overflow: "hidden",
          pointerEvents: "none",
          zIndex: 0,
        }}
      >
        <Box
          component="img"
          src={waveImg}
          alt="wave"
          sx={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
        />
      </Box>

      <ForgotPasswordPopup
        open={openForgot}
        handleClose={() => setOpenForgot(false)}
      />
    </Box>
  );
}
