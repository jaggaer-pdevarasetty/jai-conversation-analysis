"use client";

import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import InsightsOutlinedIcon from "@mui/icons-material/InsightsOutlined";
import OpenInNewRoundedIcon from "@mui/icons-material/OpenInNewRounded";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Chip,
  Divider,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import type { Enrichment } from "../services/analysisApi";

/** Shows the safe, PII-scrubbed LangSmith trace signals (ADR-0018/0021): what the live JAI
 * agent did + "what it was thinking" (its own reasoning) + which documents it used. For feedback
 * conversations it also shows the retrieved snippets and the actual (scrubbed) invocation prompt.
 * Renders an explicit reason when trace details were not captured or no trace was matched. */
export function EnrichmentPanel({ enrichment }: { enrichment?: Enrichment | null }) {
  const e = enrichment;
  const title = (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
      <InsightsOutlinedIcon color="primary" />
      <Typography variant="h3">What the assistant did (LangSmith)</Typography>
    </Box>
  );

  if (!e || !e.langsmith_found) {
    const noMatch = Boolean(e);
    return (
      <Paper aria-label="LangSmith trace" sx={{ p: 2.5 }}>
        {title}
        <Typography variant="body2" sx={{ mt: 1.5, fontWeight: 700 }}>
          {noMatch ? "No matching LangSmith trace was found." : "LangSmith trace details were not captured when this analysis ran."}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
          {noMatch
            ? "Why: the configured project and environment returned no root runs for this conversation. The trace may be outside retention or stored in another project or environment."
            : "Why: this record contains no enrichment status, so the exact lookup failure was not retained. The best-effort lookup may have been unavailable or returned no match."}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
          Retrieved documents, snippets, reasoning, and invocation prompt details cannot be shown without matched trace data.
        </Typography>
      </Paper>
    );
  }

  const chips: string[] = [
    e.intent && `intent: ${e.intent}`,
    e.agent_used && `agent: ${e.agent_used}`,
    e.platform && `platform: ${e.platform}`,
    e.interaction_mode && `mode: ${e.interaction_mode}`,
    e.response_type && `response: ${e.response_type}`,
    e.source_confidence && `agent confidence: ${e.source_confidence}`,
    e.retrieval_hit === true && `knowledge base: ${e.retrieved_count} doc(s) found`,
    e.retrieval_hit === false && "knowledge base: no docs found",
    e.had_error === true && "error",
    e.guardrail && `guardrail: ${e.guardrail}`,
    typeof e.frustration_score === "number" && `frustration: ${e.frustration_score.toFixed(2)}`,
    typeof e.turns === "number" && `turns: ${e.turns}`,
  ].filter(Boolean) as string[];

  return (
    <Paper aria-label="LangSmith trace" sx={{ p: 2.5 }}>
      {title}

      <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mt: 1.5 }}>
        {chips.length ? (
          chips.map((c) => <Chip key={c} size="small" label={c} variant="outlined" />)
        ) : (
          <Typography variant="body2" color="text.secondary">No trace signals.</Typography>
        )}
      </Stack>

      {(e.trace_url || e.trace_id) && (
        <>
          <Divider sx={{ my: 2 }} />
          <Typography variant="caption" color="text.secondary">LangSmith trace</Typography>
          <Stack direction="row" spacing={1} alignItems="center" useFlexGap flexWrap="wrap" sx={{ mt: 0.5 }}>
            <Typography variant="body2" sx={{ fontFamily: "monospace", overflowWrap: "anywhere" }}>{e.trace_id}</Typography>
            {e.trace_url && (
              <Button
                size="small"
                href={e.trace_url}
                target="_blank"
                rel="noopener noreferrer"
                endIcon={<OpenInNewRoundedIcon />}
              >
                Open trace
              </Button>
            )}
          </Stack>
        </>
      )}

      {e.reasoning_summary && (
        <>
          <Divider sx={{ my: 2 }} />
          <Typography variant="caption" color="text.secondary">What the assistant was thinking</Typography>
          <Typography variant="body2" sx={{ mt: 0.6, whiteSpace: "pre-wrap" }}>{e.reasoning_summary}</Typography>
        </>
      )}

      {e.retrieved_docs.length > 0 && (
        <>
          <Divider sx={{ my: 2 }} />
          <Typography variant="caption" color="text.secondary">Documents used ({e.retrieved_count})</Typography>
          <Stack spacing={0.5} sx={{ mt: 0.75 }}>
            {e.retrieved_docs.map((doc) => (
              <Typography key={doc} variant="body2" sx={{ overflowWrap: "anywhere" }}>• {doc}</Typography>
            ))}
          </Stack>
        </>
      )}

      {e.retrieved_snippets.length > 0 && (
        <Accordion disableGutters elevation={0} sx={{ mt: 1.5, border: "1px solid", borderColor: "divider", borderRadius: 2, "&:before": { display: "none" } }}>
          <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />} aria-label="Retrieved snippets">
            <Typography variant="body2" sx={{ fontWeight: 700 }}>Retrieved snippets ({e.retrieved_snippets.length})</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Stack spacing={1.25}>
              {e.retrieved_snippets.map((snippet, i) => (
                <Typography key={i} variant="caption" sx={{ display: "block", p: 1, bgcolor: "#F7F8FA", borderRadius: 1.5, whiteSpace: "pre-wrap" }}>{snippet}</Typography>
              ))}
            </Stack>
          </AccordionDetails>
        </Accordion>
      )}

      {e.invocation_prompt && (
        <Accordion disableGutters elevation={0} sx={{ mt: 1.5, border: "1px solid", borderColor: "divider", borderRadius: 2, "&:before": { display: "none" } }}>
          <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />} aria-label="Invocation prompt">
            <Typography variant="body2" sx={{ fontWeight: 700 }}>Actual prompt sent (scrubbed)</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography component="pre" variant="caption" sx={{ m: 0, p: 1.25, bgcolor: "#0B1020", color: "#D6E2FF", borderRadius: 1.5, whiteSpace: "pre-wrap", overflowWrap: "anywhere", fontFamily: "monospace" }}>{e.invocation_prompt}</Typography>
          </AccordionDetails>
        </Accordion>
      )}
    </Paper>
  );
}
