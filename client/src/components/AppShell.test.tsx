import { render, screen } from "@testing-library/react";
import { AppShell } from "./AppShell";

jest.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

describe("AppShell", () => {
  it("routes to Overview, Tenants, and the pooled review queue", () => {
    render(<AppShell><div>Overview content</div></AppShell>);
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Tenants" })).toHaveAttribute("href", "/tenants");
    expect(screen.getByRole("link", { name: "Review queue" })).toHaveAttribute("href", "/conversations");
    expect(screen.getByText("Operational overview")).toBeInTheDocument();
  });
});
