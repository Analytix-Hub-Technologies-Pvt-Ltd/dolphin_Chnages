import { getFontSize } from "./fontScale";

const components = (fontLevel = 0) => ({
  MuiButton: {
    styleOverrides: {
      sizeSmall: {
        fontSize: getFontSize(12, fontLevel),
        padding: "4px 10px",
      },
      sizeMedium: {
        fontSize: getFontSize(14, fontLevel),
        padding: "6px 10px",
      },
      sizeLarge: {
        fontSize: getFontSize(16, fontLevel),
        padding: "8px 22px",
      },
    },
  },
});

export default components;
