// utils/layoutScale.js

export const WELCOME_WIDTH_INCREMENT = {
  0: 0,   // base
  1: 50,  // medium
  2: 80,  // large
};

export const getWelcomeMaxWidth = (base, level) =>
  `${base + (WELCOME_WIDTH_INCREMENT[level] ?? 0)}px`;

export const DESCRIPTION_WIDTH_MAP = {
  0: "80%",
  1: "90%",
  2: "100%",
};

export const getDescriptionWidth = (level) =>
  DESCRIPTION_WIDTH_MAP[level] ?? "80%";

export const WELCOME_BOX_GAP = {
  0: 2,
  1: 1.5,
  2: .5,
};

export const getDescriptionGap = (level) =>
  WELCOME_BOX_GAP[level] ?? 0;


export const SIDEBAR_WIDTH_MAP = {
  0: 20,
  1: 22,
  2: 25,
};

export const getSidebarWidth = (level = 0) =>
  `${SIDEBAR_WIDTH_MAP[level] ?? 20}vw`;

export const getContentWidth = (level = 0) =>
  `${100 - (SIDEBAR_WIDTH_MAP[level] ?? 20)}vw`;