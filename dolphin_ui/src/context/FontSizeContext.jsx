import React, { createContext, useContext, useState } from "react";

const FontSizeContext = createContext();

export const FontSizeProvider = ({ children }) => {
  // 0 = small, 1 = medium, 2 = large
  const [fontLevel, setFontLevel] = useState(0);

  return (
    <FontSizeContext.Provider value={{ fontLevel, setFontLevel }}>
      {children}
    </FontSizeContext.Provider>
  );
};

export const useFontSize = () => useContext(FontSizeContext);
