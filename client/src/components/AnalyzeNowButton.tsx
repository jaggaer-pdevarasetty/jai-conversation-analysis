"use client";

import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import { Alert, Button, CircularProgress, Snackbar } from "@mui/material";
import { useState } from "react";
import { triggerSweep } from "../services/analysisApi";

type Toast = { msg: string; sev: "success" | "info" | "error" };

/** Manual trigger button: checks the chat DB and analyses all not-yet-analysed conversations
 * (background sweep). Used in the app bar and on the review queue. */
export function AnalyzeNowButton({
  variant = "contained",
  size = "small",
  label = "Analyze now",
}: {
  variant?: "contained" | "outlined" | "text";
  size?: "small" | "medium";
  label?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);

  const onClick = async () => {
    setBusy(true);
    try {
      const status = await triggerSweep();
      setToast(
        status === "already_running"
          ? { msg: "Analysis is already running — watch the live queue.", sev: "info" }
          : { msg: "Analysis started — watch the live queue for progress.", sev: "success" },
      );
    } catch {
      setToast({ msg: "Couldn't start analysis. Is the API running?", sev: "error" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button
        variant={variant}
        size={size}
        onClick={onClick}
        disabled={busy}
        startIcon={busy ? <CircularProgress size={16} color="inherit" /> : <PlayArrowRoundedIcon />}
      >
        {busy ? "Starting…" : label}
      </Button>
      <Snackbar
        open={!!toast}
        autoHideDuration={5000}
        onClose={() => setToast(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        {toast ? (
          <Alert severity={toast.sev} variant="filled" onClose={() => setToast(null)}>
            {toast.msg}
          </Alert>
        ) : undefined}
      </Snackbar>
    </>
  );
}
