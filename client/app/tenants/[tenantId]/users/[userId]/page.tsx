"use client";

import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import ChatBubbleOutlineRoundedIcon from "@mui/icons-material/ChatBubbleOutlineRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import {
  Alert,
  AlertTitle,
  Avatar,
  Box,
  Breadcrumbs,
  Button,
  Chip,
  CircularProgress,
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
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CategoryChip } from "../../../../../src/components/CategoryChip";
import { MarkdownContent } from "../../../../../src/components/MarkdownContent";
import { useRegion } from "../../../../../src/components/RegionContext";
import { StatCard } from "../../../../../src/components/StatCard";
import { analyzeConversation } from "../../../../../src/services/analysisApi";
import {
  fetchTenants,
  fetchTenantUsers,
  fetchUserConversations,
  type Tenant,
  type TenantUser,
  type UserConversation,
} from "../../../../../src/services/dashboardApi";

/** Per-conversation on-demand analyse (the way PROD conversations get analysed — only when a
 * reviewer clicks). The current environment is applied automatically by the API layer. */
function AnalyzeButton({ id, onDone }: { id: string; onDone: () => void | Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const run = async () => {
    setBusy(true);
    setFailed(false);
    try {
      await analyzeConversation(id);
      await onDone();
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button
      size="small"
      variant="outlined"
      disabled={busy}
      onClick={run}
      startIcon={busy ? <CircularProgress size={14} /> : <PlayArrowRoundedIcon />}
    >
      {busy ? "Analysing…" : failed ? "Retry" : "Analyze"}
    </Button>
  );
}

function StatusCell({ c }: { c: UserConversation }) {
  if (c.status === "analysing") {
    return (
      <Chip
        size="small"
        icon={<CircularProgress size={12} thickness={6} />}
        label="Analysing…"
        sx={{ bgcolor: "#fff7ed", color: "#b45309", fontWeight: 600 }}
      />
    );
  }
  if (c.status === "pending") return <Chip size="small" label="Queued" variant="outlined" />;
  return <CategoryChip category={c.category} />;
}

function formatDate(value: string | null): string {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export default function UserConversationsPage() {
  const params = useParams();
  const tenantId = String(params.tenantId);
  const userId = String(params.userId);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [user, setUser] = useState<TenantUser | null>(null);
  const [items, setItems] = useState<UserConversation[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [search, setSearch] = useState("");
  const [outcome, setOutcome] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { region, loading: regionLoading } = useRegion();

  const load = useCallback(
    () => {
      setError(null);
      return fetchUserConversations(tenantId, userId, rowsPerPage, page * rowsPerPage, region)
        .then((result) => {
          setItems(result.items);
          setTotal(result.total);
        })
        .catch(() => setError("The conversations could not be loaded. Check the API connection and try again."));
    },
    [page, rowsPerPage, tenantId, userId, region],
  );

  useEffect(() => {
    if (regionLoading) return;
    Promise.all([fetchTenants(region), fetchTenantUsers(tenantId, region)])
      .then(([tenants, users]) => {
        setTenant(tenants.find((item) => item.tenant_id === tenantId) ?? null);
        setUser(users.find((item) => item.user_id === userId) ?? null);
      })
      .catch(() => setError("The user context could not be loaded."));
    void load();
  }, [load, regionLoading, tenantId, userId, region]);

  // Auto-refresh while anything is still being analysed (lazy analyse in progress).
  useEffect(() => {
    if (!items?.some((c) => c.status === "analysing")) return;
    const t = setTimeout(load, 4000);
    return () => clearTimeout(t);
  }, [items, load]);

  const visibleItems = useMemo(() => {
    const query = search.trim().toLowerCase();
    return (items ?? []).filter((conversation) => {
      const matchesOutcome = !outcome || conversation.status === outcome || conversation.category === outcome;
      const matchesSearch = !query ||
        conversation.conversation_id.toLowerCase().includes(query) ||
        (conversation.title ?? "").toLowerCase().includes(query) ||
        (conversation.recommended_next_step ?? "").toLowerCase().includes(query);
      return matchesOutcome && matchesSearch;
    });
  }, [items, outcome, search]);

  if (error && !items) {
    return <Alert severity="error" action={<Button color="inherit" onClick={() => void load()}>Try again</Button>}><AlertTitle>Conversations unavailable</AlertTitle>{error}</Alert>;
  }

  if (!items) {
    return <Stack spacing={2.5} role="status" aria-label="Loading user conversations"><Skeleton variant="rounded" height={130} /><Skeleton variant="rounded" height={400} /></Stack>;
  }

  const analysed = items.filter((conversation) => conversation.status === "analysed").length;
  const analysing = items.filter((conversation) => conversation.status === "analysing").length;
  const waiting = items.filter((conversation) => conversation.status === "pending").length;
  const messages = items.reduce((total, conversation) => total + (conversation.message_count ?? 0), 0);
  const tenantName = tenant?.name ?? `Tenant ${tenantId}`;
  const userName = user?.user_name ?? `User ${userId}`;

  return (
    <Stack spacing={3}>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <Breadcrumbs aria-label="User conversation navigation">
        <MuiLink component={Link} href="/tenants" underline="hover">Tenants</MuiLink>
        <MuiLink component={Link} href={`/tenants/${tenantId}`} underline="hover">{tenantName}</MuiLink>
        <Typography color="text.primary">{userName}</Typography>
      </Breadcrumbs>

      <Box sx={{ display: "flex", alignItems: { xs: "flex-start", sm: "center" }, gap: 2, flexDirection: { xs: "column", sm: "row" } }}>
        <Avatar sx={{ width: 58, height: 58, bgcolor: "#FFF0E9", color: "primary.main", fontWeight: 800, fontSize: 22 }}>{userName.trim().charAt(0).toUpperCase() || "U"}</Avatar>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="overline" color="primary.main">User conversation history</Typography>
          <Typography variant="h1" component="h1" sx={{ overflowWrap: "anywhere" }}>{userName}</Typography>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mt: 0.75 }}>
            {user?.role && <Chip size="small" label={user.role} variant="outlined" />}
            <Typography variant="caption" color="text.secondary">User ID {userId}</Typography>
            <Typography variant="caption" color="text.secondary">· Tenant ID {tenantId}</Typography>
          </Stack>
        </Box>
        {analysing > 0 && (
          <Chip
            size="small"
            icon={<CircularProgress size={12} thickness={6} />}
            label={`Analysing ${analysing}`}
            sx={{ ml: { sm: "auto" }, bgcolor: "#fff7ed", color: "#b45309", fontWeight: 700 }}
          />
        )}
      </Box>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", xl: "repeat(4, 1fr)" }, gap: 2 }}>
        <StatCard label="Conversations" value={total.toLocaleString()} helper="All conversations for this user" icon={<ChatBubbleOutlineRoundedIcon />} />
        <StatCard label="Analysed on page" value={analysed.toLocaleString()} helper="Ready for reviewer inspection" icon={<ChatBubbleOutlineRoundedIcon />} tone="#16815D" />
        <StatCard label="In progress / queued" value={(analysing + waiting).toLocaleString()} helper="On the current page" icon={<CircularProgress size={20} />} tone="#B75B08" />
        <StatCard label="Messages on page" value={messages.toLocaleString()} helper="Across the current page" icon={<ChatBubbleOutlineRoundedIcon />} tone="#356BB3" />
      </Box>

      <Paper sx={{ p: 2, display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(260px, 1fr) 230px" }, gap: 1.5 }}>
        <TextField
          size="small"
          label="Search this page"
          placeholder="Title, conversation ID, or recommendation"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment> }}
        />
        <TextField fullWidth select size="small" label="Outcome on this page" value={outcome} onChange={(event) => setOutcome(event.target.value)}>
          <MenuItem value="">All outcomes</MenuItem>
          <MenuItem value="analysing">Analysing</MenuItem>
          <MenuItem value="pending">Queued</MenuItem>
          <MenuItem value="resolved">Resolved</MenuItem>
          <MenuItem value="failed_to_resolve">Failed to resolve</MenuItem>
          <MenuItem value="positive_feedback">Positive feedback</MenuItem>
          <MenuItem value="negative_feedback">Negative feedback</MenuItem>
          <MenuItem value="out_of_scope">Out of scope</MenuItem>
        </TextField>
      </Paper>

      <TableContainer component={Paper} sx={{ overflowX: "auto" }}>
        <Box sx={{ px: 2.5, py: 2, display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid", borderColor: "divider" }}>
          <Typography variant="h3">Conversations</Typography>
          <Typography variant="body2" color="text.secondary">{visibleItems.length} of {items.length} on this page</Typography>
        </Box>
        <Table aria-label="Conversations" sx={{ minWidth: 980 }}>
          <TableHead>
            <TableRow>
              <TableCell>Conversation</TableCell>
              <TableCell>Outcome</TableCell>
              <TableCell>Recommended next step</TableCell>
              <TableCell>Confidence</TableCell>
              <TableCell align="right">Messages</TableCell>
              <TableCell align="right">Open</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {visibleItems.length ? visibleItems.map((conversation) => (
              <TableRow key={conversation.conversation_id} hover>
                <TableCell sx={{ width: 280 }}>
                  {conversation.analysed ? (
                    <MuiLink component={Link} href={`/conversations/${conversation.conversation_id}`} underline="hover" sx={{ display: "block", fontWeight: 750, color: "text.primary" }}>
                      {conversation.title || `Conversation ${conversation.conversation_id.slice(0, 8)}`}
                    </MuiLink>
                  ) : (
                    <Typography variant="body2" sx={{ fontWeight: 750 }}>{conversation.title || `Conversation ${conversation.conversation_id.slice(0, 8)}`}</Typography>
                  )}
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", overflowWrap: "anywhere" }}>{conversation.conversation_id}</Typography>
                  <Typography variant="caption" color="text.secondary">{formatDate(conversation.last_message_at)}</Typography>
                </TableCell>
                <TableCell><StatusCell c={conversation} /></TableCell>
                <TableCell sx={{ minWidth: 300, maxWidth: 440 }}>
                  <Box sx={{ color: conversation.recommended_next_step ? "text.primary" : "text.secondary", maxHeight: 52, overflow: "hidden" }}>
                    <MarkdownContent>{conversation.recommended_next_step ?? "Analysis has not completed yet."}</MarkdownContent>
                  </Box>
                </TableCell>
                <TableCell>{conversation.confidence ? <Chip size="small" label={`${conversation.confidence[0].toUpperCase()}${conversation.confidence.slice(1)}`} variant="outlined" /> : <Typography variant="body2" color="text.secondary">—</Typography>}</TableCell>
                <TableCell align="right">{conversation.message_count ?? "—"}</TableCell>
                <TableCell align="right">
                  {conversation.analysed ? (
                    <Button component={Link} href={`/conversations/${conversation.conversation_id}`} size="small" endIcon={<ArrowForwardRoundedIcon />}>Review</Button>
                  ) : conversation.status === "analysing" ? (
                    <Typography variant="caption" color="text.secondary">Analysing…</Typography>
                  ) : (
                    <AnalyzeButton id={conversation.conversation_id} onDone={load} />
                  )}
                </TableCell>
              </TableRow>
            )) : (
              <TableRow><TableCell colSpan={6}><Box sx={{ py: 7, textAlign: "center" }}><SearchRoundedIcon sx={{ fontSize: 36, color: "text.disabled" }} /><Typography variant="h3" sx={{ mt: 1 }}>No conversations match</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>Try another title, ID, recommendation, outcome, or status.</Typography><Button sx={{ mt: 2 }} onClick={() => { setSearch(""); setOutcome(""); }}>Clear filters</Button></Box></TableCell></TableRow>
            )}
          </TableBody>
        </Table>
        <TablePagination
          component="div"
          count={total}
          page={page}
          rowsPerPage={rowsPerPage}
          rowsPerPageOptions={[10, 25, 50, 100]}
          onPageChange={(_, nextPage) => { setPage(nextPage); setSearch(""); setOutcome(""); }}
          onRowsPerPageChange={(event) => { setRowsPerPage(Number(event.target.value)); setPage(0); setSearch(""); setOutcome(""); }}
          labelRowsPerPage="Conversations per page"
        />
      </TableContainer>
    </Stack>
  );
}
