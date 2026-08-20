import { createContext, useContext, useMemo, useState, useEffect } from "react";
import { ThemeProvider, CssBaseline } from "@mui/material";
import getTheme from "../theme";

const ThemeModeContext = createContext(null);

export const useThemeMode = () => useContext(ThemeModeContext);

export const ThemeModeProvider = ({ children }) => {
  const [mode, setMode] = useState(() => {
    return localStorage.getItem("themeMode") || "light";
  });

  const [fontLevel, setFontLevel] = useState(() => {
    const saved = localStorage.getItem("fontLevel");
    return saved !== null ? Number(saved) : 0;
  });

  const toggleMode = () => {
    setMode((prev) => (prev === "light" ? "dark" : "light"));
  };

  useEffect(() => {
    localStorage.setItem("themeMode", mode);
  }, [mode]);

  useEffect(() => {
    localStorage.setItem("fontLevel", fontLevel);
  }, [fontLevel]);

  const theme = useMemo(
    () => getTheme(mode, fontLevel),
    [mode, fontLevel]
  );

  return (
    <ThemeModeContext.Provider
      value={{
        mode,
        toggleMode,
        fontLevel,
        setFontLevel,
      }}
    >
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ThemeModeContext.Provider>
  );
};
