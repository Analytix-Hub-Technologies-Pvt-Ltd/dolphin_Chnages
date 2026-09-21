export const FONT_SIZE_INCREMENT = {
  0: 0, // small
  1: 2, // medium
  2: 4, // large
};

export const getFontSize = (base, level) =>
  `${base + (FONT_SIZE_INCREMENT[level] ?? 0)}px`;


