import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { fetchPending, triggerSweep } from "../services/analysisApi";
import { AnalyzeNowButton } from "./AnalyzeNowButton";

jest.mock("../services/analysisApi", () => ({
  fetchPending: jest.fn(),
  triggerSweep: jest.fn(),
}));
const mockFetch = fetchPending as jest.MockedFunction<typeof fetchPending>;
const mockTrigger = triggerSweep as jest.MockedFunction<typeof triggerSweep>;

describe("AnalyzeNowButton (two-step, region-aware)", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockTrigger.mockReset();
  });

  it("fetches first, shows count + a Start button, then analyses on Start", async () => {
    mockFetch.mockResolvedValue({
      count: 3,
      ids: ["a", "b", "c"],
      by_region: { us: 2, eu: 1 },
      items: [
        { conversation_id: "a", region: "us", tenant_name: "ShopBlue", title: "Approvals", last_message_at: null },
        { conversation_id: "b", region: "us", tenant_name: "ShopBlue", title: "Invoices", last_message_at: null },
        { conversation_id: "c", region: "eu", tenant_name: "Hitachi", title: "Suppliers", last_message_at: null },
      ],
    });
    mockTrigger.mockResolvedValue("started");
    render(<AnalyzeNowButton />);

    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(mockFetch).toHaveBeenCalledTimes(1);
    // fetched: count + Start button appear (Start only shows after fetching)
    expect(await screen.findByText(/new \/ unanalyzed conversation/i)).toBeInTheDocument();
    expect(screen.getByText("US: 2")).toBeInTheDocument(); // per-region breakdown
    expect(screen.getByText("Approvals")).toBeInTheDocument();
    expect(screen.getByText("Invoices")).toBeInTheDocument();
    expect(screen.getByText("Suppliers")).toBeInTheDocument();
    expect(screen.queryByText(/Showing .* of/)).not.toBeInTheDocument();
    const start = await screen.findByRole("button", { name: /start analysis/i });

    await userEvent.click(start);
    expect(mockTrigger).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/analysis started/i)).toBeInTheDocument();
  });

  it("offers no Start button when there is nothing new to analyse", async () => {
    mockFetch.mockResolvedValue({ count: 0, ids: [], by_region: {}, items: [] });
    render(<AnalyzeNowButton />);
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(await screen.findByText(/everything is already analyzed/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start analysis/i })).not.toBeInTheDocument();
    expect(mockTrigger).not.toHaveBeenCalled();
  });

  it("shows an error when the fetch fails", async () => {
    mockFetch.mockRejectedValue(new Error("network"));
    render(<AnalyzeNowButton />);
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(await screen.findByText(/couldn't fetch conversations/i)).toBeInTheDocument();
  });
});
