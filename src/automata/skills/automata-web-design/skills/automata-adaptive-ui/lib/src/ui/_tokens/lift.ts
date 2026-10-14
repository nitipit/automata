import { paletteEntries } from "./color.js";

const ink = paletteEntries["dark.4"];

/**
 * Visual depth of the rendered silhouette, ready for CSS `filter`.
 * Level 0 adds no filter; 1–5 increase distance and softness, not z-index.
 * Hex alpha approximates 20% at level 1 and 24% at levels 2–5.
 * Transparent containers lift their painted children, not an empty box.
 * Nonzero filters create a stacking context. Compose other filters in caller CSS.
 */
export const lift = {
  0: "none",
  1: `drop-shadow(0 1px 2px ${ink}33)`,
  2: `drop-shadow(0 2px 4px ${ink}3d)`,
  3: `drop-shadow(0 4px 7px ${ink}3d)`,
  4: `drop-shadow(0 8px 12px ${ink}3d)`,
  5: `drop-shadow(0 12px 18px ${ink}3d)`,
} as const;

export type LiftLevel = keyof typeof lift;
