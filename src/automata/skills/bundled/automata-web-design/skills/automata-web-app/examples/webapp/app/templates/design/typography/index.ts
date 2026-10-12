import { Reading } from "./_index/reading.ts";
import { Scale } from "./_index/scale.ts";

/** Register the page-owned specimens without affecting other design pages. */
export function mountTypographyExamples(): void {
  if (!document.querySelector(".typography-page")) return;
  Scale.define("typography-scale");
  Reading.define("typography-reading");
}
