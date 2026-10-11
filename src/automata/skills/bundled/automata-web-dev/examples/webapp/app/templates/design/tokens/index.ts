import { Colour } from "./_index/colour.ts";
import { Spacing } from "./_index/spacing.ts";
import { Corners } from "./_index/corners.ts";
import { Lift } from "./_index/lift.ts";
import { Transparency } from "./_index/transparency.ts";

/** Register the page-local sections; existing composition tags mount on upgrade. */
export function mountTokenExamples(): void {
  if (!document.querySelector(".tokens-specimen")) return;
  Colour.define("tokens-colour");
  Spacing.define("tokens-spacing");
  Corners.define("tokens-corners");
  Lift.define("tokens-lift");
  Transparency.define("tokens-transparency");
}
