"use client";

import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import ErrorOutlineRoundedIcon from "@mui/icons-material/ErrorOutlineRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import WarningAmberRoundedIcon from "@mui/icons-material/WarningAmberRounded";
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Chip,
  InputAdornment,
  LinearProgress,
  Link as MuiLink,
  MenuItem,
  Paper,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { CATEGORIES, fetchAnalysis, type ImmediateAnalytics, type ListResponse } from "../../src/services/analysisApi";
import { CATEGORY_META, CategoryChip } from "../../src/components/CategoryChip";
import { EABadge } from "../../src/components/EABadge";
import { MarkdownContent } from "../../src/components/MarkdownContent";
import { useRegion } from "../../src/components/RegionContext";

const REASONS = [
  "guardrail_bypass",
  "empty_final_response",
  "message_error",
  "rate_limit",
  "high_frustration",
  "kb_issue",
  "ticket_failure",
  "service_failure",
  "processing_failure",
  "stream_failure",
  "authentication_failure",
  "source_code",
  "technical_error_leak",
] as const;

type KbChartView = "per_day" | "per_day_region" | "per_tenant";

const REASON_LABELS: Record<string, string> = {
  ticket_failure: "Ticket Not Created",
  message_error: "Message Error (DB)",
};

const label = (value: string) =>
  REASON_LABELS[value] ?? value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

function formatDate(value?: string | null): string {
  if (!value) return "Unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unavailable" : new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function shortDay(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en", { month: "short", day: "numeric", timeZone: "UTC" }).format(date);
}

function KbTrendCard({
  analytics,
  view,
  onViewChange,
}: {
  analytics?: ImmediateAnalytics;
  view: KbChartView;
  onViewChange: (next: KbChartView) => void;
}) {
  const byDay = (analytics?.kb_by_day ?? []).filter((row) => row.count > 0 || (analytics?.kb_by_day.length ?? 0) <= 14);
  const byDayRegion = (analytics?.kb_by_day_region ?? []).filter((row) => row.total > 0 || (analytics?.kb_by_day_region.length ?? 0) <= 14);
  const byTenant = analytics?.kb_by_tenant ?? [];
  const maxDay = Math.max(1, ...byDay.map((row) => row.count));
  const maxRegionDay = Math.max(1, ...byDayRegion.map((row) => row.total));
  const maxTenant = Math.max(1, ...byTenant.map((row) => row.count));

  return (
    <Paper sx={{ p: 2.25 }}>
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", sm: "center" }} spacing={1.5}>
        <Box>
          <Typography variant="overline" color="warning.dark">Knowledge base diagnostics</Typography>
          <Typography variant="h3">KB issue trends ({analytics?.kb_issues ?? 0})</Typography>
          <Typography variant="caption" color="text.secondary">
            Switch between daily trend, daily per-region split, and affected tenants.
          </Typography>
        </Box>
        <ToggleButtonGroup
          size="small"
          exclusive
          aria-label="KB trend view"
          value={view}
          onChange={(_, next: KbChartView | null) => {
            if (next) onViewChange(next);
          }}
        >
          <ToggleButton value="per_day">Per day</ToggleButton>
          <ToggleButton value="per_day_region">Per day · region</ToggleButton>
          <ToggleButton value="per_tenant">Per tenant</ToggleButton>
        </ToggleButtonGroup>
      </Stack>

      {view === "per_day" && (
        byDay.some((row) => row.count > 0) ? (
          <Stack spacing={1} sx={{ mt: 2 }}>
            {byDay.map((row) => (
              <Box key={row.date} sx={{ display: "grid", gridTemplateColumns: "92px 1fr 48px", gap: 1.25, alignItems: "center" }}>
                <Typography variant="caption" color="text.secondary">{shortDay(row.date)}</Typography>
                <Box sx={{ height: 12, bgcolor: "action.hover", borderRadius: 1, overflow: "hidden" }}>
                  <Box sx={{ width: `${(row.count / maxDay) * 100}%`, height: "100%", bgcolor: "#D97706", borderRadius: 1 }} />
                </Box>
                <Typography variant="caption" sx={{ fontWeight: 700, textAlign: "right" }}>{row.count}</Typography>
              </Box>
            ))}
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            No KB issue conversations recorded in the selected scope.
          </Typography>
        )
      )}

      {view === "per_day_region" && (
        byDayRegion.some((row) => row.total > 0) ? (
          <Stack spacing={1.25} sx={{ mt: 2 }}>
            <Stack direction="row" spacing={1.5}>
              <Chip size="small" label="US" sx={{ bgcolor: "#1D4ED8", color: "#fff" }} />
              <Chip size="small" label="EU" sx={{ bgcolor: "#059669", color: "#fff" }} />
              <Chip size="small" label="UK" sx={{ bgcolor: "#D97706", color: "#fff" }} />
            </Stack>
            {byDayRegion.map((row) => (
              <Box key={row.date} sx={{ display: "grid", gridTemplateColumns: "92px 1fr 110px", gap: 1.25, alignItems: "center" }}>
                <Typography variant="caption" color="text.secondary">{shortDay(row.date)}</Typography>
                <Box sx={{ display: "flex", height: 12, bgcolor: "action.hover", borderRadius: 1, overflow: "hidden" }}>
                  {row.us > 0 && <Box sx={{ width: `${(row.us / maxRegionDay) * 100}%`, bgcolor: "#1D4ED8" }} title={`US: ${row.us}`} />}
                  {row.eu > 0 && <Box sx={{ width: `${(row.eu / maxRegionDay) * 100}%`, bgcolor: "#059669" }} title={`EU: ${row.eu}`} />}
                  {row.uk > 0 && <Box sx={{ width: `${(row.uk / maxRegionDay) * 100}%`, bgcolor: "#D97706" }} title={`UK: ${row.uk}`} />}
                </Box>
                <Typography variant="caption" sx={{ fontWeight: 700, textAlign: "right" }}>
                  US {row.us} · EU {row.eu} · UK {row.uk}
                </Typography>
              </Box>
            ))}
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            No regional KB issue activity in the selected scope.
          </Typography>
        )
      )}

      {view === "per_tenant" && (
        byTenant.length > 0 ? (
          <Stack spacing={1} sx={{ mt: 2 }}>
            {byTenant.map((row) => (
              <Box key={`${row.tenant_id ?? row.tenant_name}`} sx={{ display: "grid", gridTemplateColumns: "minmax(160px, 220px) 1fr 48px", gap: 1.25, alignItems: "center" }}>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="caption" sx={{ fontWeight: 700, display: "block" }} noWrap>{row.tenant_name}</Typography>
                  <Typography variant="caption" color="text.secondary" noWrap>
                    ID: {row.tenant_id ?? "—"} {row.region ? `· ${row.region.toUpperCase()}` : ""}
                  </Typography>
                </Box>
                <Box sx={{ height: 12, bgcolor: "action.hover", borderRadius: 1, overflow: "hidden" }}>
                  <Box sx={{ width: `${(row.count / maxTenant) * 100}%`, height: "100%", bgcolor: "#B45309", borderRadius: 1 }} />
                </Box>
                <Typography variant="caption" sx={{ fontWeight: 700, textAlign: "right" }}>{row.count}</Typography>
              </Box>
            ))}
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            No tenants have KB issues in the selected scope.
          </Typography>
        )
      )}
    </Paper>
  );
}

function SeriousIssuesTrendCard({
  analytics,
  onSelectReason,
}: {
  analytics?: ImmediateAnalytics;
  onSelectReason: (reason: string) => void;
}) {
  const rows = (analytics?.serious_by_day ?? []).filter((row) => row.total > 0);
  const maxDay = Math.max(1, ...rows.map((row) => row.total));
  const top3 = (
    analytics?.top_reasons?.length
      ? analytics.top_reasons
      : Object.entries(analytics?.by_reason ?? {})
          .map(([reason, count]) => ({ reason, count }))
          .sort((a, b) => b.count - a.count)
  ).slice(0, 3);

  return (
    <Paper sx={{ p: 2.25 }} aria-label="Serious issues trend (1)">
      <Stack spacing={1.25}>
        <Box>
          <Typography variant="overline" color="error.main">Critical signal monitor</Typography>
          <Typography variant="h3">Serious issues trend (1)</Typography>
          <Typography variant="caption" color="text.secondary">
            Fixed critical signals (always tracked) plus the top 3 most frequent serious issues by count.
          </Typography>
        </Box>

        <Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5, fontWeight: 700 }}>
            Fixed monitors (all time)
          </Typography>
          <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
            <Chip
              size="small"
              onClick={() => onSelectReason("empty_final_response")}
              label={`Empty responses: ${analytics?.empty_final_response ?? 0}`}
              sx={{ bgcolor: "#EA580C", color: "#fff" }}
            />
            <Chip
              size="small"
              onClick={() => onSelectReason("guardrail_bypass")}
              label={`Guardrail bypass: ${analytics?.guardrail_bypass ?? 0}`}
              sx={{ bgcolor: "#DC2626", color: "#fff" }}
            />
            <Chip
              size="small"
              onClick={() => onSelectReason("high_frustration")}
              label={`High frustration: ${analytics?.high_frustration ?? 0}`}
              sx={{ bgcolor: "#7C3AED", color: "#fff" }}
            />
            <Chip
              size="small"
              onClick={() => onSelectReason("ticket_failure")}
              label={`Ticket not created: ${analytics?.ticket_failure ?? analytics?.by_reason?.ticket_failure ?? 0}`}
              sx={{ bgcolor: "#0284C7", color: "#fff" }}
            />
          </Stack>
        </Box>

        <Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5, fontWeight: 700 }}>
            Top 3 serious issues (last 15 days · count-wise)
          </Typography>
          <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
            {top3.length > 0 ? (
              top3.map((entry, idx) => (
                <Chip
                  key={entry.reason}
                  size="small"
                  color={idx === 0 ? "error" : idx === 1 ? "warning" : "default"}
                  variant="outlined"
                  onClick={() => onSelectReason(entry.reason)}
                  label={`#${idx + 1} ${label(entry.reason)}: ${entry.count}`}
                />
              ))
            ) : (
              <Typography variant="caption" color="text.secondary">No serious issues recorded in this scope.</Typography>
            )}
          </Stack>
        </Box>
      </Stack>

      {rows.length > 0 ? (
        <Stack spacing={1.1} sx={{ mt: 2 }}>
          {rows.map((row) => (
            <Box key={row.date} sx={{ display: "grid", gridTemplateColumns: "92px 1fr 220px", gap: 1.25, alignItems: "center" }}>
              <Typography variant="caption" color="text.secondary">{shortDay(row.date)}</Typography>
              <Box sx={{ display: "flex", height: 12, bgcolor: "action.hover", borderRadius: 1, overflow: "hidden" }}>
                {row.empty_final_response > 0 && (
                  <Box
                    sx={{ width: `${(row.empty_final_response / maxDay) * 100}%`, bgcolor: "#EA580C" }}
                    title={`Empty final response: ${row.empty_final_response}`}
                  />
                )}
                {row.guardrail_bypass > 0 && (
                  <Box
                    sx={{ width: `${(row.guardrail_bypass / maxDay) * 100}%`, bgcolor: "#DC2626" }}
                    title={`Guardrail bypass: ${row.guardrail_bypass}`}
                  />
                )}
                {(row.high_frustration ?? 0) > 0 && (
                  <Box
                    sx={{ width: `${((row.high_frustration ?? 0) / maxDay) * 100}%`, bgcolor: "#7C3AED" }}
                    title={`High frustration: ${row.high_frustration}`}
                  />
                )}
                {(row.ticket_failure ?? 0) > 0 && (
                  <Box
                    sx={{ width: `${((row.ticket_failure ?? 0) / maxDay) * 100}%`, bgcolor: "#0284C7" }}
                    title={`Ticket not created: ${row.ticket_failure}`}
                  />
                )}
                {row.other_serious > 0 && (
                  <Box
                    sx={{ width: `${(row.other_serious / maxDay) * 100}%`, bgcolor: "#4F46E5" }}
                    title={`Other urgent signals: ${row.other_serious}`}
                  />
                )}
              </Box>
              <Typography variant="caption" sx={{ fontWeight: 700, textAlign: "right" }}>
                Empty {row.empty_final_response} · Bypass {row.guardrail_bypass} · Ticket {row.ticket_failure ?? 0} · Other {row.other_serious + (row.high_frustration ?? 0)}
              </Typography>
            </Box>
          ))}
        </Stack>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          No urgent or serious issue signals found in the selected scope.
        </Typography>
      )}
    </Paper>
  );
}

export default function ImmediateActionPage() {
  const { region, loading: regionLoading } = useRegion();
  const [data, setData] = useState<ListResponse | null>(null);
  const [search, setSearch] = useState("");
  const [tenantFilter, setTenantFilter] = useState("");
  const [scope, setScope] = useState<"immediate_attention" | "kb_issue" | "immediate_or_kb">("immediate_attention");
  const [reason, setReason] = useState("");
  const [category, setCategory] = useState("");
  const [confidence, setConfidence] = useState("");
  const [hasFeedback, setHasFeedback] = useState("");
  const [dateRange, setDateRange] = useState("");
  const [sort, setSort] = useState("newest");
  const [kbChartView, setKbChartView] = useState<KbChartView>("per_day");
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(150);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    fetchAnalysis({
      region,
      review_state: reason === "kb_issue" ? "immediate_or_kb" : scope,
      attention_reason: reason,
      category,
      confidence,
      has_feedback: hasFeedback,
      date_range: dateRange,
      tenant: tenantFilter.trim(),
      query: search.trim(),
      include_analytics: true,
      sort,
      limit: rowsPerPage,
      offset: page * rowsPerPage,
    })
      .then(setData)
      .catch(() => setError("Immediate-action conversations could not be loaded."))
      .finally(() => setLoading(false));
  }, [category, confidence, dateRange, hasFeedback, page, reason, region, rowsPerPage, scope, search, sort, tenantFilter]);

  useEffect(() => {
    if (!regionLoading) load();
  }, [load, regionLoading]);

  const analytics = data?.analytics;
  const hasFilters = Boolean(
    search || tenantFilter || reason || category || confidence || hasFeedback || dateRange || scope !== "immediate_attention" || sort !== "newest",
  );

  function clearFilters() {
    setSearch("");
    setTenantFilter("");
    setScope("immediate_attention");
    setReason("");
    setCategory("");
    setConfidence("");
    setHasFeedback("");
    setDateRange("");
    setSort("newest");
    setPage(0);
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="overline" color="error.main">Operational priority</Typography>
        <Typography variant="h1" component="h1">Immediate Action</Typography>
        <Typography color="text.secondary" sx={{ mt: 1, maxWidth: 840 }}>
          JAI responses requiring urgent review—guardrail bypasses, empty answers, rate limits, high frustration, operational failures, source-code leakage, and knowledge-base gaps—with tenant impact and daily trend analytics.
        </Typography>
      </Box>

      {error && <Alert severity="error" action={<Button color="inherit" onClick={load}>Retry</Button>}><AlertTitle>Immediate Action unavailable</AlertTitle>{error}</Alert>}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", lg: "repeat(6, 1fr)" }, gap: 2 }}>
        <Paper sx={{ p: 2 }}><Typography variant="caption" color="text.secondary">Matching rows</Typography><Typography variant="h2" sx={{ mt: 0.5 }}>{data?.total ?? "—"}</Typography></Paper>
        <Paper sx={{ p: 2 }}><Typography variant="caption" color="text.secondary">Immediate attention</Typography><Typography variant="h2" sx={{ mt: 0.5, color: "error.main" }}>{analytics?.immediate_attention ?? data?.total ?? "—"}</Typography></Paper>
        <Paper sx={{ p: 2 }}><Typography variant="caption" color="text.secondary">Empty final responses</Typography><Typography variant="h2" sx={{ mt: 0.5, color: "#EA580C" }}>{analytics?.empty_final_response ?? 0}</Typography></Paper>
        <Paper sx={{ p: 2 }}><Typography variant="caption" color="text.secondary">Guardrail bypasses</Typography><Typography variant="h2" sx={{ mt: 0.5, color: "error.main" }}>{analytics?.guardrail_bypass ?? 0}</Typography></Paper>
        <Paper sx={{ p: 2 }}><Typography variant="caption" color="text.secondary">KB issues</Typography><Typography variant="h2" sx={{ mt: 0.5, color: "warning.dark" }}>{analytics?.kb_issues ?? 0}</Typography></Paper>
        <Paper sx={{ p: 2 }}><Typography variant="caption" color="text.secondary">Affected tenants</Typography><Typography variant="h2" sx={{ mt: 0.5 }}>{analytics?.affected_tenants ?? 0}</Typography></Paper>
      </Box>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "repeat(2, minmax(0, 1fr))" }, gap: 2 }}>
        <KbTrendCard analytics={analytics} view={kbChartView} onViewChange={setKbChartView} />
        <SeriousIssuesTrendCard
          analytics={analytics}
          onSelectReason={(next) => {
            setReason(next);
            setPage(0);
          }}
        />
      </Box>

      {analytics && analytics.top_tenants.length > 0 && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle2">Most impacted tenants in current window</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
            {analytics.top_tenants.slice(0, 8).map((row) => (
              <Chip
                key={`${row.tenant_id ?? row.tenant_name}`}
                size="small"
                variant="outlined"
                onClick={() => {
                  setTenantFilter(row.tenant_id || row.tenant_name);
                  setPage(0);
                }}
                label={`${row.tenant_name} (${row.tenant_id ?? "no-id"}): ${row.total} (${row.empty_final_response} empty · ${row.guardrail_bypass} bypass · ${row.kb_issues} KB)`}
              />
            ))}
          </Stack>
        </Paper>
      )}

      <Paper sx={{ p: 2, display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", lg: "repeat(4, minmax(0, 1fr))" }, gap: 1.5 }}>
        <TextField
          size="small"
          label="Search"
          placeholder="Conversation ID, title, tenant, or action"
          value={search}
          onChange={(event) => { setSearch(event.target.value); setPage(0); }}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment> }}
        />
        <TextField
          size="small"
          label="Tenant name or ID"
          placeholder="e.g. UB Suny or 1007"
          value={tenantFilter}
          onChange={(event) => { setTenantFilter(event.target.value); setPage(0); }}
        />
        <TextField select size="small" label="Issue scope" value={scope} onChange={(event) => { setScope(event.target.value as "immediate_attention" | "kb_issue" | "immediate_or_kb"); setPage(0); }}>
          <MenuItem value="immediate_attention">Immediate attention only</MenuItem>
          <MenuItem value="kb_issue">KB issues only</MenuItem>
          <MenuItem value="immediate_or_kb">Immediate attention + KB issues</MenuItem>
        </TextField>
        <TextField select size="small" label="Attention reason" value={reason} onChange={(event) => { setReason(event.target.value); setPage(0); }}>
          <MenuItem value="">All urgent reasons</MenuItem>
          {REASONS.map((value) => <MenuItem key={value} value={value}>{label(value)}</MenuItem>)}
        </TextField>
        <TextField select size="small" label="Classification" value={category} onChange={(event) => { setCategory(event.target.value); setPage(0); }}>
          <MenuItem value="">All classifications</MenuItem>
          {CATEGORIES.map((value) => <MenuItem key={value} value={value}>{CATEGORY_META[value].label}</MenuItem>)}
        </TextField>
        <TextField select size="small" label="Confidence" value={confidence} onChange={(event) => { setConfidence(event.target.value); setPage(0); }}>
          <MenuItem value="">All confidence levels</MenuItem>
          <MenuItem value="high">High</MenuItem>
          <MenuItem value="medium">Medium</MenuItem>
          <MenuItem value="low">Low</MenuItem>
        </TextField>
        <TextField select size="small" label="Activity window" value={dateRange} onChange={(event) => { setDateRange(event.target.value); setPage(0); }}>
          <MenuItem value="">All analysed dates</MenuItem>
          <MenuItem value="last_7_days">Last 7 days</MenuItem>
          <MenuItem value="last_15_days">Last 15 days</MenuItem>
          <MenuItem value="last_30_days">Last 30 days</MenuItem>
        </TextField>
        <Stack direction="row" spacing={1}>
          <TextField fullWidth select size="small" label="User feedback" value={hasFeedback} onChange={(event) => { setHasFeedback(event.target.value); setPage(0); }}>
            <MenuItem value="">All</MenuItem>
            <MenuItem value="yes">Has thumbs feedback</MenuItem>
            <MenuItem value="no">No thumbs feedback</MenuItem>
          </TextField>
          <TextField fullWidth select size="small" label="Sort" value={sort} onChange={(event) => { setSort(event.target.value); setPage(0); }}>
            <MenuItem value="newest">Newest</MenuItem>
            <MenuItem value="oldest">Oldest</MenuItem>
            <MenuItem value="attention">Priority</MenuItem>
            <MenuItem value="confidence">Lowest confidence</MenuItem>
          </TextField>
        </Stack>
      </Paper>

      <TableContainer component={Paper} sx={{ overflowX: "auto" }} aria-busy={loading}>
        {loading && <LinearProgress aria-label="Loading immediate actions" />}
        <Box sx={{ px: 2.5, py: 1.75, display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid", borderColor: "divider" }}>
          <Typography variant="body2" color="text.secondary">
            Showing up to <b>{rowsPerPage}</b> rows per page · <b>{data?.total ?? 0}</b> matching conversations in {region ? region.toUpperCase() : "all regions"}
          </Typography>
          {hasFilters && <Button size="small" onClick={clearFilters}>Clear filters</Button>}
        </Box>
        <Table aria-label="Immediate action conversations" sx={{ minWidth: 1320 }}>
          <TableHead>
            <TableRow>
              <TableCell>Conversation</TableCell>
              <TableCell>Tenant name & ID</TableCell>
              <TableCell>Immediate reason</TableCell>
              <TableCell>Classification</TableCell>
              <TableCell>Recommended action</TableCell>
              <TableCell>Last activity / analysed</TableCell>
              <TableCell align="right">Open</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? [1, 2, 3].map((row) => <TableRow key={row}>{[1, 2, 3, 4, 5, 6, 7].map((cell) => <TableCell key={cell}><Skeleton /></TableCell>)}</TableRow>) : data?.items.length ? data.items.map((item) => (
              <TableRow key={item.conversation_id} hover>
                <TableCell sx={{ width: 270 }}>
                  {item.title && (
                    <MuiLink component={Link} href={`/conversations/${item.conversation_id}`} underline="hover" sx={{ color: "text.primary", fontWeight: 750, display: "block" }}>
                      {item.title}
                    </MuiLink>
                  )}
                  <Link href={`/conversations/${item.conversation_id}`} style={{ color: "inherit", fontWeight: item.title ? 600 : 750, textDecoration: "none", overflowWrap: "anywhere" }}>
                    {item.conversation_id}
                  </Link>
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.75 }}>
                    {item.region && <Chip size="small" label={item.region.toUpperCase()} color="primary" variant="outlined" />}
                    {item.has_feedback && <Chip size="small" label="Feedback" color="secondary" variant="outlined" />}
                  </Stack>
                </TableCell>
                <TableCell sx={{ width: 220 }}>
                  <Typography variant="body2" sx={{ fontWeight: 750 }}>
                    {item.tenant_name || "Tenant unavailable"}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", fontFamily: "monospace" }}>
                    ID: {item.tenant_id || "Unavailable"}
                  </Typography>
                  {item.ea && <Box sx={{ mt: 0.5 }}><EABadge ea={item.ea} /></Box>}
                </TableCell>
                <TableCell sx={{ minWidth: 230 }}>
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                    {item.attention_reasons.map((value) => <Chip key={value} size="small" color={value === "guardrail_bypass" ? "error" : "warning"} icon={<WarningAmberRoundedIcon />} label={label(value)} />)}
                    {item.kb_issue && <Chip size="small" color="info" variant="outlined" label="KB Issue" />}
                  </Stack>
                </TableCell>
                <TableCell>
                  <CategoryChip category={item.category} />
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
                    {item.confidence ? `${label(item.confidence)} confidence` : "Confidence unavailable"}
                  </Typography>
                </TableCell>
                <TableCell sx={{ minWidth: 280, maxWidth: 420 }}><Box sx={{ maxHeight: 60, overflow: "hidden" }}><MarkdownContent>{item.recommended_next_step}</MarkdownContent></Box></TableCell>
                <TableCell sx={{ whiteSpace: "nowrap" }}>
                  <Typography variant="body2">{formatDate(item.last_message_at ?? item.analyzed_at)}</Typography>
                  <Typography variant="caption" color="text.secondary">Analysed {formatDate(item.analyzed_at)}</Typography>
                </TableCell>
                <TableCell align="right"><Button component={Link} href={`/conversations/${item.conversation_id}`} size="small" endIcon={<ArrowForwardRoundedIcon />}>Review</Button></TableCell>
              </TableRow>
            )) : <TableRow><TableCell colSpan={7}><Box sx={{ py: 8, textAlign: "center" }}><ErrorOutlineRoundedIcon sx={{ fontSize: 38, color: "text.disabled" }} /><Typography variant="h3" sx={{ mt: 1 }}>No immediate actions match</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>Try another reason, tenant, date window, or region.</Typography></Box></TableCell></TableRow>}
          </TableBody>
        </Table>
        <TablePagination
          component="div"
          count={data?.total ?? 0}
          page={page}
          rowsPerPage={rowsPerPage}
          rowsPerPageOptions={[25, 50, 100, 150]}
          onPageChange={(_, nextPage) => setPage(nextPage)}
          onRowsPerPageChange={(event) => { setRowsPerPage(Number(event.target.value)); setPage(0); }}
          labelRowsPerPage="Actions per page"
        />
      </TableContainer>
    </Stack>
  );
}
