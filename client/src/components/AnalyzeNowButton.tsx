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

type Phase = "fetching" | "fetched" | "starting" | "started" | "error";

const EMPTY: PendingResponse = { count: 0, ids: [], by_region: {}, items: [] };

function ago(iso: string | null): string {
  if (!iso) return "";
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 90) return "just now";
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return `${Math.round(secs / 86400)}d ago`;
}

/** Two-step manual analysis, scoped to the selected region:
 *  1. Click "Analyze" -> fetch new / unanalysed conversations (loader) -> show count,
 *     per-region breakdown, and a brief list.
 *  2. "Start analysis" appears (only after fetching, only if there's work) -> analyse (loader). */
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
  const isProd = env === "prod"; // PROD analyses feedback conversations automatically
  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<Phase>("fetching");
  const [data, setData] = useState<PendingResponse>(EMPTY);
  const [error, setError] = useState("");

  const busy = phase === "fetching" || phase === "starting";
  const scope = region ? region.toUpperCase() : "all regions";
  const plural = data.count === 1 ? "" : "s";
  const noun = isProd ? "feedback conversation" : "new / unanalyzed conversation";

  const startAnalysisWith = async (r?: string) => {
    setPhase("starting");
    try {
      await triggerSweep(r);
      setPhase("started");
    } catch {
      setError("Couldn't start analysis. Please try again.");
      setPhase("error");
    }
  };

  const openAndFetch = async () => {
    setOpen(true);
    setPhase("fetching");
    setError("");
    try {
      const found = await fetchPending(region);
      setData(found);
      // PROD: feedback conversations are analysed automatically — no confirmation step.
      // Non-feedback PROD conversations are analysed via the per-conversation button instead.
      if (isProd && found.count > 0) {
        await startAnalysisWith(region);
      } else {
        setPhase("fetched");
      }
    } catch {
      setError("Couldn't fetch conversations. Is the API running?");
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
        <DialogTitle>Analyze conversations · {scope}</DialogTitle>
        <DialogContent>
          {phase === "fetching" && (
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ py: 1 }}>
              <CircularProgress size={22} />
              <Typography>
                {isProd ? `Finding feedback conversations to analyze in ${scope}…` : `Fetching new / unanalyzed conversations in ${scope}…`}
              </Typography>
            </Stack>
          )}

          {phase === "fetched" &&
            (data.count > 0 ? (
              <Stack spacing={1.5}>
                <Typography>
                  Found <b>{data.count}</b> {noun}{plural} in {scope}.
                </Typography>
                {!region && Object.keys(data.by_region).length > 0 && (
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    {Object.entries(data.by_region).map(([lbl, n]) => (
                      <Chip key={lbl} size="small" variant="outlined" label={`${lbl.toUpperCase()}: ${n}`} />
                    ))}
                  </Stack>
                )}
                {data.items.length > 0 && (
                  <Box sx={{ maxHeight: 260, overflow: "auto", bgcolor: "action.hover", borderRadius: 1.5 }}>
                    <List dense disablePadding>
                      {data.items.map((it) => (
                        <ListItem key={it.conversation_id} divider>
                          <ListItemText
                            primaryTypographyProps={{ noWrap: true, fontWeight: 600 }}
                            secondaryTypographyProps={{ noWrap: true }}
                            primary={it.title || it.tenant_name || it.conversation_id.slice(0, 8)}
                            secondary={[it.region?.toUpperCase(), it.tenant_name, ago(it.last_message_at)]
                              .filter(Boolean)
                              .join(" · ")}
                          />
                        </ListItem>
                      ))}
                    </List>
                  </Box>
                )}
              </Stack>
            ) : (
              <Typography>
                {isProd
                  ? `No feedback conversations to analyze in ${scope} — they're already analyzed. (Analyze others individually from the conversation list.)`
                  : `Everything is already analyzed in ${scope} — no new conversations found.`}
              </Typography>
            ))}

          {phase === "starting" && (
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ py: 1 }}>
              <CircularProgress size={22} />
              <Typography>
                Analyzing {data.count} {noun}{plural} in {scope}…
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
          {!isProd && phase === "fetched" && data.count > 0 && (
            <Button variant="contained" startIcon={<PlayArrowRoundedIcon />} onClick={() => startAnalysisWith(region)}>
              Start analysis
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </>
  );
}
