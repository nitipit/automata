/** A proportional type scale rooted in the document's fluid font size. */
export const typography = {
  family: "system-ui, sans-serif",
  // Linear growth from 15px at 600px to 17px at 1200px; fixed outside that range.
  rootSize: "clamp(15px, calc(13px + 0.3333333333vw), 17px)",
  bodySize: "1rem",
  h1Size: "2.25rem",
  h2Size: "1.875rem",
  h3Size: "1.5rem",
  h4Size: "1.25rem",
  h5Size: "1.125rem",
  h6Size: "1rem",
  labelSize: ".85rem",
  lineHeight: "1.5",
  headingLineHeight: "1.25",
  weightRegular: "400",
  weightMedium: "600",
} as const;
