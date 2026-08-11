"use client";

import { Box, Chip, Stack, Typography } from "@mui/material";
import { ReviewerTable } from "../../src/components/ReviewerTable";

export default function AllConversationsPage() {
  return (
    <Stack spacing={3}>
      <Box sx={{ display: "flex", alignItems: { xs: "flex-start", md: "flex-end" }, justifyContent: "space-between", gap: 2, flexDirection: { xs: "column", md: "row" } }}>
        <Box>
          <Typography variant="overline" color="primary.main">Reviewer workflow</Typography>
          <Typography variant="h1" component="h1">Conversation review queue</Typography>
          <Typography color="text.secondary" sx={{ mt: 1, maxWidth: 720 }}>
            Start with unresolved and low-confidence conversations, inspect the evidence, and override the category when human judgment differs.
          </Typography>
        </Box>
        <Chip label="Up to 200 conversations per view" variant="outlined" sx={{ bgcolor: "#FFFFFF" }} />
      </Box>
      <ReviewerTable />
    </Stack>
  );
}
