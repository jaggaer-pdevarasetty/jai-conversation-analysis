"use client";

import {
  Alert,
  Breadcrumbs,
  Link as MuiLink,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CategoryChip } from "../../../../../src/components/CategoryChip";
import { fetchUserConversations, type UserConversation } from "../../../../../src/services/dashboardApi";

export default function UserConversationsPage() {
  const params = useParams();
  const tenantId = String(params.tenantId);
  const userId = String(params.userId);
  const [items, setItems] = useState<UserConversation[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchUserConversations(tenantId, userId)
      .then(setItems)
      .catch(() => setError("Could not load conversations."));
  }, [tenantId, userId]);

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!items) return <Typography>Loading…</Typography>;

  return (
    <>
      <Breadcrumbs sx={{ mb: 1 }}>
        <MuiLink component={Link} href="/tenants">
          Tenants
        </MuiLink>
        <MuiLink component={Link} href={`/tenants/${tenantId}`}>
          Users
        </MuiLink>
        <Typography color="text.primary">Conversations</Typography>
      </Breadcrumbs>
      <Typography variant="h4" gutterBottom>
        Conversations
      </Typography>
      <TableContainer component={Paper}>
        <Table aria-label="Conversations">
          <TableHead>
            <TableRow>
              <TableCell>Conversation</TableCell>
              <TableCell>Category</TableCell>
              <TableCell>Recommended next step</TableCell>
              <TableCell align="right">Messages</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((c) => (
              <TableRow key={c.conversation_id} hover>
                <TableCell>
                  <MuiLink component={Link} href={`/conversations/${c.conversation_id}`} sx={{ fontWeight: 600 }}>
                    {c.title || c.conversation_id.slice(0, 8)}
                  </MuiLink>
                </TableCell>
                <TableCell>
                  <CategoryChip category={c.category} />
                </TableCell>
                <TableCell sx={{ color: "text.secondary" }}>{c.recommended_next_step ?? "—"}</TableCell>
                <TableCell align="right">{c.message_count ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
}
