import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DownloadFeedbackButton } from "./DownloadFeedbackButton";

describe("DownloadFeedbackButton", () => {
  it("offers CSV/PDF/JSON and downloads with the current filters", async () => {
    const hrefs: string[] = [];
    const spy = jest
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        hrefs.push(this.href);
      });

    render(<DownloadFeedbackButton region="us" scope="thumbs" rating="negative" category="failed_to_resolve" />);
    await userEvent.click(screen.getByRole("button", { name: /download/i }));

    expect(screen.getByRole("menuitem", { name: /CSV/i })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /PDF/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("menuitem", { name: /JSON/i }));

    expect(hrefs).toHaveLength(1);
    const url = new URL(hrefs[0]);
    expect(url.pathname).toContain("/api/analysis/feedback/export");
    expect(url.searchParams.get("format")).toBe("json");
    expect(url.searchParams.get("scope")).toBe("thumbs");
    expect(url.searchParams.get("region")).toBe("us");
    expect(url.searchParams.get("rating")).toBe("negative");
    expect(url.searchParams.get("category")).toBe("failed_to_resolve");
    spy.mockRestore();
  });
});
