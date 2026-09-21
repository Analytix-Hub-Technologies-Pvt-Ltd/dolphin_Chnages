import { createContext, useContext, useState, useEffect } from "react";

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
    if (mode === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [mode]);

  useEffect(() => {
    localStorage.setItem("fontLevel", fontLevel);
    document.documentElement.setAttribute("data-font-level", fontLevel);
  }, [fontLevel]);

  return (
    <ThemeModeContext.Provider
      value={{
        mode,
        toggleMode,
        fontLevel,
        setFontLevel,
      }}
    >
      {children}
    </ThemeModeContext.Provider>
  );
};

