"use client";

import { Box, Paper, Typography } from "@mui/material";
import type { ReactNode } from "react";

export function StatCard({
  label,
  value,
  helper,
  icon,
  tone = "#E4511E",
}: {
  label: string;
  value: number | string;
  helper?: string;
  icon?: ReactNode;
  tone?: string;
}) {
  return (
    <Paper sx={{ p: 2.5, minWidth: 0, height: "100%" }}>
      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="body2" sx={{ color: "text.secondary", fontWeight: 650 }}>
            {label}
          </Typography>
          <Typography variant="h2" sx={{ mt: 0.7, fontVariantNumeric: "tabular-nums" }}>
            {value}
          </Typography>
        </Box>
        {icon && (
          <Box
            sx={{
              display: "grid",
              placeItems: "center",
              width: 42,
              height: 42,
              flex: "0 0 auto",
              borderRadius: 2.5,
              color: tone,
              bgcolor: `${tone}14`,
            }}
          >
            {icon}
          </Box>
        )}
      </Box>
      {helper && (
        <Typography variant="caption" sx={{ display: "block", color: "text.secondary", mt: 1.2 }}>
          {helper}
        </Typography>
      )}
    </Paper>
  );
}
