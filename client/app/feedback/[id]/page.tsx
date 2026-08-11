"use client";

import { useParams } from "next/navigation";
import { FeedbackConversationDetail } from "../../../src/components/FeedbackConversationDetail";

export default function FeedbackConversationPage() {
  const params = useParams();
  return <FeedbackConversationDetail id={String(params.id)} />;
}
