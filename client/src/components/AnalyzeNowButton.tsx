"use client";

import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import {
  Alert,
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
            {data.items.map((it) => (
              <ListItem key={it.conversation_id} divider>
                <ListItemText
                  primaryTypographyProps={{ noWrap: true, fontWeight: 600 }}
                  secondaryTypographyProps={{ noWrap: true }}
                  primary={it.title || it.tenant_name || it.conversation_id.slice(0, 8)}
                  secondary={[it.region?.toUpperCase(), it.tenant_name, ago(it.last_message_at)].filter(Boolean).join(" · ")}
                />
              </ListItem>
            ))}
          </List>
        </Box>
      )}
    </Stack>
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
              <Typography>Fetching new / unanalyzed conversations in {scopeLabel}…</Typography>
            </Stack>
          )}

          {phase === "ready" && !isProd && (
            all.count > 0 ? (
              <Stack spacing={1.5}>
                <Typography>
                  Found <b>{all.count}</b> new / unanalyzed conversation{all.count === 1 ? "" : "s"} in {scopeLabel}.
                </Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  <Chip size="small" color="primary" label={`Total ${all.count}`} />
                  <Chip size="small" color="secondary" variant="outlined" label={`New feedback ${feedback.count}`} />
                  <Chip size="small" variant="outlined" label={`Normal ${Math.max(0, all.count - feedback.count)}`} />
                </Stack>
                <PendingPreview data={all} showRegions={!region} />
              </Stack>
            ) : (
              <Typography>Everything is already analyzed in {scopeLabel} — no new conversations found.</Typography>
            )
          )}

          {phase === "ready" && isProd && (
            <Stack spacing={2} divider={<Divider flexItem />}>
              <Stack spacing={1}>
                <Typography variant="subtitle2">Feedback conversations</Typography>
                {feedback.count > 0 ? (
                  <>
                    <Typography variant="body2">
                      <b>{feedback.count}</b> conversation{feedback.count === 1 ? "" : "s"} with user feedback are not analyzed yet.
                    </Typography>
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
                <Typography variant="subtitle2">All conversations</Typography>
                {all.count > 0 ? (
                  <>
                    <Typography variant="body2">
                      <b>{all.count}</b> conversation{all.count === 1 ? "" : "s"} are not analyzed yet (feedback + normal).
                    </Typography>
                    <Alert severity="warning" sx={{ py: 0 }}>
                      This analyzes <b>every</b> conversation in {scopeLabel}, including the feedback ones above.
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
