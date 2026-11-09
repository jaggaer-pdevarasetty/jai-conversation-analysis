"use client";

import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  List,
  ListItem,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { fetchPending, triggerSweep, type PendingResponse } from "../services/analysisApi";
import { useEnv } from "./EnvContext";
import { useRegion } from "./RegionContext";

type Phase = "fetching" | "ready" | "starting" | "started" | "error";

const EMPTY: PendingResponse = { count: 0, ids: [], by_region: {}, items: [] };

function ago(iso: string | null): string {
  if (!iso) return "";
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 90) return "just now";
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return `${Math.round(secs / 86400)}d ago`;
}

/** Preview of a pending set: per-region chip breakdown + a brief (sampled) list. */
function PendingPreview({ data, showRegions }: { data: PendingResponse; showRegions: boolean }) {
  return (
    <Stack spacing={1}>
      {showRegions && Object.keys(data.by_region).length > 0 && (
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {Object.entries(data.by_region).map(([lbl, n]) => (
            <Chip key={lbl} size="small" variant="outlined" label={`${lbl.toUpperCase()}: ${n}`} />
          ))}
        </Stack>
      )}
      {data.items.length > 0 && (
        <Box sx={{ maxHeight: 180, overflow: "auto", bgcolor: "action.hover", borderRadius: 1.5 }}>
          <List dense disablePadding>
            {data.items.map((it) => {
              const neg = it.negative_count ?? 0;
              const pos = it.positive_count ?? 0;
              const fbBadge =
                neg > 0 || pos > 0
                  ? [neg > 0 ? `${neg} 👎` : null, pos > 0 ? `${pos} 👍` : null].filter(Boolean).join(" · ")
                  : null;
              return (
                <ListItem key={it.conversation_id} divider>
                  <ListItemText
                    primaryTypographyProps={{ noWrap: true, fontWeight: 600 }}
                    secondaryTypographyProps={{ noWrap: true }}
                    primary={it.title || it.tenant_name || it.conversation_id.slice(0, 8)}
                    secondary={[it.region?.toUpperCase(), it.tenant_name, fbBadge, ago(it.last_message_at)].filter(Boolean).join(" · ")}
                  />
                </ListItem>
              );
            })}
          </List>
        </Box>
      )}
      {data.items.length < data.count && (
        <Typography variant="caption" color="text.secondary">
          Showing newest {data.items.length} of {data.count} conversations.
        </Typography>
      )}
    </Stack>
  );
}

function NegativeFeedbackSummary({ data }: { data: PendingResponse }) {
  const count = data.negative_feedback_messages ?? 0;
  const positiveMessages = data.positive_feedback_messages ?? 0;
  const totalMessages = data.feedback_messages ?? count + positiveMessages;
  const positiveConversations = data.positive_feedback_conversations ?? 0;
  const negativeConversations = data.negative_feedback_conversations ?? 0;
  const items = data.negative_items ?? [];
  return (
    <Box sx={{ p: 1.5, mb: 2, border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
      <Typography variant="subtitle2">Negative feedback messages</Typography>
      <Typography variant="body2" sx={{ mt: 0.5 }}>
        <b>{count}</b> negative rated message{count === 1 ? "" : "s"} waiting for analysis
        {totalMessages > 0
          ? ` (${positiveMessages} positive message${positiveMessages === 1 ? "" : "s"} across ${data.count} feedback conversation${data.count === 1 ? "" : "s"}).`
          : "."}
      </Typography>
      <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
        <Chip size="small" color="secondary" variant="outlined" label={`Feedback convos ${data.count}`} />
        <Chip size="small" color="error" variant="outlined" label={`Negative convos ${negativeConversations}`} />
        <Chip size="small" color="success" variant="outlined" label={`Positive-only convos ${positiveConversations}`} />
        <Chip size="small" color="error" variant="outlined" label={`Negative messages ${count}`} />
        <Chip size="small" color="success" variant="outlined" label={`Positive messages ${positiveMessages}`} />
        {Object.entries(data.negative_by_region ?? {}).map(([name, total]) => (
          <Chip key={`region-${name}`} size="small" label={`${name.toUpperCase()}: ${total}`} variant="outlined" />
        ))}
        {Object.entries(data.negative_by_mode ?? {}).map(([name, total]) => (
          <Chip key={`mode-${name}`} size="small" label={`${name}: ${total}`} variant="outlined" />
        ))}
        {data.average_frustration !== null && data.average_frustration !== undefined && (
          <Chip size="small" color="warning" variant="outlined" label={`Avg frustration ${data.average_frustration.toFixed(2)}`} />
        )}
      </Stack>
      {items.length > 0 && (
        <Box sx={{ maxHeight: 240, overflow: "auto", bgcolor: "action.hover", borderRadius: 1.5, mt: 1 }}>
          <List dense disablePadding>
            {items.map((item, idx) => (
              <ListItem key={item.feedback_id} divider>
                <ListItemText
                  primaryTypographyProps={{ noWrap: true, fontWeight: 600 }}
                  secondaryTypographyProps={{ noWrap: true }}
                  primary={[
                    `Msg #${idx + 1}`,
                    item.turn_number ? `Turn ${item.turn_number}` : null,
                    item.feedback_message_id ? `id ${item.feedback_message_id.slice(0, 8)}` : null,
                    item.title || item.tenant_name || item.conversation_id.slice(0, 8),
                  ].filter(Boolean).join(" · ")}
                  secondary={[
                    item.region?.toUpperCase(),
                    item.tenant_name,
                    item.platform,
                    item.interaction_mode,
                    item.frustration_score === null ? "frustration unavailable" : `frustration ${item.frustration_score.toFixed(2)}`,
                    item.user_query ? `Q: "${item.user_query}"` : null,
                    item.comment,
                  ].filter(Boolean).join(" · ")}
                />
              </ListItem>
            ))}
          </List>
        </Box>
      )}
      {data.details_complete === false && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
          Mode and frustration lookups are limited to the newest 20 pending conversations; remaining messages are counted as Unknown.
        </Typography>
      )}
    </Box>
  );
}

/** Manual analysis, scoped to the selected region + environment.
 *  UIT: one list of new / unanalysed conversations + a single "Start analysis" button.
 *  PROD: two lists — feedback conversations (analyse feedback only) and all conversations
 *  (analyse everything, with a warning that this includes the feedback ones). */
export function AnalyzeNowButton({
  variant = "contained",
  size = "small",
  label = "Analyze",
}: {
  variant?: "contained" | "outlined" | "text";
  size?: "small" | "medium";
  label?: string;
}) {
  const { region } = useRegion(); // "" = all regions
  const { env } = useEnv();
  const isProd = env === "prod";
  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<Phase>("fetching");
  const [feedback, setFeedback] = useState<PendingResponse>(EMPTY); // PROD only
  const [all, setAll] = useState<PendingResponse>(EMPTY);
  const [started, setStarted] = useState<{ scope: string; count: number } | null>(null);
  const [error, setError] = useState("");

  const busy = phase === "fetching" || phase === "starting";
  const scopeLabel = region ? region.toUpperCase() : "all regions";

  const openAndFetch = async () => {
    setOpen(true);
    setPhase("fetching");
    setError("");
    setStarted(null);
    try {
      // Fetch both sets so we can always show the Total / New feedback / Normal breakdown.
      const [fb, everything] = await Promise.all([
        fetchPending(region, "feedback"),
        fetchPending(region, "all"),
      ]);
      setFeedback(fb);
      setAll(everything);
      setPhase("ready");
    } catch {
      setError("Couldn't fetch conversations. Is the API running?");
      setPhase("error");
    }
  };

  const start = async (scope: "all" | "feedback", count: number) => {
    setPhase("starting");
    setStarted({ scope, count });
    try {
      await triggerSweep(region, scope);
      setPhase("started");
    } catch {
      setError("Couldn't start analysis. Please try again.");
      setPhase("error");
    }
  };

  const close = () => {
    if (!busy) setOpen(false);
  };

  return (
    <>
      <Button variant={variant} size={size} startIcon={<PlayArrowRoundedIcon />} onClick={openAndFetch}>
        {label}
      </Button>

      <Dialog open={open} onClose={close} maxWidth="sm" fullWidth aria-label="Analyze conversations">
        <DialogTitle>Analyze conversations · {scopeLabel}{isProd ? " · PROD" : ""}</DialogTitle>
        <DialogContent>
          {phase === "fetching" && (
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ py: 1 }}>
              <CircularProgress size={22} />
              <Typography>Fetching conversations waiting for analysis in {scopeLabel}…</Typography>
            </Stack>
          )}

          {phase === "ready" && (feedback.deep_research_negative ?? 0) > 0 && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              <AlertTitle>Deep Research negative feedback</AlertTitle>
              {feedback.deep_research_negative} negative feedback message{feedback.deep_research_negative === 1 ? "" : "s"} came from Deep Research. Review these first.
            </Alert>
          )}
          {phase === "ready" && isProd && all.analysis_window_days && (
            <Alert severity="info" sx={{ mb: 2 }}>
              <AlertTitle>PROD analysis window</AlertTitle>
              Bulk analysis includes only conversations active in the last {all.analysis_window_days} days. Older history is excluded.
            </Alert>
          )}
          {phase === "ready" && <NegativeFeedbackSummary data={feedback} />}

          {phase === "ready" && !isProd && (
            all.count > 0 ? (
              <Stack spacing={1.5}>
                <Typography>
                  <b>{all.count}</b> conversation{all.count === 1 ? " is" : "s are"} waiting for analysis in {scopeLabel}
                  {" "}(not yet analysed, of any age).
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Recent chats appear after 5 minutes without a new message.
                </Typography>
                {/* Feedback pending is by construction a subset of all pending (feedback_only just
                    narrows the same eligible set), so Without-feedback = all - feedback >= 0;
                    max(0,…) is a defensive guard. The extra feedback fetch runs in parallel
                    (Promise.all) with the all fetch, so it adds no latency — it's what powers
                    this breakdown. */}
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  <Chip size="small" color="primary" label={`Total conversations ${all.count}`} />
                  <Chip size="small" color="secondary" variant="outlined" label={`Feedback conversations ${feedback.count}`} />
                  <Chip size="small" color="error" variant="outlined" label={`Negative messages ${feedback.negative_feedback_messages ?? 0}`} />
                  <Chip size="small" color="success" variant="outlined" label={`Positive messages ${feedback.positive_feedback_messages ?? 0}`} />
                  <Chip size="small" variant="outlined" label={`Without feedback ${Math.max(0, all.count - feedback.count)}`} />
                </Stack>
                {((all.in_progress ?? 0) > 0 || (all.failed ?? 0) > 0) && (
                  <Typography variant="caption" color="text.secondary">
                    {(all.in_progress ?? 0) > 0 && `${all.in_progress} already queued/analysing (excluded from the count above). `}
                    {(all.failed ?? 0) > 0 && `${all.failed} previously failed — will be retried when you start.`}
                  </Typography>
                )}
                <PendingPreview data={all} showRegions={!region} />
              </Stack>
            ) : (all.in_progress ?? 0) > 0 ? (
              <Typography>All conversations in {scopeLabel} are already queued or being analysed ({all.in_progress}). Watch the live analysis queue for progress — no new sweep needed.</Typography>
            ) : (
              <Typography>Everything currently eligible is already analysed in {scopeLabel}. Recent chats appear after 5 minutes without a new message.</Typography>
            )
          )}

          {phase === "ready" && isProd && (
            <Stack spacing={2} divider={<Divider flexItem />}>
              <Stack spacing={1}>
                <Typography variant="subtitle2">Feedback conversations (positive + negative)</Typography>
                {feedback.count > 0 ? (
                  <>
                    <Typography variant="body2">
                      <b>{feedback.count}</b> conversation{feedback.count === 1 ? "" : "s"} with user feedback are not analyzed yet
                      {" "}({feedback.negative_feedback_conversations ?? 0} with negative feedback, {feedback.positive_feedback_conversations ?? 0} positive-only).
                    </Typography>
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                      <Chip size="small" color="primary" label={`Total conversations ${all.count}`} />
                      <Chip size="small" color="secondary" variant="outlined" label={`Feedback conversations ${feedback.count}`} />
                      <Chip size="small" color="error" variant="outlined" label={`Negative messages ${feedback.negative_feedback_messages ?? 0}`} />
                      <Chip size="small" color="success" variant="outlined" label={`Positive messages ${feedback.positive_feedback_messages ?? 0}`} />
                      <Chip size="small" variant="outlined" label={`Without feedback ${Math.max(0, all.count - feedback.count)}`} />
                    </Stack>
                    <PendingPreview data={feedback} showRegions={!region} />
                    <Box>
                      <Button variant="contained" size="small" startIcon={<PlayArrowRoundedIcon />} onClick={() => start("feedback", feedback.count)}>
                        Analyze feedback
                      </Button>
                    </Box>
                  </>
                ) : (
                  <Typography variant="body2" color="text.secondary">All feedback conversations in {scopeLabel} are already analyzed.</Typography>
                )}
              </Stack>

              <Stack spacing={1}>
                <Typography variant="subtitle2">
                  All conversations{all.analysis_window_days ? ` (last ${all.analysis_window_days} days)` : ""}
                </Typography>
                {all.count > 0 ? (
                  <>
                    <Typography variant="body2">
                      <b>{all.count}</b> conversation{all.count === 1 ? "" : "s"}
                      {all.analysis_window_days ? ` in the last ${all.analysis_window_days} days` : ""} are not analyzed yet (feedback + normal).
                    </Typography>
                    <Alert severity="warning" sx={{ py: 0 }}>
                      This analyzes <b>every</b> conversation in {scopeLabel}
                      {all.analysis_window_days ? ` from the last ${all.analysis_window_days} days` : ""}, including the feedback ones above.
                    </Alert>
                    <PendingPreview data={all} showRegions={!region} />
                    <Box>
                      <Button variant="outlined" color="warning" size="small" startIcon={<PlayArrowRoundedIcon />} onClick={() => start("all", all.count)}>
                        Analyze all ({all.count})
                      </Button>
                    </Box>
                  </>
                ) : (
                  <Typography variant="body2" color="text.secondary">Everything in {scopeLabel} is already analyzed.</Typography>
                )}
              </Stack>
            </Stack>
          )}

          {phase === "starting" && (
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ py: 1 }}>
              <CircularProgress size={22} />
              <Typography>
                Starting analysis of {started?.count} {started?.scope === "feedback" ? "feedback " : ""}conversation
                {started?.count === 1 ? "" : "s"} in {scopeLabel}…
              </Typography>
            </Stack>
          )}
          {phase === "started" && (
            <Alert severity="success">Analysis started — watch the live analysis queue for progress.</Alert>
          )}
          {phase === "error" && <Alert severity="error">{error}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={close} disabled={busy}>
            {phase === "started" ? "Close" : "Cancel"}
          </Button>
          {phase === "ready" && !isProd && all.count > 0 && (
            <Button variant="contained" startIcon={<PlayArrowRoundedIcon />} onClick={() => start("all", all.count)}>
              Start analysis
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </>
  );
}
