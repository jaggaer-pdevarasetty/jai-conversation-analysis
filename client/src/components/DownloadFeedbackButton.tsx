"use client";

import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import { Button, ListItemText, Menu, MenuItem } from "@mui/material";
import { useState } from "react";
import { feedbackExportUrl, type ExportFormat, type FeedbackExportParams } from "../services/analysisApi";

const FORMATS: { fmt: ExportFormat; label: string; hint: string }[] = [
  { fmt: "csv", label: "CSV", hint: "Spreadsheet — one row per conversation" },
  { fmt: "pdf", label: "PDF", hint: "Formatted report" },
  { fmt: "json", label: "JSON", hint: "Full data incl. transcript" },
];

/** Download button + format menu for the feedback export. Passes the current view's filters
 * (region/scope/rating/category/search/tenant/date/sort) so the file matches exactly what the
 * reviewer is looking at, with full detail for every matching conversation (not just the page). */
export function DownloadFeedbackButton({ disabled, ...params }: FeedbackExportParams & { disabled?: boolean }) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);

  const download = (format: ExportFormat) => {
    const a = document.createElement("a");
    a.href = feedbackExportUrl({ ...params, format });
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setAnchor(null);
  };

  return (
    <>
      <Button
        variant="outlined"
        size="small"
        startIcon={<DownloadRoundedIcon />}
        onClick={(e) => setAnchor(e.currentTarget)}
        disabled={disabled}
        aria-haspopup="menu"
        aria-expanded={anchor ? "true" : undefined}
      >
        Download
      </Button>
      <Menu open={Boolean(anchor)} anchorEl={anchor} onClose={() => setAnchor(null)}>
        {FORMATS.map((f) => (
          <MenuItem key={f.fmt} onClick={() => download(f.fmt)}>
            <ListItemText primary={f.label} secondary={f.hint} />
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
