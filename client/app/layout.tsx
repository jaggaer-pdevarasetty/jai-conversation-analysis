import type { ReactNode } from "react";

export const metadata = {
  title: "Conversation Analysis",
  description: "Auto-labelled JAI Assist conversations for internal reviewers",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
