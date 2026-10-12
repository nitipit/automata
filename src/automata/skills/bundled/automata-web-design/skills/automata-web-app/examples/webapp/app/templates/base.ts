import { Button } from "@adaptive/button";
import { Card } from "@adaptive/card";
import { Form } from "@adaptive/form";
import { typography } from "@adaptive/tokens";
import { mountComponentExamples } from "./design/components/index.ts";
import { mountTokenExamples } from "./design/tokens/index.ts";
import { mountTypographyExamples } from "./design/typography/index.ts";

// The site owns document typography; primitives remain reusable CSS values.
const typeStyle = document.createElement("style");
typeStyle.textContent = `
  html { font-size: ${typography.rootSize}; }
  body { font-family: ${typography.family}; font-size: ${typography.bodySize}; font-weight: ${typography.weightRegular}; line-height: ${typography.lineHeight}; }
  h1, h2, h3, h4, h5, h6 { font-weight: ${typography.weightMedium}; line-height: ${typography.headingLineHeight}; }
  h1 { font-size: ${typography.h1Size}; }
  h2 { font-size: ${typography.h2Size}; }
  h3 { font-size: ${typography.h3Size}; }
  h4 { font-size: ${typography.h4Size}; }
  h5 { font-size: ${typography.h5Size}; }
  h6 { font-size: ${typography.h6Size}; }
  label, small { font-size: ${typography.labelSize}; }
  strong, b { font-weight: ${typography.weightMedium}; }
`;
document.head.append(typeStyle);

Button.define("ui-button");
Card.define("ui-card");
Form.define("ui-form");
mountTokenExamples();
mountComponentExamples();
mountTypographyExamples();
