import type { ReactNode } from "react";
import { AppShell } from "../src/components/AppShell";
import { Providers } from "../src/components/Providers";

export const metadata = {
  title: "JAGGAER · Conversation Analysis",
  description: "Auto-analysed JAI Assist conversations for internal reviewers",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
