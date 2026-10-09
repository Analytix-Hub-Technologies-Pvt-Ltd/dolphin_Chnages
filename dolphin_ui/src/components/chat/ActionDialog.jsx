import { Dialog, Box, Typography, Button } from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";

const ActionDialog = ({
  open,
  mode = "confirm", // "confirm" | "success" | "error"
  message,
  onClose,
  onConfirm,
}) => {
  const isConfirm = mode === "confirm";
  const isSuccess = mode === "success";
  const isError = mode === "error";

  return (
    <Dialog
      open={open}
      onClose={onClose}
      BackdropProps={{
        sx: {
          backdropFilter: "blur(6px)",   // 🔥 background blur
          backgroundColor: "rgba(0,0,0,0.2)", // slight overlay
        },
      }}
      PaperProps={{
        sx: {
          borderRadius: 4,
          width: 380,                    // 🔼 bigger width
          height: isConfirm ? 240 : 300, // 🔼 bigger height
          p: 4,
          textAlign: "center",
        },
      }}
    >
      <Box
        display="flex"
        flexDirection="column"
        alignItems="center"
        justifyContent="center"
        height="100%"
        gap={2.5} // 🔼 more spacing
      >
        {/* ICON */}
        {isSuccess && (
          <CheckCircleIcon sx={{ fontSize: 64, color: "primary.main" }} />
        )}
        {isError && (
          <ErrorIcon sx={{ fontSize: 64, color: "primary.main" }} /> // 🔵 no red
        )}

        {/* TITLE */}
        <Typography variant="h5" fontWeight={700}>
          {isConfirm
            ? "Delete Chat?"
            : isSuccess
              ? "Success"
              : "Error"}
        </Typography>

        {/* MESSAGE */}
        <Typography variant="body1" color="text.secondary">
          {message ||
            (isConfirm
              ? "Are you sure you want to permanently delete this session?"
              : "")}
        </Typography>

        {/* ACTION BUTTONS */}
        {isConfirm ? (
          <Box display="flex" gap={2} mt={1}>
            <Button
              variant="outlined"
              onClick={onClose}
              sx={{ px: 3, borderRadius: 2 }}
            >
              Cancel
            </Button>

            <Button
              variant="contained"
              onClick={onConfirm}
              sx={{
                px: 3,
                borderRadius: 2,
                bgcolor: "primary.main",   // 🔵 blue button
                "&:hover": {
                  bgcolor: "primary.dark",
                },
              }}
            >
              Yes, Delete
            </Button>
          </Box>
        ) : (
          <Button
            variant="contained"
            size="medium"
            onClick={onClose}
            sx={{
              mt: 2,
              px: 4,
              borderRadius: 2,
              bgcolor: "primary.main",
              "&:hover": {
                bgcolor: "primary.dark",
              },
            }}
          >
            OK
          </Button>
        )}
      </Box>
    </Dialog>
  );
};

export default ActionDialog;