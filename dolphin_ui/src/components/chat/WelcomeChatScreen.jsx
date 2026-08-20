import { Box, Typography } from "@mui/material";
import React from "react";
import DolphinIconB from "../../assets/images/dolphin_b.png";
import DolphinIconW from "../../assets/images/dolphin_w.png";
import ShipIconB from "../../assets/images/ship.png";
import ShipIconW from "../../assets/images/ship_w.png";
import { useThemeMode } from "../../context/ThemeModeContext";
import {
  getWelcomeMaxWidth,
  getDescriptionWidth,
  getDescriptionGap,
} from "../../theme/layoutScale";

const WelcomeChatScreen = () => {
  const { mode, fontLevel } = useThemeMode();
  return (
    <Box
      sx={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Box
        sx={{
          backgroundColor: "background.paper",
          borderRadius: 8,
          px: { xs: 1,sm:4, md: 5 },
          py: { xs: 1, sm:3,md: 3 },
          // minWidth:500,
          maxWidth: { xs: "90%", sm:"60%", md: getWelcomeMaxWidth(500, fontLevel) },
          textAlign: "center",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: getDescriptionGap(fontLevel),
          border: "1px solid",
          borderColor: "primary.main",
        }}
      >
        {/* Icons */}
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 2,
          }}
        >
          <Box
            component="img"
            src={mode === "dark" ? DolphinIconW : DolphinIconB}
            alt="Dolphin"
            sx={{ width: 60, height: 60 }}
          />
          <Box
            component="img"
            src={mode === "dark" ? ShipIconW : ShipIconB}
            alt="Cap"
            sx={{ width: 40, height: 40 }}
          />
        </Box>

        {/* Title */}
        <Box
          sx={{
            display: "flex",
            gap: 1.5,
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          <Typography
            variant="h3"
            sx={{ fontWeight: 700, color: "text.heading1" }}
          >
            Dolphin
          </Typography>
          <Typography
            variant="h3"
            sx={{ fontWeight: 700, color: "text.heading1" }}
          >
            |
          </Typography>
          <Typography
            variant="h3"
            sx={{ fontWeight: 700, color: "primary.main" }}
          >
            AI
          </Typography>
        </Box>

        {/* Subtitle */}
        <Typography
          variant="signupPageh2"
          sx={{
            fontWeight: 400,
            color: "text.heading1",
          }}
        >
          How can I{" "}
          <Box
            component="span"
            sx={(theme) => ({
              background: `linear-gradient(90deg, ${theme.palette.text.heading1}, ${theme.palette.text.heading2})`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              fontWeight: 400,
              paddingLeft: "5px", // 👈 clears the h
              marginLeft: "-5px",
            })}
          >
            help
          </Box>{" "}
          you today?
        </Typography>

        {/* Description */}
        <Typography
          variant="h6"
          sx={{
            fontWeight: 500,
            width: { xs: "96%", md: getDescriptionWidth(fontLevel) },
            color: "text.smallheading",
            lineHeight: 1.4,
          }}
        >
          You can ask me anything. I can provide summaries, key takeaways and
          knowledge checks, as well as help you locate specific videos from our
          library and recommend training courses to enhance your skills.
        </Typography>
      </Box>
    </Box>
  );
};

export default WelcomeChatScreen;
