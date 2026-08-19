"use client";

import CssBaseline from "@mui/material/CssBaseline";
import { ThemeProvider } from "@mui/material/styles";
import type { ReactNode } from "react";
import { theme } from "../theme";
import { EnvProvider } from "./EnvContext";
import { RegionProvider } from "./RegionContext";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <EnvProvider>
        <RegionProvider>{children}</RegionProvider>
      </EnvProvider>
    </ThemeProvider>
  );
}
