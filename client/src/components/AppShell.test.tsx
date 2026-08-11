import { render, screen } from "@testing-library/react";
import { AppShell } from "./AppShell";

jest.mock("next/navigation", () => ({
  usePathname: () => "/tenants",
}));

describe("AppShell", () => {
  it("routes the primary workspace through tenants without a health overview", () => {
    render(<AppShell><div>Tenant content</div></AppShell>);
    expect(screen.getByRole("link", { name: "Tenants" })).toHaveAttribute("href", "/tenants");
    expect(screen.queryByText("Health overview")).not.toBeInTheDocument();
    expect(screen.getByText("Authorised admin view")).toBeInTheDocument();
  });
});
