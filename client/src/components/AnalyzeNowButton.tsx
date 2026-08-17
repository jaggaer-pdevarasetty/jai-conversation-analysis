"use client";

import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import {
  Alert,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { fetchPending, triggerSweep } from "../services/analysisApi";

type Phase = "fetching" | "fetched" | "starting" | "started" | "error";

/** Two-step manual analysis:
 *  1. Click "Analyze" -> fetch all new / unanalysed conversations (loader).
 *  2. After fetching, a "Start analysis" button appears -> click to analyse (loader),
 *     then the live queue shows progress.
 * Used in the app bar and on the review queue. */
export function AnalyzeNowButton({
  variant = "contained",
  size = "small",
  label = "Analyze",
}: {
  variant?: "contained" | "outlined" | "text";
  size?: "small" | "medium";
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<Phase>("fetching");
  const [count, setCount] = useState(0);
  const [error, setError] = useState("");

  const busy = phase === "fetching" || phase === "starting";

  const openAndFetch = async () => {
    setOpen(true);
    setPhase("fetching");
    setError("");
    try {
      const { count } = await fetchPending();
      setCount(count);
      setPhase("fetched");
    } catch {
      setError("Couldn't fetch conversations. Is the API running?");
      setPhase("error");
    }
  };

  const startAnalysis = async () => {
    setPhase("starting");
    try {
      await triggerSweep();
      setPhase("started");
    } catch {
      setError("Couldn't start analysis. Please try again.");
      setPhase("error");
    }
  };

  const close = () => {
    if (!busy) setOpen(false);
  };

  const plural = count === 1 ? "" : "s";

  return (
    <>
      <Button variant={variant} size={size} startIcon={<PlayArrowRoundedIcon />} onClick={openAndFetch}>
        {label}
      </Button>

      <Dialog open={open} onClose={close} maxWidth="xs" fullWidth aria-label="Analyze conversations">
        <DialogTitle>Analyze conversations</DialogTitle>
        <DialogContent>
          {phase === "fetching" && (
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ py: 1 }}>
              <CircularProgress size={22} />
              <Typography>Fetching new / unanalyzed conversations…</Typography>
            </Stack>
          )}
          {phase === "fetched" && (
            <Typography>
              {count > 0
                ? `Found ${count} new / unanalyzed conversation${plural} ready to analyze.`
                : "Everything is already analyzed — no new conversations found."}
            </Typography>
          )}
          {phase === "starting" && (
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ py: 1 }}>
              <CircularProgress size={22} />
              <Typography>Starting analysis of {count} conversation{plural}…</Typography>
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
          {phase === "fetched" && count > 0 && (
            <Button variant="contained" startIcon={<PlayArrowRoundedIcon />} onClick={startAnalysis}>
              Start analysis
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </>
  );
}
