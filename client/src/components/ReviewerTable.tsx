"use client";

import {
  Alert,
  Link as MuiLink,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from "@mui/material";
import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchAnalysis, type ListItem, type ListResponse } from "../services/analysisApi";

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
  return value === null || value === undefined ? "unavailable" : String(value);
}

export function ReviewerTable({ initial }: { initial?: ListResponse }) {
  const [items, setItems] = useState<ListItem[]>(initial?.items ?? []);
  const [unanalysed, setUnanalysed] = useState<number>(initial?.unanalysed ?? 0);
  const [category, setCategory] = useState("");

  useEffect(() => {
    if (initial) return;
    let active = true;
    fetchAnalysis(category)
      .then((res) => {
        if (!active) return;
        setItems(res.items);
        setUnanalysed(res.unanalysed);
      })
      .catch(() => {
        if (active) setItems([]);
      });
    return () => {
      active = false;
    };
  }, [category, initial]);

  return (
    <div>
      {unanalysed > 0 && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {unanalysed} conversation(s) not yet analysed — queued for the next run.
        </Alert>
      )}

      <label htmlFor="category">Filter by category</label>{" "}
      <select id="category" value={category} onChange={(e) => setCategory(e.target.value)}>
        {CATEGORY_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>

      <TableContainer component={Paper} sx={{ mt: 2 }}>
        <Table aria-label="Analysed conversations">
          <TableHead>
            <TableRow>
              <TableCell>Conversation ID</TableCell>
              <TableCell>Category</TableCell>
              <TableCell>Recommended next step</TableCell>
              <TableCell>Confidence</TableCell>
              <TableCell>TTFT (ms)</TableCell>
              <TableCell>Tokens (in/out)</TableCell>
              <TableCell>Feedback</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((it) => (
              <TableRow key={it.conversation_id}>
                <TableCell>
                  <MuiLink component={Link} href={`/conversations/${it.conversation_id}`}>
                    {it.conversation_id}
                  </MuiLink>
                </TableCell>
                <TableCell>
                  {it.category}
                  {it.overridden ? " (overridden)" : ""}
                </TableCell>
                <TableCell>{it.recommended_next_step}</TableCell>
                <TableCell>{it.confidence}</TableCell>
                <TableCell>{metric(it.metrics.ttft_ms)}</TableCell>
                <TableCell>
                  {metric(it.metrics.input_tokens)} / {metric(it.metrics.output_tokens)}
                </TableCell>
                <TableCell>{it.has_feedback ? "yes" : "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </div>
  );
}
