"use client";

import { Alert, Box, LinearProgress, Paper, Stack, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { CategoryChip } from "../src/components/CategoryChip";
import { StatCard } from "../src/components/StatCard";
import { fetchOverview, type Overview } from "../src/services/dashboardApi";

const CATEGORY_ORDER = [
  "resolved",
  "failed_to_resolve",
  "positive_feedback",
  "negative_feedback",
  "out_of_scope",
];

export default function OverviewPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchOverview()
      .then(setData)
      .catch(() => setError("Could not load the overview (is the API running?)."));
  }, []);

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!data) return <Typography>Loading…</Typography>;

  const maxCount = Math.max(1, ...Object.values(data.counts));

  return (
    <Stack spacing={3}>
      <Typography variant="h4">Overview</Typography>

      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
        <StatCard label="Tenants" value={data.tenants} />
        <StatCard label="Users" value={data.users} />
        <StatCard label="Conversations" value={data.conversations} />
        <StatCard label="Analysed" value={data.analysed} />
        <StatCard label="Unanalysed" value={data.unanalysed} />
      </Stack>

      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Category distribution
        </Typography>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          {CATEGORY_ORDER.map((cat) => {
            const n = data.counts[cat] ?? 0;
            return (
              <Box key={cat} sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                <Box sx={{ width: 170 }}>
                  <CategoryChip category={cat} />
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={(n / maxCount) * 100}
                  sx={{ flex: 1, height: 10, borderRadius: 5 }}
                />
                <Typography sx={{ width: 40, textAlign: "right", fontWeight: 600 }}>{n}</Typography>
              </Box>
            );
          })}
        </Stack>
      </Paper>
    </Stack>
  );
}
