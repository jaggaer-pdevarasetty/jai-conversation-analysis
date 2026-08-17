"use client";

import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import ChatBubbleOutlineRoundedIcon from "@mui/icons-material/ChatBubbleOutlineRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import TuneRoundedIcon from "@mui/icons-material/TuneRounded";
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Chip,
  InputAdornment,
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
  Typography,
} from "@mui/material";
import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchAnalysis, type ListItem } from "../services/analysisApi";
import { CategoryChip } from "./CategoryChip";
import { MarkdownContent } from "./MarkdownContent";
import { useRegion } from "./RegionContext";

const CATEGORY_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "All categories" },
  { value: "resolved", label: "JAI resolved user query" },
  { value: "failed_to_resolve", label: "JAI failed to resolve" },
  { value: "positive_feedback", label: "Positive feedback" },
  { value: "negative_feedback", label: "Negative feedback" },
  { value: "out_of_scope", label: "Out of scope" },
];

/** AC-7: missing telemetry is shown as "unavailable", never 0. */
function metric(value: number | null): string {
  return value === null || value === undefined ? "unavailable" : value.toLocaleString();
}

function latency(value: number | null): string {
  if (value === null || value === undefined) return "unavailable";
  return value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(1)} s`;
}

function formatDate(value?: string): string {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function confidenceColor(confidence: string): "success" | "warning" | "default" {
  if (confidence === "high") return "success";
  if (confidence === "low") return "warning";
  return "default";
}

export function ReviewerTable() {
  const [items, setItems] = useState<ListItem[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [total, setTotal] = useState(0);
  const [unanalysed, setUnanalysed] = useState(0);
  const [category, setCategory] = useState("");
  const [confidence, setConfidence] = useState("");
  const [reviewState, setReviewState] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const { region, loading: regionLoading } = useRegion();

  useEffect(() => {
    const timer = setTimeout(() => {
      setPage(0);
      setQuery(search.trim());
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (regionLoading) return;
    let active = true;
    setLoading(true);
    setError(null);
    fetchAnalysis({
      category,
      region,
      query,
      confidence,
      review_state: reviewState,
      sort,
      limit: rowsPerPage,
      offset: page * rowsPerPage,
    })
      .then((res) => {
        if (!active) return;
        setItems(res.items);
        setCounts(res.counts);
        setTotal(res.total);
        setUnanalysed(res.unanalysed);
      })
      .catch(() => {
        if (active) setError("The review queue could not be loaded. Check the API connection and try again.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [category, confidence, page, query, region, regionLoading, reload, reviewState, rowsPerPage, sort]);

  const needsAttention = (counts.failed_to_resolve ?? 0) + (counts.negative_feedback ?? 0) + (counts.out_of_scope ?? 0);
  const hasFilters = Boolean(category || confidence || reviewState || search || sort !== "newest");
  const firstResult = total ? page * rowsPerPage + 1 : 0;
  const lastResult = Math.min((page + 1) * rowsPerPage, total);

  function resetFilters() {
    setCategory("");
    setConfidence("");
    setReviewState("");
    setSearch("");
    setQuery("");
    setSort("newest");
    setPage(0);
  }

  return (
    <Stack spacing={2.5}>
      {unanalysed > 0 && (
        <Alert severity="warning">
          <AlertTitle>{unanalysed} {unanalysed === 1 ? "conversation is" : "conversations are"} not yet analysed</AlertTitle>
          They remain queued and will be retried during the next scheduled run.
        </Alert>
      )}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" }, gap: 1.5 }}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Matching conversations</Typography>
          <Typography variant="h3" sx={{ mt: 0.4 }}>{total.toLocaleString()}</Typography>
        </Paper>
        <Paper sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Needs attention</Typography>
          <Typography variant="h3" sx={{ mt: 0.4, color: "error.main" }}>{needsAttention.toLocaleString()}</Typography>
        </Paper>
        <Paper sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Overrides on this page</Typography>
          <Typography variant="h3" sx={{ mt: 0.4 }}>{items.filter((item) => item.overridden).length.toLocaleString()}</Typography>
        </Paper>
      </Box>

      <Paper sx={{ p: 2, display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", lg: "repeat(3, minmax(0, 1fr))" }, gap: 1.5, alignItems: "center" }}>
        <TextField
          fullWidth
          size="small"
          label="Search conversations"
          placeholder="ID or recommended action"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment> }}
        />
        <TextField fullWidth select size="small" label="Filter by category" value={category} onChange={(event) => { setCategory(event.target.value); setPage(0); }}>
          {CATEGORY_OPTIONS.map((option) => <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>)}
        </TextField>
        <TextField fullWidth select size="small" label="Confidence" value={confidence} onChange={(event) => { setConfidence(event.target.value); setPage(0); }}>
          <MenuItem value="">All confidence</MenuItem>
          <MenuItem value="low">Low confidence</MenuItem>
          <MenuItem value="medium">Medium confidence</MenuItem>
          <MenuItem value="high">High confidence</MenuItem>
        </TextField>
        <TextField fullWidth select size="small" label="Review state" value={reviewState} onChange={(event) => { setReviewState(event.target.value); setPage(0); }}>
          <MenuItem value="">All conversations</MenuItem>
          <MenuItem value="attention">Needs attention</MenuItem>
          <MenuItem value="feedback">Has feedback</MenuItem>
          <MenuItem value="overridden">Human override</MenuItem>
          <MenuItem value="missing_telemetry">Missing telemetry</MenuItem>
        </TextField>
        <TextField fullWidth select size="small" label="Sort" value={sort} onChange={(event) => { setSort(event.target.value); setPage(0); }}>
          <MenuItem value="newest">Newest conversation</MenuItem>
          <MenuItem value="oldest">Oldest conversation</MenuItem>
          <MenuItem value="attention">Attention first</MenuItem>
          <MenuItem value="confidence">Lowest confidence</MenuItem>
          <MenuItem value="slowest">Slowest response</MenuItem>
          <MenuItem value="tokens">Highest token use</MenuItem>
        </TextField>
      </Paper>

      {error ? (
        <Alert severity="error" action={<Button color="inherit" onClick={() => setReload((value) => value + 1)}>Try again</Button>}>
          <AlertTitle>Review queue unavailable</AlertTitle>
          {error}
        </Alert>
      ) : (
        <TableContainer component={Paper} sx={{ overflowX: "auto" }}>
          <Box sx={{ px: 2.5, py: 2, display: "flex", alignItems: "center", gap: 1.25, borderBottom: "1px solid", borderColor: "divider" }}>
            <TuneRoundedIcon sx={{ color: "text.secondary", fontSize: 20 }} />
            <Typography variant="body2" sx={{ fontWeight: 750 }}>
              {loading ? "Loading conversations" : total ? `Showing ${firstResult.toLocaleString()}–${lastResult.toLocaleString()} of ${total.toLocaleString()}` : "No conversations"}
            </Typography>
            {hasFilters && <Button size="small" onClick={resetFilters} sx={{ ml: "auto" }}>Clear filters</Button>}
          </Box>
          <Table aria-label="Analysed conversations" sx={{ minWidth: 920 }}>
            <TableHead>
              <TableRow>
                <TableCell>Conversation</TableCell>
                <TableCell>Classification</TableCell>
                <TableCell>Recommended action</TableCell>
                <TableCell>Confidence</TableCell>
                <TableCell sx={{ display: { xs: "none", lg: "table-cell" } }}>Performance</TableCell>
                <TableCell sx={{ display: { xs: "none", xl: "table-cell" } }}>Feedback</TableCell>
                <TableCell align="right">Open</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? [1, 2, 3, 4].map((row) => (
                <TableRow key={row}>
                  {[1, 2, 3, 4, 5, 6, 7].map((cell) => <TableCell key={cell}><Skeleton /></TableCell>)}
                </TableRow>
              )) : items.length ? items.map((item) => (
                <TableRow key={item.conversation_id} hover sx={{ "&:hover": { bgcolor: "#FCFCFD" } }}>
                  <TableCell sx={{ width: 255 }}>
                    <MuiLink component={Link} href={`/conversations/${item.conversation_id}`} underline="hover" sx={{ display: "block", color: "text.primary", fontWeight: 750, fontSize: 13, overflowWrap: "anywhere" }}>
                      {item.conversation_id}
                    </MuiLink>
                    <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>Last message {formatDate(item.last_message_at ?? item.analyzed_at)}</Typography>
                    <Typography variant="caption" color="text.secondary">Analysed {formatDate(item.analyzed_at)}</Typography>
                  </TableCell>
                  <TableCell sx={{ width: 175 }}>
                    <CategoryChip category={item.category} />
                    {item.overridden && <Typography variant="caption" sx={{ display: "block", mt: 0.6, color: "warning.dark", fontWeight: 700 }}>Human override</Typography>}
                  </TableCell>
                  <TableCell sx={{ minWidth: 250, maxWidth: 390 }}>
                    <Box sx={{ maxHeight: 52, overflow: "hidden" }}><MarkdownContent>{item.recommended_next_step}</MarkdownContent></Box>
                  </TableCell>
                  <TableCell>
                    <Chip size="small" variant="outlined" color={confidenceColor(item.confidence)} label={`${item.confidence[0]?.toUpperCase()}${item.confidence.slice(1)}`} />
                  </TableCell>
                  <TableCell sx={{ display: { xs: "none", lg: "table-cell" }, whiteSpace: "nowrap" }}>
                    <Typography variant="body2" sx={{ fontWeight: 700 }}>{latency(item.metrics.ttft_ms)}</Typography>
                    <Typography variant="caption" color="text.secondary">{metric(item.metrics.input_tokens)} / {metric(item.metrics.output_tokens)} tokens</Typography>
                  </TableCell>
                  <TableCell sx={{ display: { xs: "none", xl: "table-cell" } }}>
                    {item.has_feedback ? <Chip size="small" icon={<ChatBubbleOutlineRoundedIcon />} label="Provided" variant="outlined" /> : <Typography variant="body2" color="text.secondary">None</Typography>}
                  </TableCell>
                  <TableCell align="right">
                    <Button component={Link} href={`/conversations/${item.conversation_id}`} size="small" endIcon={<ArrowForwardRoundedIcon />} aria-label={`Review conversation ${item.conversation_id}`}>Review</Button>
                  </TableCell>
                </TableRow>
              )) : (
                <TableRow>
                  <TableCell colSpan={7}>
                    <Box sx={{ py: 7, textAlign: "center" }}>
                      <SearchRoundedIcon sx={{ fontSize: 34, color: "text.disabled" }} />
                      <Typography variant="h3" sx={{ mt: 1 }}>{hasFilters ? "No conversations match" : "No conversations available"}</Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{hasFilters ? "Try a different ID, action, category, confidence, or review state." : "No analysed conversations are available in this scope."}</Typography>
                      {hasFilters && <Button sx={{ mt: 2 }} onClick={resetFilters}>Clear filters</Button>}
                    </Box>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          <TablePagination
            component="div"
            count={total}
            page={page}
            rowsPerPage={rowsPerPage}
            rowsPerPageOptions={[10, 25, 50, 100]}
            onPageChange={(_, nextPage) => setPage(nextPage)}
            onRowsPerPageChange={(event) => { setRowsPerPage(Number(event.target.value)); setPage(0); }}
            labelRowsPerPage="Conversations per page"
          />
        </TableContainer>
      )}
    </Stack>
  );
}
