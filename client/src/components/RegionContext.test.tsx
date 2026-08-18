import { render, screen, waitFor } from "@testing-library/react";
import { fetchRegions } from "../services/dashboardApi";
import { RegionProvider, useRegion } from "./RegionContext";

jest.mock("../services/dashboardApi", () => ({
  fetchRegions: jest.fn(),
}));

const fetchRegionsMock = fetchRegions as jest.MockedFunction<typeof fetchRegions>;

function RegionProbe() {
  const { region, loading } = useRegion();
  return <div>{loading ? "Loading" : region || "All regions"}</div>;
}

describe("RegionProvider", () => {
  beforeEach(() => {
    window.localStorage.clear();
    fetchRegionsMock.mockReset();
  });

  it("falls back to All regions when the saved region is unreachable", async () => {
    window.localStorage.setItem("jai.region", "eu");
    fetchRegionsMock.mockResolvedValue([
      { label: "us", reachable: true, counts: {}, error: null },
      { label: "eu", reachable: false, counts: {}, error: "unreachable" },
    ]);
    render(<RegionProvider><RegionProbe /></RegionProvider>);
    expect(screen.getByText("Loading")).toBeInTheDocument();
    expect(await screen.findByText("All regions")).toBeInTheDocument();
    // The saved region is only unreachable right now — keep it stored so it's restored once the
    // region recovers, rather than erasing the user's choice permanently.
    await waitFor(() => expect(window.localStorage.getItem("jai.region")).toBe("eu"));
  });
});
