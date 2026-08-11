import { render, screen } from "@testing-library/react";
import { CategoryChip } from "./CategoryChip";

describe("CategoryChip", () => {
  it("shows a human label for a known category", () => {
    render(<CategoryChip category="failed_to_resolve" />);
    expect(screen.getByText("Failed to resolve")).toBeInTheDocument();
  });

  it("shows 'Not analysed' when there is no category", () => {
    render(<CategoryChip category={null} />);
    expect(screen.getByText("Not analysed")).toBeInTheDocument();
  });
});
