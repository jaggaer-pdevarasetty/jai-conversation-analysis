"use client";

import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import ErrorOutlineRoundedIcon from "@mui/icons-material/ErrorOutlineRounded";
import TroubleshootRoundedIcon from "@mui/icons-material/TroubleshootRounded";
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Chip,
  LinearProgress,
  MenuItem,
  Paper,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { fetchGroups, type GroupsResponse } from "../../src/services/analysisApi";
import { MarkdownContent } from "../../src/components/MarkdownContent";
import { useRegion } from "../../src/components/RegionContext";

export default function InsightsPage() {
  const [data, setData] = useState<GroupsResponse | null>(null);
  const [scope, setScope] = useState("issues");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { region, loading: regionLoading } = useRegion();

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchGroups({ region, scope })
      .then(setData)
      .catch(() => setError("The insights could not be loaded. Check the API connection and try again."))
      .finally(() => setLoading(false));
  }, [region, scope]);

  useEffect(() => {
    if (!regionLoading) load();
  }, [load, regionLoading]);

  if (error) {
    return <Alert severity="error" action={<Button color="inherit" onClick={load}>Try again</Button>}><AlertTitle>Insights unavailable</AlertTitle>{error}</Alert>;
  }
  if (!data) {
    return <Stack spacing={2.5} role="status" aria-label="Loading insights"><Skeleton variant="rounded" height={120} /><Skeleton variant="rounded" height={440} /></Stack>;
  }

  const totalConversations = data.items.reduce((sum, group) => sum + group.conversations, 0);

  return (
    <Stack spacing={3}>
      <Box sx={{ display: "flex", alignItems: { xs: "flex-start", lg: "flex-end" }, justifyContent: "space-between", gap: 2, flexDirection: { xs: "column", lg: "row" } }}>
        <Box>
          <Typography variant="overline" color="primary.main">Fix once, resolve many</Typography>
          <Typography variant="h1" component="h1">Insights</Typography>
          <Typography color="text.secondary" sx={{ mt: 1, maxWidth: 760 }}>
            Conversations grouped by shared root cause and knowledge gap, ranked by impact, so the biggest recurring problems surface first.
          </Typography>
        </Box>
        <TextField select size="small" label="Scope" value={scope} onChange={(event) => setScope(event.target.value)} sx={{ minWidth: 220 }}>
          <MenuItem value="issues">Went badly (feedback + negative)</MenuItem>
          <MenuItem value="all">All analysed conversations</MenuItem>
        </TextField>
      </Box>

      <TableContainer component={Paper} sx={{ overflowX: "auto" }} aria-busy={loading}>
        {loading && <LinearProgress aria-label="Loading insights" />}
        <Box sx={{ px: 2.5, py: 2, borderBottom: "1px solid", borderColor: "divider" }}>
          <Typography variant="h3">Root‑cause groups</Typography>
          <Typography variant="body2" color="text.secondary">
            {data.total} {data.total === 1 ? "group" : "groups"} · {totalConversations.toLocaleString()} conversations
          </Typography>
        </Box>
        <Table aria-label="Root-cause groups" sx={{ minWidth: 900 }}>
          <TableHead>
            <TableRow>
              <TableCell>Root cause</TableCell>
              <TableCell align="right">Conversations</TableCell>
              <TableCell align="right">Tenants</TableCell>
              <TableCell align="right">Users</TableCell>
              <TableCell>Suggested fix</TableCell>
              <TableCell align="right">Open</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.items.length ? data.items.map((group) => (
              <TableRow key={group.root_cause} hover>
                <TableCell sx={{ maxWidth: 320 }}>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                    <Typography variant="body2" sx={{ fontWeight: 750 }}>{group.label}</Typography>
                    {group.knowledge_gap && <Chip size="small" color="warning" variant="outlined" icon={<TroubleshootRoundedIcon />} label="Knowledge gap" />}
                  </Stack>
                </TableCell>
                <TableCell align="right"><Typography variant="body2" sx={{ fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>{group.conversations.toLocaleString()}</Typography></TableCell>
                <TableCell align="right" sx={{ fontVariantNumeric: "tabular-nums" }}>{group.tenants.toLocaleString()}</TableCell>
                <TableCell align="right" sx={{ fontVariantNumeric: "tabular-nums" }}>{group.users.toLocaleString()}</TableCell>
                <TableCell sx={{ minWidth: 280, maxWidth: 460 }}>
                  <Box sx={{ color: group.example_next_step ? "text.primary" : "text.secondary", display: "-webkit-box", WebkitBoxOrient: "vertical", WebkitLineClamp: 2, overflow: "hidden" }}>
                    <MarkdownContent>{group.example_next_step || "No suggested fix captured yet."}</MarkdownContent>
                  </Box>
                </TableCell>
                <TableCell align="right">
                  <Button component={Link} href={`/feedback?root_cause=${encodeURIComponent(group.root_cause)}`} size="small" endIcon={<ArrowForwardRoundedIcon />} aria-label={`Open ${group.label} conversations`}>Review</Button>
                </TableCell>
              </TableRow>
            )) : (
              <TableRow><TableCell colSpan={6}><Box sx={{ py: 8, textAlign: "center" }}><ErrorOutlineRoundedIcon sx={{ fontSize: 38, color: "text.disabled" }} /><Typography variant="h3" sx={{ mt: 1 }}>No groups yet</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>Analyse some conversations, then root causes will be grouped here.</Typography></Box></TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
}
