"use client";

import Chip from "@mui/material/Chip";

const STYLE: Record<string, { bg: string; fg: string; label: string }> = {
  resolved: { bg: "#e7f5ec", fg: "#1b7f3b", label: "Resolved" },
  failed_to_resolve: { bg: "#fdecec", fg: "#c62828", label: "Failed to resolve" },
  positive_feedback: { bg: "#e8f1fd", fg: "#1565c0", label: "Positive feedback" },
  negative_feedback: { bg: "#fdefe3", fg: "#e65100", label: "Negative feedback" },
  out_of_scope: { bg: "#f0f0f3", fg: "#5b5b6b", label: "Out of scope" },
};

export function CategoryChip({ category }: { category: string | null }) {
  if (!category) return <Chip size="small" label="Not analysed" variant="outlined" />;
  const s = STYLE[category] ?? { bg: "#f0f0f3", fg: "#5b5b6b", label: category };
  return (
    <Chip
      size="small"
      label={s.label}
      sx={{ bgcolor: s.bg, color: s.fg, fontWeight: 600, border: "none" }}
    />
  );
}
