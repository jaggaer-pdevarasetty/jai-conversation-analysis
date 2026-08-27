"use client";

import AccessTimeRoundedIcon from "@mui/icons-material/AccessTimeRounded";
import AccountCircleOutlinedIcon from "@mui/icons-material/AccountCircleOutlined";
import BoltRoundedIcon from "@mui/icons-material/BoltRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import ForumOutlinedIcon from "@mui/icons-material/ForumOutlined";
import PsychologyOutlinedIcon from "@mui/icons-material/PsychologyOutlined";
import SmartToyOutlinedIcon from "@mui/icons-material/SmartToyOutlined";
import ThumbDownAltOutlinedIcon from "@mui/icons-material/ThumbDownAltOutlined";
import ThumbUpAltOutlinedIcon from "@mui/icons-material/ThumbUpAltOutlined";
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Chip,
  Divider,
  MenuItem,
  Paper,
  Skeleton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import {
  CATEGORIES,
  type ConversationDetail as Detail,
  fetchConversation,
  overrideCategory,
} from "../services/analysisApi";
import { CATEGORY_META, CategoryChip, categoryLabel } from "./CategoryChip";
import { EABadge } from "./EABadge";
import { EnrichmentPanel } from "./EnrichmentPanel";
import { MarkdownContent } from "./MarkdownContent";

/** AC-7: missing telemetry shows "unavailable", never 0. */
function metric(value: number | null): string {
  return value === null || value === undefined ? "unavailable" : value.toLocaleString();
}

/** input + output across the whole conversation. AC-7: if EITHER half is missing the total is
 * unknowable, so show "unavailable" (never substitute 0, which would understate it). */
function totalTokens(input: number | null, output: number | null): string {
  if (input === null || input === undefined || output === null || output === undefined) return "unavailable";
  return (input + output).toLocaleString();
}

function latency(value: number | null): string {
  if (value === null || value === undefined) return "unavailable";
  return value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(1)} s`;
}

function feedbackLabel(rating: boolean | null): string {
  if (rating === true) return "Positive feedback";
  if (rating === false) return "Negative feedback";
  return "No explicit rating";
}

function formatDate(value?: string): string {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function roleLabel(role: string): string {
  if (role === "assistant") return "JAI Assistant";
  if (role === "live_agent") return "Live agent";
  if (role === "system") return "System";
  return "User";
}

function MetricCard({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <Box aria-label={label} sx={{ p: 1.6, border: "1px solid", borderColor: "divider", borderRadius: 2.5, bgcolor: "#FAFBFC" }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, color: "text.secondary" }}>
        {icon}
        <Typography variant="caption" sx={{ fontWeight: 700 }}>{label}</Typography>
      </Box>
      <Typography variant="h3" sx={{ mt: 0.7, fontVariantNumeric: "tabular-nums" }}>{value}</Typography>
    </Box>
  );
}

export function ConversationDetail({ id, initial }: { id: string; initial?: Detail }) {
  const [detail, setDetail] = useState<Detail | null>(initial ?? null);
  const [error, setError] = useState<string | null>(null);
  const [override, setOverride] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    if (initial) return;
    let active = true;
    setDetail(null);
    setError(null);
    fetchConversation(id)
      .then((result) => { if (active) setDetail(result); })
      .catch(() => { if (active) setError("The conversation could not be loaded. Check the API connection and try again."); });
    return () => { active = false; };
  }, [id, initial, reload]);

  async function saveOverride() {
    if (!override) return;
    setSaving(true);
    setSaved(false);
    try {
      await overrideCategory(id, override, "reviewer");
      setDetail(await fetchConversation(id));
      setOverride("");
      setSaved(true);
    } catch {
      setError("The category override could not be saved. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  if (error && !detail) {
    return <Alert severity="error" action={<Button color="inherit" onClick={() => setReload((value) => value + 1)}>Try again</Button>}><AlertTitle>Conversation unavailable</AlertTitle>{error}</Alert>;
  }

  if (!detail) {
    return (
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 1.5fr) minmax(340px, .75fr)" }, gap: 2.5 }} role="status" aria-label="Loading conversation">
        <Skeleton variant="rounded" height={620} />
        <Skeleton variant="rounded" height={500} />
      </Box>
    );
  }

  const a = detail.analysis;
  const m = detail.metrics;
  const signals = a.signals;
  const activeSignals = signals ? [
    signals.repeated_prompts && "Repeated prompts",
    signals.abandoned && "Abandoned",
    signals.error && "Error detected",
    signals.out_of_scope_intent && "Out-of-scope intent",
    signals.frustrated && "Frustration detected",
    signals.feedback && `${signals.feedback[0].toUpperCase()}${signals.feedback.slice(1)} feedback signal`,
  ].filter(Boolean) as string[] : [];
  const feedbackIcon = detail.feedback.rating === true
    ? <ThumbUpAltOutlinedIcon color="success" />
    : detail.feedback.rating === false
      ? <ThumbDownAltOutlinedIcon color="error" />
      : <ForumOutlinedIcon sx={{ color: "text.secondary" }} />;

  return (
    <Stack spacing={2.5}>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {saved && <Alert severity="success" onClose={() => setSaved(false)}>Category override saved and added to the audit record.</Alert>}

      <Paper sx={{ p: { xs: 2.25, md: 3 } }}>
        <Box sx={{ display: "flex", flexDirection: { xs: "column", md: "row" }, alignItems: { xs: "flex-start", md: "center" }, justifyContent: "space-between", gap: 2 }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="overline" color="primary.main">Conversation review</Typography>
            <Typography variant="h2" component="h1" sx={{ overflowWrap: "anywhere" }}>{detail.conversation_id}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.7 }}>Analysed {formatDate(a.analyzed_at)}</Typography>
          </Box>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <CategoryChip category={a.category} />
            <Chip size="small" label={`${a.confidence[0]?.toUpperCase()}${a.confidence.slice(1)} confidence`} variant="outlined" color={a.confidence === "high" ? "success" : a.confidence === "low" ? "warning" : "default"} />
            <Chip size="small" label={a.status === "analysed" ? "Analysis complete" : a.status} icon={<CheckCircleRoundedIcon />} sx={{ bgcolor: "#F2F4F7" }} />
          </Stack>
        </Box>
      </Paper>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 1.55fr) minmax(340px, .72fr)" }, gap: 2.5, alignItems: "start" }}>
        <Paper aria-label="Transcript" sx={{ overflow: "hidden" }}>
          <Box sx={{ px: { xs: 2.25, md: 3 }, py: 2.5, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Box>
              <Typography variant="h3">Conversation transcript</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.35 }}>{detail.messages.length} {detail.messages.length === 1 ? "message" : "messages"} · ordered from first to last</Typography>
            </Box>
            <Chip size="small" label="De-identified" variant="outlined" />
          </Box>
          <Divider />
          <Stack spacing={0} sx={{ p: { xs: 2.25, md: 3 } }}>
            {detail.messages.length ? detail.messages.map((message, index) => {
              const assistant = message.role === "assistant";
              return (
                <Box key={message.id} sx={{ display: "flex", gap: 1.5, pb: index === detail.messages.length - 1 ? 0 : 3 }}>
                  <Box sx={{ display: "grid", placeItems: "center", width: 36, height: 36, borderRadius: 2, flex: "0 0 auto", bgcolor: assistant ? "#FFF0E9" : "#EEF2F7", color: assistant ? "primary.main" : "secondary.main" }}>
                    {assistant ? <SmartToyOutlinedIcon sx={{ fontSize: 20 }} /> : <AccountCircleOutlinedIcon sx={{ fontSize: 20 }} />}
                  </Box>
                  <Box sx={{ minWidth: 0, flex: 1 }}>
                    <Box sx={{ display: "flex", alignItems: "baseline", gap: 1, flexWrap: "wrap" }}>
                      <Typography variant="body2" sx={{ fontWeight: 750 }}>{roleLabel(message.role)}</Typography>
                      {message.created_at && <Typography variant="caption" color="text.secondary">{formatDate(message.created_at)}</Typography>}
                      {message.model && <Typography variant="caption" color="text.secondary">· {message.model}</Typography>}
                    </Box>
                    <Box sx={{ mt: 0.75, px: 2, py: 1.5, borderRadius: 2.5, bgcolor: assistant ? "#FFFFFF" : "#F7F8FA", border: "1px solid", borderColor: "divider" }}>
                      <MarkdownContent>{message.content || "No message content"}</MarkdownContent>
                    </Box>
                  </Box>
                </Box>
              );
            }) : (
              <Box sx={{ py: 8, textAlign: "center" }}><Typography variant="h3">No transcript available</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>The conversation analysis exists, but no de-identified messages were stored.</Typography></Box>
            )}
          </Stack>
        </Paper>

        <Stack spacing={2.5} sx={{ position: { lg: "sticky" }, top: { lg: 96 } }}>
          <Paper aria-label="Recommended action" sx={{ p: 2.5 }}>
            <Typography variant="h3">Recommended action</Typography>
            <Box sx={{ mt: 1.25, p: 1.6, bgcolor: "#FFF6F1", borderRadius: 2.5, borderLeft: "4px solid", borderColor: "primary.main", fontWeight: 700 }}><MarkdownContent>{a.recommended_next_step}</MarkdownContent></Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.5 }}>Model rationale</Typography>
            <Box sx={{ mt: 0.35, fontSize: 14 }}><MarkdownContent>{a.rationale || "No model rationale was provided."}</MarkdownContent></Box>
          </Paper>

          <Paper aria-label="Analysis" sx={{ p: 2.5 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <PsychologyOutlinedIcon color="primary" />
              <Typography variant="h3">Detected signals</Typography>
            </Box>
            <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mt: 2 }}>
              {activeSignals.length ? activeSignals.map((signal) => <Chip key={signal} size="small" label={signal} variant="outlined" />) : <Typography variant="body2" color="text.secondary">No deterministic risk signals detected.</Typography>}
            </Stack>
          </Paper>

          {detail.source && (
            <Paper aria-label="Conversation context" sx={{ p: 2.5 }}>
              <Typography variant="h3">Conversation context</Typography>
              {detail.source.ea && <Box sx={{ mt: 1.25 }}><EABadge ea={detail.source.ea} /></Box>}
              <Stack spacing={1.15} sx={{ mt: 2 }}>
                <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">Tenant</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right" }}>{detail.source.tenant_name || "Unavailable"}</Typography></Box>
                <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">User</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right", overflowWrap: "anywhere" }}>{detail.source.user_name || "Unavailable"}</Typography></Box>
                <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">Created</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right" }}>{formatDate(detail.source.created_at ?? undefined)}</Typography></Box>
                <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">Last message</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right" }}>{formatDate(detail.source.last_message_at ?? undefined)}</Typography></Box>
                <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">Analysed</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right" }}>{formatDate(a.analyzed_at)}</Typography></Box>
                <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">Analyzer</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right", overflowWrap: "anywhere" }}>{a.analyzer_version || "Not available"}</Typography></Box>
              </Stack>
            </Paper>
          )}

          <Paper aria-label="Metrics" sx={{ p: 2.5 }}>
            <Typography variant="h3">Cost & responsiveness</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.4 }}>Conversation-level generation telemetry</Typography>
            <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1.25, mt: 2 }}>
              <MetricCard label="Time to first token" value={latency(m.ttft_ms)} icon={<AccessTimeRoundedIcon sx={{ fontSize: 16 }} />} />
              <MetricCard label="Input tokens" value={metric(m.input_tokens)} icon={<BoltRoundedIcon sx={{ fontSize: 16 }} />} />
              <MetricCard label="Output tokens" value={metric(m.output_tokens)} icon={<BoltRoundedIcon sx={{ fontSize: 16 }} />} />
              <MetricCard label="Total tokens" value={totalTokens(m.input_tokens, m.output_tokens)} icon={<BoltRoundedIcon sx={{ fontSize: 16 }} />} />
            </Box>
          </Paper>

          <Paper aria-label="Feedback" sx={{ p: 2.5 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              {feedbackIcon}
              <Typography variant="h3">User feedback</Typography>
            </Box>
            <Typography variant="body2" sx={{ fontWeight: 750, mt: 1.6 }}>{feedbackLabel(detail.feedback.rating)}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{detail.feedback.comment || "No written feedback was provided."}</Typography>
          </Paper>

          <EnrichmentPanel enrichment={detail.enrichment} />

          <Paper aria-label="Override" sx={{ p: 2.5 }}>
            <Typography variant="h3">Decision & audit</Typography>
            <Stack spacing={1.2} sx={{ mt: 2 }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">Model category</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right" }}>{categoryLabel(a.model_category)}</Typography></Box>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">Effective category</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right" }}>{categoryLabel(a.category)}</Typography></Box>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">Analyzer</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right", overflowWrap: "anywhere" }}>{a.analyzer_version || "Not available"}</Typography></Box>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">Run ID</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right", overflowWrap: "anywhere" }}>{a.run_id || "Not available"}</Typography></Box>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">Analysed</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right" }}>{formatDate(a.analyzed_at)}</Typography></Box>
              {a.override && <Alert severity="warning" sx={{ mt: 0.5 }}>Overridden by {a.override.actor} on {formatDate(a.override.at)}</Alert>}
            </Stack>
            <Divider sx={{ my: 2.25 }} />
            <Typography variant="body2" sx={{ fontWeight: 750 }}>Override category</Typography>
            <Typography variant="caption" color="text.secondary">The model decision is retained in the audit record.</Typography>
            <Stack spacing={1.25} sx={{ mt: 1.5 }}>
              <TextField select fullWidth size="small" label="New category" value={override} onChange={(event) => setOverride(event.target.value)}>
                {CATEGORIES.map((category) => <MenuItem key={category} value={category}>{CATEGORY_META[category].label}</MenuItem>)}
              </TextField>
              <Button fullWidth variant="contained" disabled={!override || saving || override === a.category} onClick={saveOverride}>
                {saving ? "Saving override…" : "Save override"}
              </Button>
            </Stack>
          </Paper>
        </Stack>
      </Box>
    </Stack>
  );
}
