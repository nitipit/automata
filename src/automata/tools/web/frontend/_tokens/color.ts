import { clampGamut, formatHex, toGamut } from "culori";

export const shades = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950] as const;
export type Shade = typeof shades[number];
/** Tuned OKLCH hue/chroma anchors; perceptual hue intervals are not equal. */
export const colorAnchors = {
  red: [25, .22], redOrange: [40, .20], orange: [58, .18],
  yellowOrange: [78, .17], yellow: [98, .17], yellowGreen: [125, .18],
  green: [150, .18], blueGreen: [185, .14], blue: [250, .19],
  blueViolet: [275, .20], violet: [300, .20], redViolet: [330, .21],
  pink: [355, .17], brown: [60, .09], neutral: [155, .012],
} as const;
export type PaletteFamily = keyof typeof colorAnchors;
const lightness = [.98, .95, .90, .83, .73, .63, .53, .43, .34, .25, .17];
const chromaScale = [.12, .25, .45, .65, .85, 1, .95, .80, .65, .45, .30];
const gamut = toGamut("rgb");
const clamp = clampGamut("rgb");
type Ramp = Record<Shade, string>;
/** Every exported palette color is a resolved, opaque sRGB literal. */
export const palette = Object.fromEntries(Object.entries(colorAnchors).map(([family, [h, c]]) => [
  family,
  Object.fromEntries(shades.map((shade, index) => [shade, formatHex(clamp(gamut({
    mode: "oklch", l: lightness[index], c: c * chromaScale[index], h,
  })))])),
])) as Record<PaletteFamily, Ramp> & { neutral: Ramp & { white: string; black: string } };
palette.neutral.white = "#ffffff";
palette.neutral.black = "#000000";

/** Legacy aliases for existing small components; new components use semantic roles. */
export const color = {
  ink: palette.neutral[950], muted: palette.neutral[700],
  surface: palette.neutral.white, canvas: palette.neutral[50], line: palette.neutral[300],
  accent: palette.green[700], accentSoft: palette.green[100], focus: palette.blue[600],
};
