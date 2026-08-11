"use client";

import { alpha, createTheme } from "@mui/material/styles";

// White-first, clean, LangSmith-inspired. JAGGAER-orange accent.
export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#E4511E", dark: "#BE3C10", light: "#FFF0E9" }, // JAGGAER orange accent
    secondary: { main: "#314158" },
    success: { main: "#16815D" },
    warning: { main: "#B75B08" },
    error: { main: "#C43D4B" },
    background: { default: "#F5F6F8", paper: "#FFFFFF" },
    divider: "#E3E6EB",
    text: { primary: "#172033", secondary: "#667085" },
  },
  shape: { borderRadius: 14 },
  typography: {
    fontFamily:
      'Inter, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    h1: { fontSize: "2.25rem", lineHeight: 1.14, fontWeight: 750, letterSpacing: -1.1 },
    h2: { fontSize: "1.65rem", lineHeight: 1.2, fontWeight: 750, letterSpacing: -0.65 },
    h3: { fontSize: "1.2rem", lineHeight: 1.3, fontWeight: 700, letterSpacing: -0.2 },
    h4: { fontWeight: 750, letterSpacing: -0.6 },
    h5: { fontWeight: 700 },
    h6: { fontWeight: 700 },
    body1: { lineHeight: 1.6 },
    body2: { lineHeight: 1.55 },
    button: { textTransform: "none", fontWeight: 700, letterSpacing: 0 },
    overline: { fontWeight: 700, letterSpacing: 1.2, lineHeight: 1.8 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: { minWidth: 320 },
        "::selection": { background: alpha("#E4511E", 0.18) },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { border: "1px solid #E3E6EB", boxShadow: "0 1px 2px rgba(16, 24, 40, 0.025)" },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: { root: { borderRadius: 10, minHeight: 40, paddingInline: 18 } },
    },
    MuiChip: {
      styleOverrides: { root: { borderRadius: 8, fontWeight: 650 } },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          background: "#FFFFFF",
          "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: "#A8AFBA" },
        },
        notchedOutline: { borderColor: "#D8DCE3" },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: { borderBottomColor: "#ECEEF2" },
        head: {
          fontSize: 12,
          fontWeight: 750,
          letterSpacing: 0.45,
          textTransform: "uppercase",
          color: "#667085",
          background: "#F8F9FB",
        },
      },
    },
    MuiTableRow: {
      styleOverrides: { root: { "&:last-child td": { borderBottom: 0 } } },
    },
    MuiAppBar: {
      styleOverrides: {
        root: { background: alpha("#FFFFFF", 0.92), color: "#172033", borderBottom: "1px solid #E3E6EB" },
      },
    },
    MuiAlert: {
      styleOverrides: { root: { borderRadius: 12 } },
    },
  },
});
