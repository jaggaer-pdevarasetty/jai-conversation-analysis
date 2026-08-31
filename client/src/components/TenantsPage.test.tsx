import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TenantsPage from "../../app/tenants/page";
import type { Tenant } from "../services/dashboardApi";

const mockFetchTenants = jest.fn();

jest.mock("../services/dashboardApi", () => ({
  ...jest.requireActual("../services/dashboardApi"),
  fetchTenants: (...args: unknown[]) => mockFetchTenants(...args),
}));

jest.mock("./RegionContext", () => ({
  useRegion: () => ({ region: "us", loading: false }),
}));

const tenants: Tenant[] = [
  {
    tenant_id: "1",
    name: "ENEL S.p.A.",
    conversations: 100,
    users: 10,
    ea: { key: "enel", label: "ENEL", product: "JI", status: "active", privacy: "RoPA / ISO 42001", privacy_sensitive: true },
  },
  { tenant_id: "2", name: "Acme Corp", conversations: 50, users: 5, ea: null },
];

describe("TenantsPage — Early Access", () => {
  beforeEach(() => {
    mockFetchTenants.mockReset();
    mockFetchTenants.mockResolvedValue(tenants);
  });

  it("badges Early Access tenants (with a privacy flag) and filters to EA only", async () => {
    render(<TenantsPage />);
    expect(await screen.findByText("ENEL S.p.A.")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();

    // EA badge + privacy flag on the ENEL card
    expect(screen.getByText("Early Access · JI")).toBeInTheDocument();
    expect(screen.getByText("Privacy")).toBeInTheDocument();

    // "Early Access only" filter hides the non-EA tenant
    await userEvent.click(screen.getByLabelText("Early Access only"));
    expect(screen.queryByText("Acme Corp")).not.toBeInTheDocument();
    expect(screen.getByText("ENEL S.p.A.")).toBeInTheDocument();
  });

  it("'Clear filters' in the empty state resets the Early Access filter too", async () => {
    render(<TenantsPage />);
    await screen.findByText("ENEL S.p.A.");
    await userEvent.click(screen.getByLabelText("Early Access only"));
    await userEvent.type(screen.getByLabelText("Search tenants"), "zzz-no-match");
    // both hidden → empty state with a Clear filters button
    await userEvent.click(await screen.findByRole("button", { name: "Clear filters" }));
    expect(await screen.findByText("Acme Corp")).toBeInTheDocument(); // EA filter cleared
    expect(screen.getByText("ENEL S.p.A.")).toBeInTheDocument();
  });
});
