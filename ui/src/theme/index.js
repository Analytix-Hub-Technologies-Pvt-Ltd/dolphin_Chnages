import typography from "./typography";
import { lightPalette, darkPalette } from "./palette";

const getTheme = (mode, fontLevel = 0) => ({
  palette: mode === "dark" ? darkPalette : lightPalette,
  typography: typography(fontLevel),
});

export default getTheme;
