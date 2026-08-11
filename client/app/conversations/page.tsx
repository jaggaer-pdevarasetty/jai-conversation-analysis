"use client";

import { Typography } from "@mui/material";
import { ReviewerTable } from "../../src/components/ReviewerTable";

export default function AllConversationsPage() {
  return (
    <>
      <Typography variant="h4" gutterBottom>
        All conversations
      </Typography>
      <ReviewerTable />
    </>
  );
}
