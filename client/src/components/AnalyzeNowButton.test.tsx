import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { triggerSweep } from "../services/analysisApi";
import { AnalyzeNowButton } from "./AnalyzeNowButton";

jest.mock("../services/analysisApi", () => ({ triggerSweep: jest.fn() }));
const mockTrigger = triggerSweep as jest.MockedFunction<typeof triggerSweep>;

describe("AnalyzeNowButton", () => {
  beforeEach(() => mockTrigger.mockReset());

  it("triggers a background sweep and confirms it started", async () => {
    mockTrigger.mockResolvedValue("started");
    render(<AnalyzeNowButton />);
    await userEvent.click(screen.getByRole("button", { name: /analyze now/i }));
    expect(mockTrigger).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/analysis started/i)).toBeInTheDocument();
  });

  it("tells the user when a sweep is already running", async () => {
    mockTrigger.mockResolvedValue("already_running");
    render(<AnalyzeNowButton />);
    await userEvent.click(screen.getByRole("button", { name: /analyze now/i }));
    expect(await screen.findByText(/already running/i)).toBeInTheDocument();
  });

  it("shows an error when the trigger fails", async () => {
    mockTrigger.mockRejectedValue(new Error("network"));
    render(<AnalyzeNowButton />);
    await userEvent.click(screen.getByRole("button", { name: /analyze now/i }));
    expect(await screen.findByText(/couldn't start analysis/i)).toBeInTheDocument();
  });
});
