import { Colour } from "./index.components/colour.ts";
import { Typography } from "./index.components/typography.ts";
import { Spacing } from "./index.components/spacing.ts";
import { Corners } from "./index.components/corners.ts";
import { Lift } from "./index.components/lift.ts";
import { Transparency } from "./index.components/transparency.ts";

/** Register the page-local sections; existing composition tags mount on upgrade. */
export function mountTokenExamples(): void {
  if (!document.querySelector(".tokens-specimen")) return;
  Colour.define("tokens-colour");
  Typography.define("tokens-typography");
  Spacing.define("tokens-spacing");
  Corners.define("tokens-corners");
  Lift.define("tokens-lift");
  Transparency.define("tokens-transparency");
}
