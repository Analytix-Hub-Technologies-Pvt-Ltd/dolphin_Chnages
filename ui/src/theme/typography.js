import { getFontSize } from "./fontScale";

const typography = (fontLevel = 0) => ({
  fontFamily: "Poppins, sans-serif",

  h1: {
    fontWeight: 600,
    fontSize: getFontSize(32, fontLevel),
  },
  h2: {
    fontWeight: 600,
    fontSize: getFontSize(24, fontLevel),
  },
  h3: {
    fontWeight: 700,
    fontSize: getFontSize(20, fontLevel),
  },
  h4: {
    fontWeight: 500,
    fontSize: getFontSize(18, fontLevel),
  },
  body1: {
    fontWeight: 500,
    fontSize: getFontSize(16, fontLevel),
  },
  body2: {
    fontWeight: 400,
    fontSize: getFontSize(14, fontLevel),
  },
  caption: {
    fontWeight: 400,
    fontSize: getFontSize(10, fontLevel),
  },
  h6: {
    fontWeight: 500,
    fontSize: getFontSize(12, fontLevel),
  },

  signupPageh1: {
    fontWeight: 700,
    fontSize: getFontSize(42, fontLevel),
    lineHeight: 1.4,
  },

  signupPageh2: {
    fontWeight: 500,
    fontSize: getFontSize(30, fontLevel),
    lineHeight: 1.1,
  },

  button: {
    fontWeight: 600,
    textTransform: "none",
  },
});

export default typography;
