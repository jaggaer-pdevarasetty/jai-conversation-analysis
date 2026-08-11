# ADR-0015 — Safe transcript Markdown and responsive filters

**Status:** Accepted (2026-08-11)

## Context
Assistant messages contain Markdown for emphasis, steps, links, and code, but the transcript showed
raw syntax. The review-queue filter bar also used native selects with floating MUI labels in a grid
that became narrower after the desktop drawer, causing duplicated labels and overlapping controls.
Conversation content is untrusted, so rendering arbitrary HTML is not acceptable.

## Options considered
1. **Keep plain text.** Safest and smallest, but produces a visibly broken transcript for normal
   assistant responses.
2. **Add a full Markdown dependency.** Broad syntax coverage, but adds a large dependency tree and
   its ESM-only build conflicts with the current Jest setup.
3. **Render the needed safe Markdown subset in React.** Covers headings, emphasis, lists, links,
   code, quotes, and rules without HTML parsing or `dangerouslySetInnerHTML`.

## Decision
Choose option 3. `MarkdownContent` converts the supported Markdown subset directly to React nodes,
rejects unsafe link protocols, and styles output within the existing MUI theme. Use it for transcript
messages, recommendations, and rationale.

Replace every native `Select` + floating `InputLabel` combination with MUI `TextField select`.
Filter grids use one, two, or three equal columns by breakpoint rather than fixed minimum widths.
The pooled queue adds a review-state filter (attention, feedback, override, missing telemetry) and
sorting by response latency or token use.

## Consequences
- Raw HTML remains text and scripts are never executed.
- No runtime dependency is added.
- Full table/task-list Markdown is deferred until real conversations require it.
- Filters no longer overlap at desktop, tablet, or mobile widths.
