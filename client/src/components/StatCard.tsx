"use client";

import { Paper, Typography } from "@mui/material";

export function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <Paper sx={{ p: 2.5, flex: 1, minWidth: 150 }}>
      <Typography variant="caption" sx={{ color: "text.secondary", textTransform: "uppercase", letterSpacing: 0.5 }}>
        {label}
      </Typography>
      <Typography variant="h4" sx={{ mt: 0.5 }}>
        {value}
      </Typography>
    </Paper>
  );
}
