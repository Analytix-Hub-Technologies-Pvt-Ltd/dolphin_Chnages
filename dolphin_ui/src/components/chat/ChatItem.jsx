import { Box, Menu, MenuItem, Typography, useTheme } from "@mui/material";
import { Message } from "../../assets/svgIcons/message";
import { Threedot } from "../../assets/svgIcons/ThreeDots";
import { useState } from "react";
import { DeleteIcon } from "../../assets/svgIcons/DeleteIcon";
import { deleteSession } from "../../api/fetchApi";
import ActionDialog from "./ActionDialog";
import { saveSession } from "../../api/fetchApi";
import SaveAltIcon from "@mui/icons-material/SaveAlt";
import DoDisturbAltIcon from "@mui/icons-material/DoDisturbAlt";
import { Pin } from "../../assets/svgIcons/Pin";

export const ChatItem = ({
  title,
  active,
  onClick,
  sessionId,
  onDelete,
  tabType,
  isSaved,
  onToggleSave,
  isPinned,
  onTogglePin,
}) => {
  const theme = useTheme();
  const [anchorEl, setAnchorEl] = useState(null);

  const open = Boolean(anchorEl);

  const handleMenuOpen = (event) => {
    event.stopPropagation(); //  prevent chat click
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleDialogClose = () => {
    if (dialog.mode === "success" && dialog.message.includes("deleted")) {
      onDelete(sessionId);
    }

    setDialog((prev) => ({ ...prev, open: false }));
  };

  const handleConfirmDelete = async () => {
    try {
      await deleteSession(sessionId);

      setDialog({
        open: true,
        mode: "success",
        message: "Session deleted successfully",
      });
    } catch (err) {
      setDialog({
        open: true,
        mode: "error",
        message: "Failed to delete session",
      });
    }
  };

  const [dialog, setDialog] = useState({
    open: false,
    mode: "confirm",
    message: "",
  });

  const handleDeleteClick = (e) => {
    e.stopPropagation();
    setDialog({
      open: true,
      mode: "confirm",
    });
    handleMenuClose();
  };

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 1,
        py: 1,
        px: 1,
        borderRadius: 2,
        bgcolor: active ? "background.lightblue1" : "transparent",
        "&:hover": {
          bgcolor: "background.lightblue1",
        },
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-start",
          gap: 1,
          width: "70%",
          cursor: "pointer",
        }}
        onClick={onClick}
      >
        <Message size={22} color={theme.palette.text.main} />

        <Typography
          variant="body2"
          sx={{
            width: "80%",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            color: active ? "text.main" : "text.primary",
          }}
        >
          {title ? title : "New Chat"}
        </Typography>
      </Box>

      <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>
        {isPinned && (
          <Box
            sx={{
              width: 22,
              height: 22,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Pin size={16} color={"#FFAE00"} />
          </Box>
        )}
        <Box
          sx={{
            width: 22,
            height: 22,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: "50%",
            cursor: "pointer",
            "&:hover": {
              bgcolor: "text.placeholder1",
            },
          }}
          onClick={handleMenuOpen}
        >
          <Threedot size={22} color={theme.palette.text.menu} />
        </Box>
        <Menu
          anchorEl={anchorEl}
          open={open}
          onClose={handleMenuClose}
          anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
          transformOrigin={{ vertical: "top", horizontal: "right" }}
          PaperProps={{
            sx: {
              borderRadius: 2,
              minWidth: 140,
              border: "1px solid",
              borderColor: "primary.main",
              backgroundColor: "background.paper",
              marginLeft: 15,
            },
          }}
        >
          {/* ✅ ONLY FOR SAVED TAB */}
          {tabType === 1 && (
            <MenuItem
              onClick={async () => {
                handleMenuClose();

                try {
                  await saveSession(sessionId);

                  const updatedStatus = !isSaved;

                  onToggleSave?.(sessionId, updatedStatus);

                  setDialog({
                    open: true,
                    mode: "success",
                    message: updatedStatus
                      ? "Chat saved successfully"
                      : "Removed from saved chats",
                  });
                } catch (err) {
                  console.error("Save toggle failed:", err);
                }
              }}
              sx={{ display: "flex", gap: 1 }}
            >
              {isSaved ? (
                <DoDisturbAltIcon sx={{ fontSize: 18 }} />
              ) : (
                <SaveAltIcon sx={{ fontSize: 18 }} />
              )}

              {isSaved ? "Remove from Saved" : "Save Chat"}
            </MenuItem>
          )}

          {/* ✅ PIN OPTION */}
          <MenuItem
            onClick={(e) => {
              e.stopPropagation();
              handleMenuClose();
              onTogglePin?.(sessionId);
            }}
            sx={{ display: "flex", gap: 1 }}
          >
            {isPinned ? (
              <DoDisturbAltIcon sx={{ fontSize: 18 }} />
            ) : (
              <Pin size={18} color={theme.palette.text.primary} />
            )}
            {isPinned ? "Unpin Chat" : "Pin Chat"}
          </MenuItem>

          {/* ✅ ALWAYS SHOW DELETE */}
          <MenuItem
            sx={{ display: "flex", gap: 1 }}
            onClick={handleDeleteClick}
          >
            <DeleteIcon size={18} color={theme.palette.text.primary} />
            Delete
          </MenuItem>
        </Menu>
      </Box>

      <ActionDialog
        open={dialog.open}
        mode={dialog.mode}
        message={dialog.message}
        onClose={handleDialogClose}
        onConfirm={handleConfirmDelete}
      />
    </Box>
  );
};
