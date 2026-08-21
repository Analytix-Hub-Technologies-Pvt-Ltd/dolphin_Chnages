import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import reportWebVitals from "./reportWebVitals";

import { ThemeModeProvider } from "./context/ThemeModeContext";
import { BrowserRouter } from "react-router-dom";

const root = ReactDOM.createRoot(document.getElementById("root"));

root.render(
  <ThemeModeProvider>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </ThemeModeProvider>
);

reportWebVitals();
