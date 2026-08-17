"use client";

import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import AutoGraphRoundedIcon from "@mui/icons-material/AutoGraphRounded";
import BusinessRoundedIcon from "@mui/icons-material/BusinessRounded";
import CheckCircleOutlineRoundedIcon from "@mui/icons-material/CheckCircleOutlineRounded";
import ErrorOutlineRoundedIcon from "@mui/icons-material/ErrorOutlineRounded";
import FactCheckOutlinedIcon from "@mui/icons-material/FactCheckOutlined";
import ForumOutlinedIcon from "@mui/icons-material/ForumOutlined";
import GroupsOutlinedIcon from "@mui/icons-material/GroupsOutlined";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import SpeedRoundedIcon from "@mui/icons-material/SpeedRounded";
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Chip,
  Divider,
  InputAdornment,
  LinearProgress,
  Paper,
  Skeleton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { idSearchHref } from "../src/components/AppShell";
import { CATEGORY_META, CategoryChip } from "../src/components/CategoryChip";
import { MarkdownContent } from "../src/components/MarkdownContent";
import { useRegion } from "../src/components/RegionContext";
import { StatCard } from "../src/components/StatCard";
import {
  fetchAnalysis,
  fetchLatestRun,
  type ListResponse,
  type RunSummary,
} from "../src/services/analysisApi";
import { fetchOverview, type Overview } from "../src/services/dashboardApi";

const CATEGORY_ORDER = [
  "resolved",
  "failed_to_resolve",
  "positive_feedback",
  "negative_feedback",
  "out_of_scope",
];

const CATEGORY_HELP: Record<string, string> = {
  resolved: "Requests completed without a negative signal",
  failed_to_resolve: "Unresolved, repeated, abandoned, or frustrated sessions",
  positive_feedback: "Conversations with explicit positive feedback",
  negative_feedback: "Conversations with explicit negative feedback",
  out_of_scope: "Requests outside JAI's current capabilities",
};

function formatDate(value?: string): string {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function runDuration(run: RunSummary): string {
  const ms = new Date(run.completed_at).getTime() - new Date(run.started_at).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "Not available";
  return ms < 1000 ? "< 1 sec" : `${(ms / 1000).toFixed(1)} sec`;
}

export default function OverviewPage() {
  const [data, setData] = useState<ListResponse | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [run, setRun] = useState<RunSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [idSearch, setIdSearch] = useState("");
  const [idSearchError, setIdSearchError] = useState(false);
  const requestId = useRef(0);
  const router = useRouter();
  const { region, loading: regionLoading } = useRegion();

  const load = useCallback(async () => {
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError(null);
    const [analysisResult, overviewResult, runResult] = await Promise.allSettled([
      fetchAnalysis({ region }),
      fetchOverview(region),
      fetchLatestRun(),
    ]);
    if (currentRequest !== requestId.current) return;
    if (analysisResult.status === "rejected") {
      setError("The analysis service could not be reached. Check that the API is running, then try again.");
      setLoading(false);
      return;
    }
    setData(analysisResult.value);
    setOverview(overviewResult.status === "fulfilled" ? overviewResult.value : null);
    setRun(runResult.status === "fulfilled" ? runResult.value : null);
    setLoading(false);
  }, [region]);

  useEffect(() => {
    if (!regionLoading) void load();
  }, [load, regionLoading]);

  const recent = useMemo(
    () => [...(data?.items ?? [])].sort((a, b) => (b.last_message_at ?? b.analyzed_at ?? "").localeCompare(a.last_message_at ?? a.analyzed_at ?? "")).slice(0, 5),
    [data],
  );

  if (loading) {
    return (
      <Stack spacing={3} role="status" aria-label="Loading overview">
        <Skeleton variant="rounded" height={112} />
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", xl: "repeat(3, 1fr)" }, gap: 2 }}>
          {[1, 2, 3, 4, 5, 6].map((item) => <Skeleton key={item} variant="rounded" height={136} />)}
        </Box>
        <Skeleton variant="rounded" height={380} />
      </Stack>
    );
  }

  if (error || !data) {
    return (
      <Alert severity="error" action={<Button color="inherit" onClick={() => void load()}>Try again</Button>}>
        <AlertTitle>Overview unavailable</AlertTitle>
        {error}
      </Alert>
    );
  }

  const analysed = data.total;
  const sourceConversations = overview?.conversations ?? analysed;
  const positive = (data.counts.resolved ?? 0) + (data.counts.positive_feedback ?? 0);
  const attention =
    (data.counts.failed_to_resolve ?? 0) +
    (data.counts.negative_feedback ?? 0) +
    (data.counts.out_of_scope ?? 0);
  const coverageItems = data.items.filter(
    (item) => item.metrics.ttft_ms !== null && item.metrics.input_tokens !== null && item.metrics.output_tokens !== null,
  ).length;
  const telemetryCoverage = data.items.length ? Math.round((coverageItems / data.items.length) * 100) : 0;
  const analysisCoverage = sourceConversations ? Math.round((analysed / sourceConversations) * 100) : 0;
  const lowConfidence = data.items.filter((item) => item.confidence === "low").length;
  const overrides = data.items.filter((item) => item.overridden).length;

  return (
    <Stack spacing={3.5}>
      <Box sx={{ display: "flex", alignItems: { xs: "flex-start", lg: "flex-end" }, justifyContent: "space-between", gap: 2, flexDirection: { xs: "column", lg: "row" } }}>
        <Box>
          <Typography variant="overline" color="primary.main">Conversation intelligence</Typography>
          <Typography component="h1" variant="h1">Overview</Typography>
          <Typography color="text.secondary" sx={{ mt: 1, maxWidth: 720 }}>
            Organisation coverage, conversation outcomes, analysis health, and the latest records in one place.
          </Typography>
          <Box
            component="form"
            onSubmit={(event) => {
              event.preventDefault();
              const href = idSearchHref(idSearch);
              setIdSearchError(href === null);
              if (href) router.push(href);
            }}
            aria-label="Find a conversation or tenant"
            sx={{ mt: 2, display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: 1, width: "100%", maxWidth: 620 }}
          >
            <TextField
              fullWidth
              required
              size="small"
              label="Find conversation or tenant"
              placeholder="Conversation UUID or tenant ID"
              value={idSearch}
              error={idSearchError}
              helperText={idSearchError ? "Enter a conversation UUID or numeric tenant ID." : undefined}
              onChange={(event) => { setIdSearch(event.target.value); setIdSearchError(false); }}
              InputProps={{ startAdornment: <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment> }}
            />
            <Button type="submit" variant="contained" sx={{ width: { xs: "100%", sm: "auto" } }}>Find</Button>
          </Box>
        </Box>
        <Stack direction="row" spacing={1.25} flexWrap="wrap" useFlexGap>
          <Button component={Link} href="/tenants" variant="outlined" endIcon={<ArrowForwardRoundedIcon />}>Browse tenants</Button>
          <Button component={Link} href="/conversations" variant="contained" endIcon={<ArrowForwardRoundedIcon />}>Open review queue</Button>
        </Stack>
      </Box>

      {data.unanalysed > 0 ? (
        <Alert severity="warning">
          <AlertTitle>{data.unanalysed} {data.unanalysed === 1 ? "conversation is" : "conversations are"} waiting for analysis</AlertTitle>
          Failed analyses remain visible and will be retried during the next scheduled run.
        </Alert>
      ) : (
        <Paper sx={{ p: 2, display: "flex", alignItems: "center", gap: 1.5, bgcolor: "#F0FAF6", borderColor: "#CFEBDD" }}>
          <CheckCircleOutlineRoundedIcon color="success" />
          <Box>
            <Typography variant="body2" sx={{ fontWeight: 750 }}>Analysis retry queue is clear</Typography>
            <Typography variant="caption" color="text.secondary">No failed conversations are waiting for retry.</Typography>
          </Box>
          {run && <Chip size="small" label={`Last run ${formatDate(run.completed_at)}`} sx={{ ml: "auto", display: { xs: "none", sm: "flex" }, bgcolor: "#FFFFFF" }} />}
        </Paper>
      )}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", xl: "repeat(3, 1fr)" }, gap: 2 }}>
        <StatCard label="Tenants" value={(overview?.tenants ?? "—").toLocaleString()} helper="Organisations in the authorised directory" icon={<BusinessRoundedIcon />} />
        <StatCard label="Users" value={(overview?.users ?? "—").toLocaleString()} helper="Distinct users across tenants" icon={<GroupsOutlinedIcon />} tone="#356BB3" />
        <StatCard label="Source conversations" value={sourceConversations.toLocaleString()} helper="Available read-only conversation records" icon={<ForumOutlinedIcon />} tone="#65758B" />
        <StatCard label="Analysed" value={analysed.toLocaleString()} helper={`${analysisCoverage}% of source conversations`} icon={<FactCheckOutlinedIcon />} tone="#16815D" />
        <StatCard label="Needs attention" value={attention.toLocaleString()} helper="Failures, negative feedback, and capability gaps" icon={<ErrorOutlineRoundedIcon />} tone="#C43D4B" />
        <StatCard label="Telemetry complete" value={`${telemetryCoverage}%`} helper="Latency and token data in the loaded analysis set" icon={<SpeedRoundedIcon />} tone="#7A55B8" />
      </Box>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 1.65fr) minmax(300px, .75fr)" }, gap: 2.5, alignItems: "start" }}>
        <Paper sx={{ p: { xs: 2.25, md: 3 } }}>
          <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 2, mb: 3 }}>
            <Box>
              <Typography variant="h3">Outcome mix</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>Distribution across the five review categories</Typography>
            </Box>
            <AutoGraphRoundedIcon sx={{ color: "text.secondary" }} />
          </Box>
          <Stack spacing={2.5}>
            {CATEGORY_ORDER.map((category) => {
              const count = data.counts[category] ?? 0;
              const percent = analysed ? Math.round((count / analysed) * 100) : 0;
              const meta = CATEGORY_META[category];
              return (
                <Box key={category}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 1 }}>
                    <CategoryChip category={category} />
                    <Typography variant="caption" color="text.secondary" sx={{ display: { xs: "none", sm: "block" } }}>{CATEGORY_HELP[category]}</Typography>
                    <Box sx={{ ml: "auto", textAlign: "right", flex: "0 0 auto" }}>
                      <Typography variant="body2" sx={{ fontWeight: 750 }}>{count.toLocaleString()}</Typography>
                      <Typography variant="caption" color="text.secondary">{percent}%</Typography>
                    </Box>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={percent}
                    aria-label={`${meta.label}: ${percent}%`}
                    sx={{ height: 8, borderRadius: 99, bgcolor: `${meta.bar}16`, "& .MuiLinearProgress-bar": { bgcolor: meta.bar, borderRadius: 99 } }}
                  />
                </Box>
              );
            })}
          </Stack>
        </Paper>

        <Stack spacing={2.5}>
          <Paper sx={{ p: 2.5 }}>
            <Typography variant="h3">Latest analysis run</Typography>
            {run ? (
              <Stack spacing={1.6} sx={{ mt: 2.25 }} divider={<Divider flexItem />}>
                <Box><Typography variant="caption" color="text.secondary">Completed</Typography><Typography variant="body2" sx={{ fontWeight: 700, mt: 0.25 }}>{formatDate(run.completed_at)}</Typography></Box>
                <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 2 }}>
                  <Box><Typography variant="caption" color="text.secondary">Analysed</Typography><Typography variant="h3">{run.analysed}</Typography></Box>
                  <Box><Typography variant="caption" color="text.secondary">Duration</Typography><Typography variant="h3">{runDuration(run)}</Typography></Box>
                </Box>
                <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 2 }}>
                  <Box><Typography variant="caption" color="text.secondary">Failed</Typography><Typography variant="body2" sx={{ fontWeight: 700 }}>{run.failed}</Typography></Box>
                  <Box><Typography variant="caption" color="text.secondary">Too recent</Typography><Typography variant="body2" sx={{ fontWeight: 700 }}>{run.skipped}</Typography></Box>
                </Box>
                <Typography variant="caption" color="text.secondary">Scheduled every 4 hours · conversations settle for 5 minutes</Typography>
              </Stack>
            ) : <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>Run information is currently unavailable.</Typography>}
          </Paper>

          <Paper sx={{ p: 2.5 }}>
            <Typography variant="h3">Review signals</Typography>
            <Stack spacing={1.5} sx={{ mt: 2 }}>
              <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}><Typography variant="body2" color="text.secondary">Positive outcomes</Typography><Chip size="small" label={positive} /></Box>
              <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}><Typography variant="body2" color="text.secondary">Low confidence</Typography><Chip size="small" label={lowConfidence} /></Box>
              <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}><Typography variant="body2" color="text.secondary">Human overrides</Typography><Chip size="small" label={overrides} /></Box>
              <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}><Typography variant="body2" color="text.secondary">Missing telemetry</Typography><Chip size="small" label={data.items.length - coverageItems} /></Box>
            </Stack>
          </Paper>
        </Stack>
      </Box>

      <Paper sx={{ overflow: "hidden" }}>
        <Box sx={{ px: { xs: 2.25, md: 3 }, py: 2.5, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
          <Box><Typography variant="h3">Recent analyses</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.35 }}>Latest records added to the reviewer workspace</Typography></Box>
          <Button component={Link} href="/conversations" size="small" endIcon={<ArrowForwardRoundedIcon />}>View all</Button>
        </Box>
        <Divider />
        {recent.length ? recent.map((item, index) => (
          <Box key={item.conversation_id}>
            <Box sx={{ px: { xs: 2.25, md: 3 }, py: 1.8, display: "grid", gridTemplateColumns: { xs: "minmax(0, 1fr) auto", lg: "minmax(0, 1.1fr) 170px minmax(0, 1.25fr) auto" }, gap: 2, alignItems: "center" }}>
              <Box sx={{ minWidth: 0, overflow: "hidden" }}>
                <Typography component={Link} href={`/conversations/${item.conversation_id}`} title={item.conversation_id} variant="body2" sx={{ display: "block", color: "text.primary", fontWeight: 750, textDecoration: "none", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", "&:hover": { color: "primary.main" } }}>{item.conversation_id}</Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.25, whiteSpace: "nowrap" }}>{formatDate(item.analyzed_at)}</Typography>
              </Box>
              <Box sx={{ display: { xs: "none", lg: "block" }, minWidth: 0 }}><CategoryChip category={item.category} /></Box>
              <Box sx={{ display: { xs: "none", lg: "block" }, maxHeight: 48, overflow: "hidden", color: "text.secondary" }}><MarkdownContent>{item.recommended_next_step}</MarkdownContent></Box>
              <Button component={Link} href={`/conversations/${item.conversation_id}`} size="small" aria-label={`Review conversation ${item.conversation_id}`}>Review</Button>
            </Box>
            {index < recent.length - 1 && <Divider />}
          </Box>
        )) : <Typography color="text.secondary" sx={{ p: 3 }}>No analysed conversations yet.</Typography>}
      </Paper>
    </Stack>
  );
}
