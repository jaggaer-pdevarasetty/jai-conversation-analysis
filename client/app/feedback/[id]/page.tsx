"use client";

import { useParams, useSearchParams } from "next/navigation";
import { FeedbackConversationDetail } from "../../../src/components/FeedbackConversationDetail";

export default function FeedbackConversationPage() {
  const params = useParams();
  const messageId = useSearchParams().get("message_id") ?? undefined;
  return <FeedbackConversationDetail id={String(params.id)} selectedFeedbackMessageId={messageId} />;
}
