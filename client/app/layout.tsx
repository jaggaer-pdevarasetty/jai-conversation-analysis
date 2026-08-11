import type { ReactNode } from "react";
import { AppShell } from "../src/components/AppShell";
import { Providers } from "../src/components/Providers";

export const metadata = {
  title: "JAI Conversation Intelligence",
  description: "Tenant conversation administration and evidence-led review for JAI Assist",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0 }}>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
