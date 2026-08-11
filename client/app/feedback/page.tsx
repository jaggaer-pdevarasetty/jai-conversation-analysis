"use client";

import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import ChatBubbleOutlineRoundedIcon from "@mui/icons-material/ChatBubbleOutlineRounded";
import ErrorOutlineRoundedIcon from "@mui/icons-material/ErrorOutlineRounded";
import InsightsRoundedIcon from "@mui/icons-material/InsightsRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import ThumbDownAltRoundedIcon from "@mui/icons-material/ThumbDownAltRounded";
import ThumbUpAltRoundedIcon from "@mui/icons-material/ThumbUpAltRounded";
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
import { useCallback, useEffect, useMemo, useState } from "react";
import { CATEGORIES, fetchFeedback, type FeedbackItem, type FeedbackListResponse } from "../../src/services/analysisApi";
import { CATEGORY_META, CategoryChip } from "../../src/components/CategoryChip";
import { StatCard } from "../../src/components/StatCard";

function formatDate(value?: string | null): string {
  if (!value) return "Unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unavailable";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function tokenTotal(item: FeedbackItem): string {
  if (item.input_tokens === null || item.input_tokens === undefined || item.output_tokens === null || item.output_tokens === undefined) return "Unavailable";
  return (item.input_tokens + item.output_tokens).toLocaleString();
}

export default function FeedbackPage() {
  const [data, setData] = useState<FeedbackListResponse | null>(null);
  const [search, setSearch] = useState("");
  const [rating, setRating] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("negative_first");
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    fetchFeedback()
      .then(setData)
      .catch(() => setError("The explicit-feedback records could not be loaded. Check the API connection and try again."));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filteredItems = useMemo(() => {
    const query = search.trim().toLowerCase();
    const items = (data?.items ?? []).filter((item) =>
      (!rating || (rating === "positive" ? item.rating : !item.rating)) &&
      (!category || item.category === category) &&
      (!query || [
        item.conversation_id,
        item.comment,
        item.title,
        item.tenant_name,
        item.user_name,
        item.recommended_next_step,
        item.why_it_happened,
      ].some((value) => String(value ?? "").toLowerCase().includes(query))),
    );
    return [...items].sort((a, b) => {
      if (sort === "newest") return (b.analyzed_at ?? "").localeCompare(a.analyzed_at ?? "");
      if (sort === "oldest") return (a.analyzed_at ?? "").localeCompare(b.analyzed_at ?? "");
      return Number(a.rating) - Number(b.rating);
    });
  }, [category, data, rating, search, sort]);

  if (error) {
    return <Alert severity="error" action={<Button color="inherit" onClick={load}>Try again</Button>}><AlertTitle>Feedback unavailable</AlertTitle>{error}</Alert>;
  }

  if (!data) {
    return <Stack spacing={2.5} aria-label="Loading feedback"><Skeleton variant="rounded" height={120} /><Skeleton variant="rounded" height={130} /><Skeleton variant="rounded" height={440} /></Stack>;
  }

  const positive = data.positive ?? data.items.filter((item) => item.rating).length;
  const negative = data.negative ?? data.items.filter((item) => !item.rating).length;
  const negativeRate = data.total ? Math.round((negative / data.total) * 100) : 0;
  const deepCoverage = data.total ? Math.round((data.items.filter((item) => item.deep).length / data.total) * 100) : 0;
  const visibleItems = filteredItems.slice(page * rowsPerPage, (page + 1) * rowsPerPage);
  const hasFilters = Boolean(search || rating || category || sort !== "negative_first");

  function clearFilters() {
    setSearch("");
    setRating("");
    setCategory("");
    setSort("negative_first");
    setPage(0);
  }

  return (
    <Stack spacing={3}>
      <Box sx={{ display: "flex", alignItems: { xs: "flex-start", lg: "flex-end" }, justifyContent: "space-between", gap: 2, flexDirection: { xs: "column", lg: "row" } }}>
        <Box>
          <Typography variant="overline" color="primary.main">Voice of the user</Typography>
          <Typography variant="h1" component="h1">Feedback intelligence</Typography>
          <Typography color="text.secondary" sx={{ mt: 1, maxWidth: 760 }}>
            Explicit thumbs ratings connected to conversation context, root-cause analysis, remediation guidance, and operational telemetry.
          </Typography>
        </Box>
        <Chip icon={<ChatBubbleOutlineRoundedIcon />} label="Explicit feedback only" variant="outlined" sx={{ bgcolor: "#FFFFFF" }} />
      </Box>

      {negative > 0 && (
        <Alert severity="warning">
          <AlertTitle>{negative} negative {negative === 1 ? "rating requires" : "ratings require"} attention</AlertTitle>
          Negative feedback is prioritised first so reviewers can move directly from the user remark to the complete conversation and root cause.
        </Alert>
      )}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", xl: "repeat(4, 1fr)" }, gap: 2 }}>
        <StatCard label="Explicit ratings" value={data.total.toLocaleString()} helper="Feedback conversations currently available" icon={<ChatBubbleOutlineRoundedIcon />} />
        <StatCard label="Negative feedback" value={negative.toLocaleString()} helper={`${negativeRate}% of explicit ratings`} icon={<ThumbDownAltRoundedIcon />} tone="#C43D4B" />
        <StatCard label="Positive feedback" value={positive.toLocaleString()} helper="Confirmed positive experiences" icon={<ThumbUpAltRoundedIcon />} tone="#16815D" />
        <StatCard label="Deep analysis coverage" value={`${deepCoverage}%`} helper="Records with root-cause guidance" icon={<InsightsRoundedIcon />} tone="#6B55B5" />
      </Box>

      <Paper sx={{ p: 2, display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", xl: "minmax(280px, 1.4fr) repeat(3, minmax(180px, 1fr))" }, gap: 1.5 }}>
        <TextField
          fullWidth
          size="small"
          label="Search feedback"
          placeholder="Remark, title, tenant, user, or conversation ID"
          value={search}
          onChange={(event) => { setSearch(event.target.value); setPage(0); }}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment> }}
        />
        <TextField fullWidth select size="small" label="Sentiment" value={rating} onChange={(event) => { setRating(event.target.value); setPage(0); }}>
          <MenuItem value="">All ratings</MenuItem>
          <MenuItem value="negative">Negative</MenuItem>
          <MenuItem value="positive">Positive</MenuItem>
        </TextField>
        <TextField fullWidth select size="small" label="Category" value={category} onChange={(event) => { setCategory(event.target.value); setPage(0); }}>
          <MenuItem value="">All categories</MenuItem>
          {CATEGORIES.map((value) => <MenuItem key={value} value={value}>{CATEGORY_META[value].label}</MenuItem>)}
        </TextField>
        <TextField fullWidth select size="small" label="Sort" value={sort} onChange={(event) => { setSort(event.target.value); setPage(0); }}>
          <MenuItem value="negative_first">Negative first</MenuItem>
          <MenuItem value="newest">Newest analysis</MenuItem>
          <MenuItem value="oldest">Oldest analysis</MenuItem>
        </TextField>
      </Paper>

      <TableContainer component={Paper}>
        <Box sx={{ px: 2.5, py: 2, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2, borderBottom: "1px solid", borderColor: "divider" }}>
          <Box>
            <Typography variant="h3">Feedback records</Typography>
            <Typography variant="body2" color="text.secondary">{filteredItems.length} matching {filteredItems.length === 1 ? "conversation" : "conversations"}</Typography>
          </Box>
          {hasFilters && <Button size="small" onClick={clearFilters}>Clear filters</Button>}
        </Box>
        <Table aria-label="Feedback conversations" sx={{ minWidth: 1220 }}>
          <TableHead>
            <TableRow>
              <TableCell>Rating & user remark</TableCell>
              <TableCell>Conversation</TableCell>
              <TableCell>Tenant & user</TableCell>
              <TableCell>Analysis</TableCell>
              <TableCell>Root cause</TableCell>
              <TableCell>Tokens</TableCell>
              <TableCell align="right">Open</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {visibleItems.length ? visibleItems.map((item) => (
              <TableRow key={item.conversation_id} hover>
                <TableCell sx={{ width: 260 }}>
                  <Chip
                    size="small"
                    icon={item.rating ? <ThumbUpAltRoundedIcon /> : <ThumbDownAltRoundedIcon />}
                    label={item.rating ? "Positive" : "Negative"}
                    color={item.rating ? "success" : "error"}
                    variant="outlined"
                  />
                  <Typography variant="body2" sx={{ mt: 1, fontWeight: 650, display: "-webkit-box", WebkitBoxOrient: "vertical", WebkitLineClamp: 3, overflow: "hidden" }}>
                    {item.comment ? `“${item.comment}”` : "No written remark"}
                  </Typography>
                </TableCell>
                <TableCell sx={{ width: 260 }}>
                  <MuiLink component={Link} href={`/feedback/${item.conversation_id}`} underline="hover" sx={{ color: "text.primary", fontWeight: 750, display: "block" }}>
                    {item.title || `Conversation ${item.conversation_id.slice(0, 8)}`}
                  </MuiLink>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", overflowWrap: "anywhere" }}>{item.conversation_id}</Typography>
                  <Typography variant="caption" color="text.secondary">{formatDate(item.last_message_at ?? item.analyzed_at)}</Typography>
                </TableCell>
                <TableCell sx={{ width: 210 }}>
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>{item.tenant_name || "Tenant unavailable"}</Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", overflowWrap: "anywhere" }}>{item.user_name || "User unavailable"}</Typography>
                </TableCell>
                <TableCell sx={{ width: 180 }}>
                  <CategoryChip category={item.category} />
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.75 }}>{item.confidence ? `${item.confidence[0].toUpperCase()}${item.confidence.slice(1)} confidence` : "Confidence unavailable"}</Typography>
                </TableCell>
                <TableCell sx={{ minWidth: 280, maxWidth: 420 }}>
                  <Typography variant="body2" color={item.why_it_happened ? "text.primary" : "text.secondary"} sx={{ display: "-webkit-box", WebkitBoxOrient: "vertical", WebkitLineClamp: 3, overflow: "hidden" }}>
                    {item.why_it_happened || "Root-cause analysis is not available yet."}
                  </Typography>
                </TableCell>
                <TableCell sx={{ whiteSpace: "nowrap" }}>
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>{tokenTotal(item)}</Typography>
                  <Typography variant="caption" color="text.secondary">input + output</Typography>
                </TableCell>
                <TableCell align="right">
                  <Button component={Link} href={`/feedback/${item.conversation_id}`} size="small" endIcon={<ArrowForwardRoundedIcon />} aria-label={`Review feedback for ${item.conversation_id}`}>Review</Button>
                </TableCell>
              </TableRow>
            )) : (
              <TableRow><TableCell colSpan={7}><Box sx={{ py: 8, textAlign: "center" }}><ErrorOutlineRoundedIcon sx={{ fontSize: 38, color: "text.disabled" }} /><Typography variant="h3" sx={{ mt: 1 }}>No feedback matches</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>Try a different sentiment, category, or search term.</Typography><Button sx={{ mt: 2 }} onClick={clearFilters}>Clear filters</Button></Box></TableCell></TableRow>
            )}
          </TableBody>
        </Table>
        <TablePagination
          component="div"
          count={filteredItems.length}
          page={page}
          rowsPerPage={rowsPerPage}
          rowsPerPageOptions={[5, 10, 25]}
          onPageChange={(_, nextPage) => setPage(nextPage)}
          onRowsPerPageChange={(event) => { setRowsPerPage(Number(event.target.value)); setPage(0); }}
          labelRowsPerPage="Feedback per page"
        />
      </TableContainer>
    </Stack>
  );
}
