"use client";

import { Container, Typography } from "@mui/material";
import { ReviewerTable } from "../src/components/ReviewerTable";

export default function Page() {
  return (
    <Container sx={{ py: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Conversation Analysis
      </Typography>
      <Typography variant="body1" gutterBottom>
        Every completed JAI Assist conversation, auto-labelled with a recommended next step.
      </Typography>
      <ReviewerTable />
    </Container>
  );
}
