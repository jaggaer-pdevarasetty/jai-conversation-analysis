"use client";

import { createTheme } from "@mui/material/styles";

// White-first, clean, LangSmith-inspired. JAGGAER-orange accent.
export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#E8541E" }, // JAGGAER orange accent
    background: { default: "#ffffff", paper: "#ffffff" },
    divider: "#ececf1",
    text: { primary: "#1a1a2e", secondary: "#6b7280" },
  },
  shape: { borderRadius: 10 },
  typography: {
    fontFamily:
      'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    h4: { fontWeight: 700, letterSpacing: -0.5 },
    h5: { fontWeight: 700 },
    h6: { fontWeight: 700 },
    button: { textTransform: "none", fontWeight: 600 },
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: { border: "1px solid #ececf1", boxShadow: "none" },
      },
    },
    MuiTableCell: {
      styleOverrides: { head: { fontWeight: 700, color: "#6b7280", background: "#fafafb" } },
    },
    MuiAppBar: {
      styleOverrides: {
        root: { background: "#ffffff", color: "#1a1a2e", borderBottom: "1px solid #ececf1" },
      },
    },
  },
});
