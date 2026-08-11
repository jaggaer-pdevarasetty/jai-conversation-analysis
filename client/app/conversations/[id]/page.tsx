"use client";

import ArrowBackRoundedIcon from "@mui/icons-material/ArrowBackRounded";
import { Box, Button, Typography } from "@mui/material";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ConversationDetail } from "../../../src/components/ConversationDetail";

export default function ConversationPage() {
  const params = useParams();
  const id = String(params.id);
  return (
    <>
      <Box sx={{ mb: 2.5, display: "flex", alignItems: "center", gap: 1.5 }}>
        <Button component={Link} href="/conversations" startIcon={<ArrowBackRoundedIcon />} color="secondary">
          Back to queue
        </Button>
        <Typography variant="caption" color="text.secondary" sx={{ display: { xs: "none", sm: "block" } }}>
          Conversation {id.slice(0, 8)}…
        </Typography>
      </Box>
      <ConversationDetail id={id} />
    </>
  );
}
