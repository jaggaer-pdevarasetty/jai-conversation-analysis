"use client";

import AccessTimeRoundedIcon from "@mui/icons-material/AccessTimeRounded";
import AccountCircleOutlinedIcon from "@mui/icons-material/AccountCircleOutlined";
import ArrowBackRoundedIcon from "@mui/icons-material/ArrowBackRounded";
import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import BoltRoundedIcon from "@mui/icons-material/BoltRounded";
import ChatBubbleOutlineRoundedIcon from "@mui/icons-material/ChatBubbleOutlineRounded";
import InsightsRoundedIcon from "@mui/icons-material/InsightsRounded";
import SmartToyOutlinedIcon from "@mui/icons-material/SmartToyOutlined";
import ThumbDownAltRoundedIcon from "@mui/icons-material/ThumbDownAltRounded";
import ThumbUpAltRoundedIcon from "@mui/icons-material/ThumbUpAltRounded";
import {
  Alert,
  AlertTitle,
  Avatar,
  Box,
  Breadcrumbs,
  Button,
  Chip,
  Divider,
  Link as MuiLink,
  Paper,
  Skeleton,
  Stack,
  Typography,
} from "@mui/material";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  fetchFeedbackConversation,
  fetchFeedbackItem,
  type ConversationDetail,
  type FeedbackItem,
  type Message,
} from "../services/analysisApi";
import { CategoryChip } from "./CategoryChip";
import { EnrichmentPanel } from "./EnrichmentPanel";
import { MarkdownContent } from "./MarkdownContent";

function formatDate(value?: string | null): string {
  if (!value) return "Unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unavailable";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function metric(value: number | null, suffix = ""): string {
  return value === null || value === undefined ? "Unavailable" : `${value.toLocaleString()}${suffix}`;
}

/** input + output across the whole conversation. "Unavailable" only when both are missing. */
function totalTokens(input: number | null, output: number | null): string {
  if ((input ?? null) === null && (output ?? null) === null) return "Unavailable";
  return ((input ?? 0) + (output ?? 0)).toLocaleString();
}

function roleLabel(role: string): string {
  if (role === "assistant") return "JAI Assistant";
  if (role === "live_agent") return "Live agent";
  if (role === "system") return "System";
  return "User";
}

function suggestionsMarkdown(value?: string): string | undefined {
  const text = value?.trim();
  if (!text?.startsWith("[") || !text.endsWith("]")) return value;
  try {
    const parsed = JSON.parse(text) as unknown;
    if (Array.isArray(parsed) && parsed.every((item) => typeof item === "string")) return parsed.map((item) => `- ${item}`).join("\n");
  } catch {
    const items = text.slice(1, -1)
      .split(/"\s*,\s*"|'\s*,\s*'|"\s*,\s*'|'\s*,\s*"/)
      .map((item) => item.replace(/^["']|["']$/g, "").replace(/\\(["'])/g, "$1").trim())
      .filter(Boolean);
    if (items.length > 1) return items.map((item) => `- ${item}`).join("\n");
  }
  return value;
}

function AnalysisSection({ title, body, accent = false }: { title: string; body?: string; accent?: boolean }) {
  if (!body?.trim()) return null;
  return (
    <Box>
      <Typography variant="overline" sx={{ color: accent ? "primary.main" : "text.secondary" }}>{title}</Typography>
      <Box sx={{ mt: 0.35 }}><MarkdownContent>{body}</MarkdownContent></Box>
    </Box>
  );
}

function Metric({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <Box sx={{ p: 1.5, border: "1px solid", borderColor: "divider", borderRadius: 2.5, bgcolor: "#FAFBFC" }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.7, color: "text.secondary" }}>{icon}<Typography variant="caption" sx={{ fontWeight: 700 }}>{label}</Typography></Box>
      <Typography sx={{ mt: 0.6, fontWeight: 750 }}>{value}</Typography>
    </Box>
  );
}

export function FeedbackConversationDetail({
  id,
  initialDetail,
  initialFeedback,
}: {
  id: string;
  initialDetail?: ConversationDetail;
  initialFeedback?: FeedbackItem;
}) {
  const [detail, setDetail] = useState<ConversationDetail | null>(initialDetail ?? null);
  const [feedbackItem, setFeedbackItem] = useState<FeedbackItem | null>(initialFeedback ?? null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    if (initialDetail && initialFeedback) return;
    let active = true;
    setDetail(null);
    setFeedbackItem(null);
    setError(null);
    Promise.all([fetchFeedbackConversation(id), fetchFeedbackItem(id)])
      .then(([conversation, feedback]) => {
        if (!active) return;
        setDetail(conversation);
        setFeedbackItem(feedback);
      })
      .catch(() => { if (active) setError("This feedback conversation could not be loaded from the current API response."); });
    return () => { active = false; };
  }, [id, initialDetail, initialFeedback, reload]);

  if (error) return <Alert severity="error" action={<Button color="inherit" onClick={() => setReload((value) => value + 1)}>Try again</Button>}><AlertTitle>Feedback detail unavailable</AlertTitle>{error}</Alert>;
  if (!detail || !feedbackItem) return <Stack spacing={2.5} role="status" aria-label="Loading feedback conversation"><Skeleton variant="rounded" height={130} /><Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "1.5fr .75fr" }, gap: 2.5 }}><Skeleton variant="rounded" height={650} /><Skeleton variant="rounded" height={520} /></Box></Stack>;

  const positive = feedbackItem.rating === true;
  const source = detail.source ?? feedbackItem;
  const deep = detail.deep ?? feedbackItem.deep;
  const exactMessageId = feedbackItem.feedback_message_id ?? detail.feedback.message_id ?? null;
  const exactMessage = exactMessageId ? detail.messages.find((message) => message.id === exactMessageId) : undefined;
  const fallbackMessage = [...detail.messages].reverse().find((message) => message.role === "assistant");
  const highlightedMessage = exactMessage ?? fallbackMessage;
  const exactLink = Boolean(exactMessage);
  const accent = positive ? "#16815D" : "#C43D4B";
  const tint = positive ? "#F0FAF6" : "#FFF3F4";

  return (
    <Stack spacing={2.5}>
      <Breadcrumbs aria-label="Feedback navigation">
        <MuiLink component={Link} href="/feedback" underline="hover">Feedback</MuiLink>
        <Typography color="text.primary">{source?.title || id.slice(0, 8)}</Typography>
      </Breadcrumbs>

      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <Button component={Link} href="/feedback" startIcon={<ArrowBackRoundedIcon />} color="secondary">Back to feedback</Button>
        <Button component={Link} href={`/conversations/${id}`} endIcon={<ArrowForwardRoundedIcon />} sx={{ ml: "auto" }}>Standard analysis</Button>
      </Box>

      <Paper sx={{ p: { xs: 2.25, md: 3 }, borderTop: "4px solid", borderTopColor: accent, bgcolor: tint }}>
        <Box sx={{ display: "flex", alignItems: { xs: "flex-start", md: "center" }, justifyContent: "space-between", gap: 2, flexDirection: { xs: "column", md: "row" } }}>
          <Box sx={{ minWidth: 0 }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Chip
                icon={positive ? <ThumbUpAltRoundedIcon /> : <ThumbDownAltRoundedIcon />}
                label={positive ? "Positive feedback" : "Negative feedback"}
                color={positive ? "success" : "error"}
              />
              <CategoryChip category={detail.analysis.category} />
              <Chip size="small" variant="outlined" label={`${detail.analysis.confidence[0]?.toUpperCase()}${detail.analysis.confidence.slice(1)} confidence`} />
            </Stack>
            <Typography variant="h2" component="h1" sx={{ mt: 1.5, overflowWrap: "anywhere" }}>{source?.title || `Feedback conversation ${id}`}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.6 }}>Conversation ID {id}</Typography>
          </Box>
          <Box sx={{ minWidth: { md: 310 }, maxWidth: 520, p: 2, borderRadius: 2.5, bgcolor: "#FFFFFF", border: "1px solid", borderColor: `${accent}40` }}>
            <Typography variant="overline" sx={{ color: accent }}>User remark</Typography>
            <Box sx={{ mt: 0.4, fontWeight: 700, fontSize: 17 }}><MarkdownContent>{feedbackItem.comment ? `“${feedbackItem.comment}”` : "No written remark was provided."}</MarkdownContent></Box>
          </Box>
        </Box>
      </Paper>

      {!exactLink && highlightedMessage && (
        <Alert severity="info">
          The current API does not expose the exact feedback message ID. The final assistant response is highlighted as feedback context; it is not claimed as an exact source match.
        </Alert>
      )}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 1.55fr) minmax(340px, .72fr)" }, gap: 2.5, alignItems: "start" }}>
        <Paper aria-label="Feedback conversation transcript" sx={{ overflow: "hidden" }}>
          <Box sx={{ px: { xs: 2.25, md: 3 }, py: 2.5, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
            <Box><Typography variant="h3">Full conversation</Typography><Typography variant="body2" color="text.secondary">{detail.messages.length} ordered messages · highlighted response shows feedback context</Typography></Box>
            <ChatBubbleOutlineRoundedIcon sx={{ color: "text.secondary" }} />
          </Box>
          <Divider />
          <Stack sx={{ p: { xs: 2.25, md: 3 } }}>
            {detail.messages.map((message: Message, index) => {
              const assistant = message.role === "assistant";
              const highlighted = highlightedMessage?.id === message.id;
              return (
                <Box key={message.id} sx={{ display: "flex", gap: 1.5, pb: index === detail.messages.length - 1 ? 0 : 3 }}>
                  <Avatar sx={{ width: 36, height: 36, bgcolor: assistant ? "#FFF0E9" : "#EEF2F7", color: assistant ? "primary.main" : "secondary.main" }}>
                    {assistant ? <SmartToyOutlinedIcon sx={{ fontSize: 20 }} /> : <AccountCircleOutlinedIcon sx={{ fontSize: 20 }} />}
                  </Avatar>
                  <Box sx={{ minWidth: 0, flex: 1 }}>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
                      <Typography variant="body2" sx={{ fontWeight: 750 }}>{roleLabel(message.role)}</Typography>
                      {message.created_at && <Typography variant="caption" color="text.secondary">{formatDate(message.created_at)}</Typography>}
                      {message.model && <Typography variant="caption" color="text.secondary">· {message.model}</Typography>}
                      {highlighted && <Chip size="small" icon={positive ? <ThumbUpAltRoundedIcon /> : <ThumbDownAltRoundedIcon />} label={exactLink ? "Rated response" : "Feedback context"} color={positive ? "success" : "error"} />}
                    </Box>
                    <Box sx={{ mt: 0.75, px: 2, py: 1.6, borderRadius: 2.5, bgcolor: highlighted ? tint : assistant ? "#FFFFFF" : "#F7F8FA", border: highlighted ? "2px solid" : "1px solid", borderColor: highlighted ? accent : "divider", boxShadow: highlighted ? `0 8px 24px ${accent}18` : "none" }}>
                      <MarkdownContent>{message.content || "No message content"}</MarkdownContent>
                    </Box>
                    {highlighted && feedbackItem.comment && (
                      <Box sx={{ mt: 1, p: 1.4, borderRadius: 2, bgcolor: tint, borderLeft: "3px solid", borderColor: accent }}>
                        <Typography variant="caption" sx={{ color: accent, fontWeight: 750 }}>USER FEEDBACK ON THIS CONTEXT</Typography>
                        <Box sx={{ mt: 0.25, fontWeight: 650 }}><MarkdownContent>{feedbackItem.comment}</MarkdownContent></Box>
                      </Box>
                    )}
                  </Box>
                </Box>
              );
            })}
          </Stack>
        </Paper>

        <Stack spacing={2.5} sx={{ position: { lg: "sticky" }, top: { lg: 96 } }}>
          <Paper sx={{ p: 2.5 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}><InsightsRoundedIcon color="primary" /><Typography variant="h3">Root-cause analysis</Typography></Box>
            {deep ? (
              <Stack spacing={1.8} divider={<Divider flexItem />} sx={{ mt: 2 }}>
                <AnalysisSection title="What happened" body={deep.what_happened} />
                <AnalysisSection title="Why it happened" body={deep.why_it_happened} accent />
                <AnalysisSection title="How to avoid it" body={deep.how_to_avoid} />
                <AnalysisSection title="Suggestions" body={suggestionsMarkdown(deep.suggestions)} />
              </Stack>
            ) : <Alert severity="info" sx={{ mt: 2 }}>Deep analysis is not available in the API response yet.</Alert>}
          </Paper>

          <EnrichmentPanel enrichment={detail.enrichment} />

          <Paper sx={{ p: 2.5 }}>
            <Typography variant="h3">Recommended action</Typography>
            <Box sx={{ mt: 1.25, p: 1.6, bgcolor: "#FFF6F1", borderRadius: 2.5, borderLeft: "4px solid", borderColor: "primary.main" }}><MarkdownContent>{detail.analysis.recommended_next_step}</MarkdownContent></Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.5 }}>Model rationale</Typography>
            <Box sx={{ mt: 0.35 }}><MarkdownContent>{detail.analysis.rationale || feedbackItem.rationale || "No rationale available."}</MarkdownContent></Box>
          </Paper>

          <Paper sx={{ p: 2.5 }}>
            <Typography variant="h3">Conversation context</Typography>
            <Stack spacing={1.15} sx={{ mt: 2 }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">Tenant</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right" }}>{source?.tenant_name || "Unavailable"}</Typography></Box>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">User</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right", overflowWrap: "anywhere" }}>{source?.user_name || "Unavailable"}</Typography></Box>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">Created</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right" }}>{formatDate(source?.created_at)}</Typography></Box>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">Last message</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right" }}>{formatDate(source?.last_message_at)}</Typography></Box>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">Analysed</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right" }}>{formatDate(detail.analysis.analyzed_at)}</Typography></Box>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="body2" color="text.secondary">Analyzer</Typography><Typography variant="body2" sx={{ fontWeight: 700, textAlign: "right", overflowWrap: "anywhere" }}>{detail.analysis.analyzer_version || "Unavailable"}</Typography></Box>
            </Stack>
          </Paper>

          <Paper sx={{ p: 2.5 }}>
            <Typography variant="h3">Cost & responsiveness</Typography>
            <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1.25, mt: 2 }}>
              <Metric label="TTFT" value={metric(detail.metrics.ttft_ms, " ms")} icon={<AccessTimeRoundedIcon sx={{ fontSize: 16 }} />} />
              <Metric label="Input tokens" value={metric(detail.metrics.input_tokens)} icon={<BoltRoundedIcon sx={{ fontSize: 16 }} />} />
              <Metric label="Output tokens" value={metric(detail.metrics.output_tokens)} icon={<BoltRoundedIcon sx={{ fontSize: 16 }} />} />
              <Metric label="Total tokens" value={totalTokens(detail.metrics.input_tokens, detail.metrics.output_tokens)} icon={<BoltRoundedIcon sx={{ fontSize: 16 }} />} />
            </Box>
          </Paper>
        </Stack>
      </Box>
    </Stack>
  );
}
