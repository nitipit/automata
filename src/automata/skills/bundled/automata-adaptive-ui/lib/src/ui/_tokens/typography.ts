/** Typography characteristics shared by the component baseline. */
export const typography = {
  family: "system-ui, sans-serif",
  lineHeight: "1.5",
  weightMedium: "600",
  // Linear viewport sizing from 600px to 1200px, clamped outside that range.
  // Body slope: (17 - 15) / 600; heading slope: (40 - 28) / 600.
  bodySize: "clamp(15px, calc(13px + 0.3333333333vw), 17px)",
  headingSize: "clamp(28px, calc(16px + 2vw), 40px)",
  // Place labels directly inside a body-sized parent to avoid compounded scaling.
  labelSize: ".85em",
} as const;
