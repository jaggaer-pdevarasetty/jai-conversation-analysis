"use client";

import Chip from "@mui/material/Chip";

export const CATEGORY_META: Record<string, { bg: string; fg: string; bar: string; label: string }> = {
  resolved: { bg: "#E7F6F0", fg: "#137052", bar: "#26A77A", label: "Resolved" },
  failed_to_resolve: { bg: "#FDECEF", fg: "#A83242", bar: "#D94A5A", label: "Failed to resolve" },
  positive_feedback: { bg: "#EAF2FF", fg: "#245FA8", bar: "#4F8BD5", label: "Positive feedback" },
  negative_feedback: { bg: "#FFF0E3", fg: "#A94D05", bar: "#E77720", label: "Negative feedback" },
  out_of_scope: { bg: "#EFF1F4", fg: "#505B6D", bar: "#7B8492", label: "Out of scope" },
};

export function categoryLabel(category: string | null): string {
  return category ? (CATEGORY_META[category]?.label ?? category) : "Not analysed";
}

export function CategoryChip({ category }: { category: string | null }) {
  if (!category) return <Chip size="small" label="Not analysed" variant="outlined" />;
  const s = CATEGORY_META[category] ?? { bg: "#EFF1F4", fg: "#505B6D", bar: "#7B8492", label: category };
  return (
    <Chip
      size="small"
      label={s.label}
      sx={{ bgcolor: s.bg, color: s.fg, fontWeight: 700, border: "1px solid", borderColor: `${s.bar}33` }}
    />
  );
}
