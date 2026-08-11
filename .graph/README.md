# .graph/ — AST code graph

This directory holds the **AST code graph** built by **codebase-memory-mcp** (registered in
`../.mcp.json`). The graph gives AI tools structural memory of the codebase for the
EXPLORE stage of the loop.

- Generated artifacts (`*.json`) are build output and are gitignored (see `.gitignore`).
- Rebuild via the codebase-memory-mcp server (the MCP indexes `src/` on demand).

> The graph is produced by the MCP tool at index time; it is not hand-authored.
