"use client";

import { Box } from "@mui/material";
import { createElement, Fragment, type ReactNode } from "react";

const INLINE = /(\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)|\*([^*\n]+)\*|~~(.+?)~~)/g;

function inline(text: string, prefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let cursor = 0;
  let index = 0;
  for (const match of text.matchAll(INLINE)) {
    const start = match.index ?? 0;
    if (start > cursor) nodes.push(text.slice(cursor, start));
    const token = match[0];
    const key = `${prefix}-${index++}`;
    if (match[2] !== undefined) {
      nodes.push(<strong key={key}>{inline(match[2], key)}</strong>);
    } else if (match[3] !== undefined) {
      nodes.push(<code key={key}>{match[3]}</code>);
    } else if (match[4] !== undefined && match[5] !== undefined) {
      const href = /^(https?:|mailto:|\/|#)/i.test(match[5]) ? match[5] : "#";
      nodes.push(<a key={key} href={href} target={href.startsWith("http") ? "_blank" : undefined} rel={href.startsWith("http") ? "noreferrer" : undefined}>{inline(match[4], key)}</a>);
    } else if (match[6] !== undefined) {
      nodes.push(<em key={key}>{inline(match[6], key)}</em>);
    } else if (match[7] !== undefined) {
      nodes.push(<del key={key}>{inline(match[7], key)}</del>);
    } else {
      nodes.push(token);
    }
    cursor = start + token.length;
  }
  if (cursor < text.length) nodes.push(text.slice(cursor));
  return nodes;
}

function startsBlock(line: string): boolean {
  return /^\s*(```|#{1,6}\s|[-*+]\s|\d+[.)]\s|>\s|([-*_]\s*){3,})/.test(line);
}

function blocks(markdown: string): ReactNode[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const nodes: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
      continue;
    }
    if (line.trimStart().startsWith("```")) {
      const language = line.trim().slice(3).trim();
      const code: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].trimStart().startsWith("```")) code.push(lines[i++]);
      i += 1;
      nodes.push(<pre key={`block-${i}`}><code data-language={language || undefined}>{code.join("\n")}</code></pre>);
      continue;
    }
    const heading = line.match(/^\s*(#{1,6})\s+(.+)$/);
    if (heading) {
      nodes.push(createElement(`h${heading[1].length}`, { key: `block-${i}` }, inline(heading[2], `heading-${i}`)));
      i += 1;
      continue;
    }
    const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
    if (unordered) {
      const items: ReactNode[] = [];
      while (i < lines.length) {
        const item = lines[i].match(/^\s*[-*+]\s+(.+)$/);
        if (!item) break;
        items.push(<li key={`item-${i}`}>{inline(item[1], `item-${i}`)}</li>);
        i += 1;
      }
      nodes.push(<ul key={`block-${i}`}>{items}</ul>);
      continue;
    }
    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (ordered) {
      const items: ReactNode[] = [];
      while (i < lines.length) {
        const item = lines[i].match(/^\s*\d+[.)]\s+(.+)$/);
        if (!item) break;
        items.push(<li key={`item-${i}`}>{inline(item[1], `item-${i}`)}</li>);
        i += 1;
      }
      nodes.push(<ol key={`block-${i}`}>{items}</ol>);
      continue;
    }
    if (/^\s*>\s?/.test(line)) {
      const quote: string[] = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) quote.push(lines[i++].replace(/^\s*>\s?/, ""));
      nodes.push(<blockquote key={`block-${i}`}>{inline(quote.join(" "), `quote-${i}`)}</blockquote>);
      continue;
    }
    if (/^\s*([-*_]\s*){3,}$/.test(line)) {
      nodes.push(<hr key={`block-${i}`} />);
      i += 1;
      continue;
    }
    const paragraph = [line.trim()];
    i += 1;
    while (i < lines.length && lines[i].trim() && !startsBlock(lines[i])) paragraph.push(lines[i++].trim());
    nodes.push(<p key={`block-${i}`}>{inline(paragraph.join(" "), `paragraph-${i}`)}</p>);
  }
  return nodes;
}

export function MarkdownContent({ children }: { children: string }) {
  return (
    <Box
      sx={{
        overflowWrap: "anywhere",
        "& > :first-of-type": { mt: 0 },
        "& > :last-child": { mb: 0 },
        "& p": { my: 1, lineHeight: 1.65 },
        "& h1, & h2, & h3, & h4, & h5, & h6": { mt: 2, mb: 0.8, lineHeight: 1.3, fontWeight: 750 },
        "& h1": { fontSize: "1.35rem" },
        "& h2": { fontSize: "1.2rem" },
        "& h3, & h4, & h5, & h6": { fontSize: "1.05rem" },
        "& ul, & ol": { my: 1, pl: 3 },
        "& li": { mb: 0.5, pl: 0.25 },
        "& strong": { fontWeight: 750 },
        "& a": { color: "primary.main", textDecorationColor: "primary.light", textUnderlineOffset: 2 },
        "& code": { px: 0.6, py: 0.2, borderRadius: 1, bgcolor: "#EEF1F5", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: "0.88em" },
        "& pre": { my: 1.25, p: 1.5, overflowX: "auto", borderRadius: 2, bgcolor: "#111827", color: "#F8FAFC" },
        "& pre code": { p: 0, bgcolor: "transparent", color: "inherit" },
        "& blockquote": { my: 1.25, mx: 0, pl: 1.5, borderLeft: "3px solid", borderColor: "primary.light", color: "text.secondary" },
        "& hr": { my: 2, border: 0, borderTop: "1px solid", borderColor: "divider" },
      }}
    >
      <Fragment>{blocks(children)}</Fragment>
    </Box>
  );
}
