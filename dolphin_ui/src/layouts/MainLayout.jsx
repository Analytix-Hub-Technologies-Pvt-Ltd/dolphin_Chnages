import React from "react";
import { Grid, useMediaQuery, useTheme } from "@mui/material";

const MainLayout = ({ header, leftPanel, contentPanel }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const isTab = useMediaQuery(theme.breakpoints.down("md"));

  return (
    <Grid container height="100vh" width="100vw" flexDirection="column">
      <Grid item xs={12} sx={{ height: "10vh" }}>
        {header}
      </Grid>

      <Grid item xs={12} sx={{ height: "90vh", display: "flex" }}>
        {!isMobile && !isTab && leftPanel && leftPanel}
        
        {contentPanel}
      </Grid>
    </Grid>
  );
};

export default MainLayout;
