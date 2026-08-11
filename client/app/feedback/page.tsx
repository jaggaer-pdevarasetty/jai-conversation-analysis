"use client";

import ThumbDownAltRoundedIcon from "@mui/icons-material/ThumbDownAltRounded";
import ThumbUpAltRoundedIcon from "@mui/icons-material/ThumbUpAltRounded";
import {
  Alert,
  Box,
  Chip,
  Divider,
  Link as MuiLink,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CategoryChip } from "../../src/components/CategoryChip";
import { MarkdownContent } from "../../src/components/MarkdownContent";
import { fetchFeedback, type FeedbackItem } from "../../src/services/analysisApi";

function Section({ title, body, accent }: { title: string; body: string; accent?: boolean }) {
  if (!body?.trim()) return null;
  return (
    <Box>
      <Typography
        variant="overline"
        sx={{ color: accent ? "primary.main" : "text.secondary", fontWeight: 700, letterSpacing: 0.4 }}
      >
        {title}
      </Typography>
      <Box sx={{ mt: 0.25 }}>
        <MarkdownContent>{body}</MarkdownContent>
      </Box>
    </Box>
  );
}

function FeedbackCard({ item }: { item: FeedbackItem }) {
  const positive = item.rating === true;
  const deep = item.deep;
  return (
    <Paper sx={{ p: 2.5, borderLeft: "4px solid", borderColor: positive ? "#1b7f3b" : "#c62828" }}>
      <Stack direction="row" spacing={1.25} alignItems="center" flexWrap="wrap" useFlexGap>
        {positive ? (
          <ThumbUpAltRoundedIcon sx={{ color: "#1b7f3b" }} />
        ) : (
          <ThumbDownAltRoundedIcon sx={{ color: "#c62828" }} />
        )}
        <Typography sx={{ fontWeight: 700 }}>
          {positive ? "Positive feedback" : "Negative feedback"}
        </Typography>
        <CategoryChip category={item.category} />
        <Box sx={{ flexGrow: 1 }} />
        <MuiLink component={Link} href={`/conversations/${item.conversation_id}`} sx={{ fontWeight: 600 }}>
          Open conversation →
        </MuiLink>
      </Stack>

      {item.comment && (
        <Box
          sx={{
            mt: 1.5,
            p: 1.5,
            bgcolor: "#f7f8fa",
            borderRadius: 2,
            borderLeft: "3px solid",
            borderColor: "divider",
          }}
        >
          <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 700 }}>
            USER REMARK
          </Typography>
          <Typography sx={{ fontStyle: "italic" }}>&ldquo;{item.comment}&rdquo;</Typography>
        </Box>
      )}

      {deep ? (
        <Stack spacing={1.75} sx={{ mt: 2 }} divider={<Divider flexItem />}>
          <Section title="What happened" body={deep.what_happened} />
          <Section title="Why it happened (root cause)" body={deep.why_it_happened} accent />
          <Section title="How to avoid it" body={deep.how_to_avoid} />
          <Section title="Suggestions for the team" body={deep.suggestions} />
        </Stack>
      ) : (
        <Alert severity="info" sx={{ mt: 2 }}>
          Deep analysis not generated yet — open the conversation and re-analyse to produce it.
        </Alert>
      )}
    </Paper>
  );
}

export default function FeedbackPage() {
  const [items, setItems] = useState<FeedbackItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchFeedback()
      .then((d) => setItems(d.items))
      .catch(() => setError("Could not load feedback."));
  }, []);

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!items) return <Typography>Loading…</Typography>;

  const positive = items.filter((i) => i.rating === true).length;
  const negative = items.filter((i) => i.rating === false).length;

  return (
    <Stack spacing={2.5}>
      <Box>
        <Typography variant="h4">User feedback</Typography>
        <Typography color="text.secondary">
          Conversations where the user explicitly rated JAI. These matter most — each gets a
          deeper root-cause analysis.
        </Typography>
      </Box>

      <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap>
        <Chip label={`Total: ${items.length}`} sx={{ fontWeight: 700 }} />
        <Chip
          icon={<ThumbUpAltRoundedIcon />}
          label={`Positive: ${positive}`}
          sx={{ bgcolor: "#e7f5ec", color: "#1b7f3b", fontWeight: 700 }}
        />
        <Chip
          icon={<ThumbDownAltRoundedIcon />}
          label={`Negative: ${negative}`}
          sx={{ bgcolor: "#fdecec", color: "#c62828", fontWeight: 700 }}
        />
      </Stack>

      {items.length === 0 ? (
        <Alert severity="info">No conversations have explicit thumbs feedback yet.</Alert>
      ) : (
        <Stack spacing={2}>
          {items.map((item) => (
            <FeedbackCard key={item.conversation_id} item={item} />
          ))}
        </Stack>
      )}
    </Stack>
  );
}
