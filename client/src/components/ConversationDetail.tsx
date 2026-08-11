"use client";

import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  MenuItem,
  Paper,
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

/** AC-7: missing telemetry shows "unavailable", never 0. */
function metric(value: number | null): string {
  return value === null || value === undefined ? "unavailable" : String(value);
}

function feedbackLabel(rating: boolean | null): string {
  if (rating === true) return "thumbs up";
  if (rating === false) return "thumbs down";
  return "none";
}

export function ConversationDetail({ id, initial }: { id: string; initial?: Detail }) {
  const [detail, setDetail] = useState<Detail | null>(initial ?? null);
  const [error, setError] = useState<string | null>(null);
  const [override, setOverride] = useState<string>("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (initial) return;
    fetchConversation(id)
      .then(setDetail)
      .catch(() => setError("Could not load the conversation."));
  }, [id, initial]);

  async function saveOverride() {
    if (!override) return;
    setSaving(true);
    try {
      await overrideCategory(id, override, "reviewer");
      setDetail(await fetchConversation(id));
      setOverride("");
    } catch {
      setError("Override failed.");
    } finally {
      setSaving(false);
    }
  }

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!detail) return <Typography>Loading…</Typography>;

  const a = detail.analysis;
  const m = detail.metrics;

  return (
    <Stack spacing={2}>
      <Typography variant="h5" component="h1">
        Conversation {detail.conversation_id}
      </Typography>

      <Paper sx={{ p: 2 }} aria-label="Analysis">
        <Typography variant="h6">Analysis</Typography>
        <Stack direction="row" spacing={1} sx={{ my: 1 }}>
          <Chip label={a.category} color="primary" />
          <Chip label={`confidence: ${a.confidence}`} variant="outlined" />
          {a.override && <Chip label={`overridden from ${a.model_category}`} color="warning" />}
        </Stack>
        <Typography>
          <strong>Recommended next step:</strong> {a.recommended_next_step}
        </Typography>
        <Typography color="text.secondary">
          <strong>Why:</strong> {a.rationale || "—"}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {a.analyzer_version} · {a.analyzed_at}
        </Typography>
      </Paper>

      <Paper sx={{ p: 2 }} aria-label="Metrics">
        <Typography variant="h6">Cost & responsiveness</Typography>
        <Typography>Latency (ms): {metric(m.ttft_ms)}</Typography>
        <Typography>Input tokens: {metric(m.input_tokens)}</Typography>
        <Typography>Output tokens: {metric(m.output_tokens)}</Typography>
        <Typography>Prompt tokens: {metric(m.prompt_tokens)}</Typography>
      </Paper>

      <Paper sx={{ p: 2 }} aria-label="Feedback">
        <Typography variant="h6">Feedback</Typography>
        <Typography>Rating: {feedbackLabel(detail.feedback.rating)}</Typography>
        <Typography>Comment: {detail.feedback.comment ?? "—"}</Typography>
      </Paper>

      <Paper sx={{ p: 2 }} aria-label="Transcript">
        <Typography variant="h6">Transcript</Typography>
        <Stack spacing={1} sx={{ mt: 1 }}>
          {detail.messages.map((msg) => (
            <Box key={msg.id}>
              <Typography variant="caption" color="text.secondary">
                {msg.role}
              </Typography>
              <Typography sx={{ whiteSpace: "pre-wrap" }}>{msg.content}</Typography>
              <Divider sx={{ mt: 1 }} />
            </Box>
          ))}
        </Stack>
      </Paper>

      <Paper sx={{ p: 2 }} aria-label="Override">
        <Typography variant="h6">Override category</Typography>
        <Stack direction="row" spacing={1} sx={{ mt: 1 }} alignItems="center">
          <TextField
            select
            size="small"
            label="New category"
            value={override}
            onChange={(e) => setOverride(e.target.value)}
            sx={{ minWidth: 220 }}
          >
            {CATEGORIES.map((c) => (
              <MenuItem key={c} value={c}>
                {c}
              </MenuItem>
            ))}
          </TextField>
          <Button variant="contained" disabled={!override || saving} onClick={saveOverride}>
            Save override
          </Button>
        </Stack>
      </Paper>
    </Stack>
  );
}
