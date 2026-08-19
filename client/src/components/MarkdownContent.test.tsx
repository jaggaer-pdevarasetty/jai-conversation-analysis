import { render, screen } from "@testing-library/react";
import { MarkdownContent } from "./MarkdownContent";

describe("MarkdownContent HTML handling", () => {
  it("keeps ordinary content that merely looks like tags", () => {
    render(<MarkdownContent>{"Use the placeholder <tenant-id> when configuring."}</MarkdownContent>);
    expect(screen.getByText(/<tenant-id>/)).toBeInTheDocument();
  });

  it("does not eat comparison expressions", () => {
    render(<MarkdownContent>{"Set it if x < 5 and y > 3 today."}</MarkdownContent>);
    expect(screen.getByText(/x < 5 and y > 3/)).toBeInTheDocument();
  });

  it("preserves angle-bracket content inside code spans", () => {
    render(<MarkdownContent>{"Wrap it in `<div>` before saving."}</MarkdownContent>);
    expect(screen.getByText("<div>")).toBeInTheDocument();
  });

  it("renders HTML as safe escaped text without deleting content", () => {
    render(<MarkdownContent>{'See <a href="http://x">the guide</a> in <div>this box</div>.'}</MarkdownContent>);
    // React escapes text nodes, so raw HTML is shown literally (safe) and nothing is deleted
    expect(screen.getByText(/the guide/)).toBeInTheDocument();
    expect(screen.getByText(/this box/)).toBeInTheDocument();
  });

  it("renders redacted tables whose rows have missing cells", () => {
    render(
      <MarkdownContent>{'| Invoice | Status | Amount |\n| --- | --- | ---: |\n| <a href="https://example.test">3917582</a> | Paid |\n| 3917583 | Payable | 100.00 |'}</MarkdownContent>,
    );
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(3);
    expect(screen.getByText("3917582")).toBeInTheDocument();
    expect(screen.queryByText(/<a href/)).not.toBeInTheDocument();
  });
});
