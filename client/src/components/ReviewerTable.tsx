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
  FormControl,
  InputAdornment,
  InputLabel,
  Link as MuiLink,
  MenuItem,
  Paper,
  Select,
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
import { useEffect, useMemo, useState } from "react";
import { fetchAnalysis, type ListItem, type ListResponse } from "../services/analysisApi";
import { CategoryChip } from "./CategoryChip";

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

export function ReviewerTable({ initial }: { initial?: ListResponse }) {
  const [items, setItems] = useState<ListItem[]>(initial?.items ?? []);
  const [unanalysed, setUnanalysed] = useState<number>(initial?.unanalysed ?? 0);
  const [category, setCategory] = useState("");
  const [confidence, setConfidence] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("attention");
  const [loading, setLoading] = useState(!initial);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    if (initial) return;
    let active = true;
    setLoading(true);
    setError(null);
    fetchAnalysis(category)
      .then((res) => {
        if (!active) return;
        setItems(res.items);
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
  }, [category, initial, reload]);

  const visibleItems = useMemo(() => {
    const query = search.trim().toLowerCase();
    const filtered = items.filter(
      (item) =>
        (!confidence || item.confidence === confidence) &&
        (!query ||
          item.conversation_id.toLowerCase().includes(query) ||
          item.recommended_next_step.toLowerCase().includes(query)),
    );
    const priority: Record<string, number> = {
      negative_feedback: 0,
      failed_to_resolve: 1,
      out_of_scope: 2,
      positive_feedback: 3,
      resolved: 4,
    };
    return [...filtered].sort((a, b) => {
      if (sort === "newest") return (b.analyzed_at ?? "").localeCompare(a.analyzed_at ?? "");
      if (sort === "confidence") return ({ low: 0, medium: 1, high: 2 }[a.confidence] ?? 3) - ({ low: 0, medium: 1, high: 2 }[b.confidence] ?? 3);
      return (priority[a.category] ?? 9) - (priority[b.category] ?? 9);
    });
  }, [confidence, items, search, sort]);

  const needsAttention = items.filter((item) => ["failed_to_resolve", "negative_feedback", "out_of_scope"].includes(item.category)).length;
  const hasFilters = Boolean(category || confidence || search);

  function resetFilters() {
    setCategory("");
    setConfidence("");
    setSearch("");
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
          <Typography variant="caption" color="text.secondary">Loaded conversations</Typography>
          <Typography variant="h3" sx={{ mt: 0.4 }}>{items.length.toLocaleString()}</Typography>
        </Paper>
        <Paper sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Needs attention</Typography>
          <Typography variant="h3" sx={{ mt: 0.4, color: "error.main" }}>{needsAttention.toLocaleString()}</Typography>
        </Paper>
        <Paper sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Human overrides</Typography>
          <Typography variant="h3" sx={{ mt: 0.4 }}>{items.filter((item) => item.overridden).length.toLocaleString()}</Typography>
        </Paper>
      </Box>

      <Paper sx={{ p: 2, display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(240px, 1fr) repeat(3, minmax(170px, auto))" }, gap: 1.5, alignItems: "center" }}>
        <TextField
          size="small"
          label="Search conversations"
          placeholder="ID or recommended action"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment> }}
        />
        <FormControl size="small">
          <InputLabel htmlFor="category-filter">Filter by category</InputLabel>
          <Select
            native
            value={category}
            label="Filter by category"
            onChange={(event) => setCategory(String(event.target.value))}
            inputProps={{ id: "category-filter" }}
          >
            {CATEGORY_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </Select>
        </FormControl>
        <FormControl size="small">
          <InputLabel htmlFor="confidence-filter">Confidence</InputLabel>
          <Select native value={confidence} label="Confidence" onChange={(event) => setConfidence(String(event.target.value))} inputProps={{ id: "confidence-filter" }}>
            <option value="">All confidence</option>
            <option value="low">Low confidence</option>
            <option value="medium">Medium confidence</option>
            <option value="high">High confidence</option>
          </Select>
        </FormControl>
        <FormControl size="small">
          <InputLabel htmlFor="sort-order">Sort</InputLabel>
          <Select native value={sort} label="Sort" onChange={(event) => setSort(String(event.target.value))} inputProps={{ id: "sort-order" }}>
            <option value="attention">Attention first</option>
            <option value="newest">Newest analysis</option>
            <option value="confidence">Lowest confidence</option>
          </Select>
        </FormControl>
      </Paper>

      {error ? (
        <Alert severity="error" action={<Button color="inherit" onClick={() => setReload((value) => value + 1)}>Try again</Button>}>
          <AlertTitle>Review queue unavailable</AlertTitle>
          {error}
        </Alert>
      ) : (
        <TableContainer component={Paper}>
          <Box sx={{ px: 2.5, py: 2, display: "flex", alignItems: "center", gap: 1.25, borderBottom: "1px solid", borderColor: "divider" }}>
            <TuneRoundedIcon sx={{ color: "text.secondary", fontSize: 20 }} />
            <Typography variant="body2" sx={{ fontWeight: 750 }}>
              {loading ? "Loading conversations" : `${visibleItems.length.toLocaleString()} ${visibleItems.length === 1 ? "conversation" : "conversations"}`}
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
                <TableCell align="right"><span className="sr-only">Open</span></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? [1, 2, 3, 4].map((row) => (
                <TableRow key={row}>
                  {[1, 2, 3, 4, 5, 6, 7].map((cell) => <TableCell key={cell}><Skeleton /></TableCell>)}
                </TableRow>
              )) : visibleItems.length ? visibleItems.map((item) => (
                <TableRow key={item.conversation_id} hover sx={{ "&:hover": { bgcolor: "#FCFCFD" } }}>
                  <TableCell sx={{ width: 255 }}>
                    <MuiLink component={Link} href={`/conversations/${item.conversation_id}`} underline="hover" sx={{ display: "block", color: "text.primary", fontWeight: 750, fontSize: 13, overflowWrap: "anywhere" }}>
                      {item.conversation_id}
                    </MuiLink>
                    <Typography variant="caption" color="text.secondary">{formatDate(item.analyzed_at)}</Typography>
                  </TableCell>
                  <TableCell sx={{ width: 175 }}>
                    <CategoryChip category={item.category} />
                    {item.overridden && <Typography variant="caption" sx={{ display: "block", mt: 0.6, color: "warning.dark", fontWeight: 700 }}>Human override</Typography>}
                  </TableCell>
                  <TableCell sx={{ minWidth: 250, maxWidth: 390 }}>
                    <Typography variant="body2" sx={{ display: "-webkit-box", WebkitBoxOrient: "vertical", WebkitLineClamp: 2, overflow: "hidden" }}>{item.recommended_next_step}</Typography>
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
                      <Typography variant="h3" sx={{ mt: 1 }}>No conversations match</Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>Try a different ID, action, category, or confidence level.</Typography>
                      <Button sx={{ mt: 2 }} onClick={resetFilters}>Clear filters</Button>
                    </Box>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Stack>
  );
}
