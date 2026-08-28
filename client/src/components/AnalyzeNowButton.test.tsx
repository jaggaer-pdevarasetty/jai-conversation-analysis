import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { fetchPending, triggerSweep, type PendingResponse } from "../services/analysisApi";
import { AnalyzeNowButton } from "./AnalyzeNowButton";

jest.mock("../services/analysisApi", () => ({
  fetchPending: jest.fn(),
  triggerSweep: jest.fn(),
}));
let mockEnv = "uit";
jest.mock("./EnvContext", () => ({
  useEnv: () => ({ env: mockEnv, setEnv: () => {}, environments: ["uit", "prod"], loading: false }),
}));
const mockFetch = fetchPending as jest.MockedFunction<typeof fetchPending>;
const mockTrigger = triggerSweep as jest.MockedFunction<typeof triggerSweep>;

describe("AnalyzeNowButton", () => {
  beforeEach(() => {
    mockEnv = "uit";
    mockFetch.mockReset();
    mockTrigger.mockReset();
  });

  it("UIT: fetches, shows the total/feedback/normal breakdown + a Start button, then analyses on Start", async () => {
    const feedbackPending: PendingResponse = { count: 1, ids: ["a"], by_region: { us: 1 }, items: [] };
    const allPending: PendingResponse = {
      count: 3,
      ids: ["a", "b", "c"],
      by_region: { us: 2, eu: 1 },
      items: [
        { conversation_id: "a", region: "us", tenant_name: "ShopBlue", title: "Approvals", last_message_at: null },
        { conversation_id: "b", region: "us", tenant_name: "ShopBlue", title: "Invoices", last_message_at: null },
        { conversation_id: "c", region: "eu", tenant_name: "Hitachi", title: "Suppliers", last_message_at: null },
      ],
    };
    mockFetch.mockImplementation((_region, scope) =>
      Promise.resolve(scope === "feedback" ? feedbackPending : allPending),
    );
    mockTrigger.mockResolvedValue("started");
    render(<AnalyzeNowButton />);

    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(mockFetch).toHaveBeenCalledWith("", "all");
    expect(mockFetch).toHaveBeenCalledWith("", "feedback");
    expect(await screen.findByText(/new \/ unanalyzed conversation/i)).toBeInTheDocument();
    // breakdown: total 3, new feedback 1, normal 2
    expect(screen.getByText("Total 3")).toBeInTheDocument();
    expect(screen.getByText("New feedback 1")).toBeInTheDocument();
    expect(screen.getByText("Normal 2")).toBeInTheDocument();
    expect(screen.getByText("US: 2")).toBeInTheDocument();
    expect(screen.getByText("Approvals")).toBeInTheDocument();
    const start = await screen.findByRole("button", { name: /start analysis/i });

    await userEvent.click(start);
    expect(mockTrigger).toHaveBeenCalledWith("", "all");
    expect(await screen.findByText(/analysis started/i)).toBeInTheDocument();
  });

  it("UIT: offers no Start button when there is nothing new to analyse", async () => {
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

  it("PROD: shows feedback + all sections with separate buttons; feedback button sweeps feedback only", async () => {
    mockEnv = "prod";
    mockFetch.mockImplementation((_region, scope) =>
      Promise.resolve(
        scope === "feedback"
          ? { count: 5, ids: [], by_region: { us: 5 }, items: [] }
          : { count: 20, ids: [], by_region: { us: 20 }, items: [] },
      ),
    );
    mockTrigger.mockResolvedValue("started");
    render(<AnalyzeNowButton />);

    await userEvent.click(screen.getByRole("button", { name: /^analyze$/i }));
    // both scopes fetched
    expect(mockFetch).toHaveBeenCalledWith("", "feedback");
    expect(mockFetch).toHaveBeenCalledWith("", "all");
    // two sections + warning on "all"
    expect(await screen.findByText(/with user feedback are not analyzed/i)).toBeInTheDocument();
    expect(screen.getByText(/analyzes/i)).toBeInTheDocument(); // warning text
    const feedbackBtn = screen.getByRole("button", { name: /analyze feedback/i });
    expect(screen.getByRole("button", { name: /analyze all/i })).toBeInTheDocument();

    await userEvent.click(feedbackBtn);
    expect(mockTrigger).toHaveBeenCalledWith("", "feedback");
    expect(await screen.findByText(/analysis started/i)).toBeInTheDocument();
  });
});
