"use client";

import { Container } from "@mui/material";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ConversationDetail } from "../../../src/components/ConversationDetail";

export default function ConversationPage() {
  const params = useParams();
  const id = String(params.id);
  return (
    <Container sx={{ py: 4 }}>
      <Link href="/">← Back to all conversations</Link>
      <div style={{ marginTop: 16 }}>
        <ConversationDetail id={id} />
      </div>
    </Container>
  );
}
