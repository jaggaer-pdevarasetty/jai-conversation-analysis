"use client";

import { Breadcrumbs, Link as MuiLink, Typography } from "@mui/material";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ConversationDetail } from "../../../src/components/ConversationDetail";

export default function ConversationPage() {
  const params = useParams();
  const id = String(params.id);
  return (
    <>
      <Breadcrumbs sx={{ mb: 2 }}>
        <MuiLink component={Link} href="/conversations">
          Conversations
        </MuiLink>
        <Typography color="text.primary">{id.slice(0, 8)}</Typography>
      </Breadcrumbs>
      <ConversationDetail id={id} />
    </>
  );
}
