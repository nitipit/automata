import { Reading } from "./_index/reading.ts";

/** Register the page-owned specimens without affecting other design pages. */
export function mountTypographyExamples(): void {
  if (!document.querySelector(".typography-page")) return;
  Reading.define("typography-reading");
}
