import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InsightsPage from "../../app/insights/page";
import type { GroupsResponse } from "../services/analysisApi";

const mockFetchGroups = jest.fn();

jest.mock("../services/analysisApi", () => ({
  ...jest.requireActual("../services/analysisApi"),
  fetchGroups: (...args: unknown[]) => mockFetchGroups(...args),
}));

jest.mock("./RegionContext", () => ({
  useRegion: () => ({ region: "us", loading: false }),
}));

const response: GroupsResponse = {
  items: [
    { root_cause: "knowledge_gap", label: "Knowledge gap (right document not retrieved)", knowledge_gap: true, conversations: 40, tenants: 3, users: 25, sample_conversation_ids: ["a"], example_next_step: "Add the **Services form** guidance" },
    { root_cause: "wrong_routing", label: "Wrong routing / out of scope", knowledge_gap: false, conversations: 5, tenants: 1, users: 4, sample_conversation_ids: ["b"], example_next_step: "" },
  ],
  total: 2,
  scope: "issues",
};

describe("InsightsPage", () => {
  beforeEach(() => {
    mockFetchGroups.mockReset();
    mockFetchGroups.mockResolvedValue(response);
  });

  it("shows impact-ranked root-cause groups, counts, a knowledge-gap flag, and a drill-in link", async () => {
    render(<InsightsPage />);
    expect(await screen.findByText("Knowledge gap (right document not retrieved)")).toBeInTheDocument();
    expect(screen.getByText("40")).toBeInTheDocument(); // conversations impact
    expect(screen.getByText("Knowledge gap")).toBeInTheDocument(); // the flag chip
    expect(screen.getByText("Services form").tagName).toBe("STRONG"); // markdown suggested fix
    const review = screen.getAllByRole("link", { name: /Open .* conversations/i })[0];
    expect(review).toHaveAttribute("href", expect.stringContaining("root_cause=knowledge_gap"));
  });

  it("switches the scope to all analysed conversations", async () => {
    render(<InsightsPage />);
    await screen.findByText("Knowledge gap (right document not retrieved)");
    await userEvent.click(screen.getByLabelText("Scope"));
    await userEvent.click(await screen.findByRole("option", { name: /All analysed/ }));
    await waitFor(() => expect(mockFetchGroups).toHaveBeenLastCalledWith(expect.objectContaining({ scope: "all" })));
  });
});
