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

describe("AnalyzeNowButton (two-step)", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockTrigger.mockReset();
  });

  it("fetches first, shows the count + a Start button, then analyses on Start", async () => {
    mockFetch.mockResolvedValue({ count: 3, ids: ["a", "b", "c"] });
    mockTrigger.mockResolvedValue("started");
    render(<AnalyzeNowButton />);

    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(mockFetch).toHaveBeenCalledTimes(1);
    // fetched: count shown + Start button appears (only after fetching)
    expect(await screen.findByText(/found 3 new/i)).toBeInTheDocument();
    const start = screen.getByRole("button", { name: /start analysis/i });

    await userEvent.click(start);
    expect(mockTrigger).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/analysis started/i)).toBeInTheDocument();
  });

  it("offers no Start button when there is nothing new to analyse", async () => {
    mockFetch.mockResolvedValue({ count: 0, ids: [] });
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
