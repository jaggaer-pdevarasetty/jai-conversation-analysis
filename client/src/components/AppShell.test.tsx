import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppShell, idSearchHref } from "./AppShell";

const mockPush = jest.fn();
const mockSetRegion = jest.fn();

jest.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: mockPush }),
}));

jest.mock("./RegionContext", () => ({
  useRegion: () => ({
    region: "",
    setRegion: mockSetRegion,
    regions: [{ label: "us", reachable: true, counts: {}, error: null }],
  }),
}));

describe("Overview ID search", () => {
  it("routes conversation UUIDs and tenant IDs to their records", () => {
    expect(idSearchHref("4512ec35-9164-4225-a7eb-06c1a26cf652")).toBe("/conversations/4512ec35-9164-4225-a7eb-06c1a26cf652");
    expect(idSearchHref("20256789")).toBe("/tenants/20256789");
  });
});

describe("AppShell", () => {
  beforeEach(() => jest.clearAllMocks());

  it("routes to Overview, Tenants, and the pooled review queue", () => {
    render(<AppShell><div>Overview content</div></AppShell>);
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Tenants" })).toHaveAttribute("href", "/tenants");
    expect(screen.getByRole("link", { name: "Review queue" })).toHaveAttribute("href", "/conversations");
    expect(screen.getByText("Operational overview")).toBeInTheDocument();
  });

  it("returns to the overview when the region changes", async () => {
    render(<AppShell><div>Overview content</div></AppShell>);
    await userEvent.click(screen.getByRole("combobox"));
    await userEvent.click(await screen.findByRole("option", { name: "US" }));
    expect(mockSetRegion).toHaveBeenCalledWith("us");
    expect(mockPush).toHaveBeenCalledWith("/");
  });
});
