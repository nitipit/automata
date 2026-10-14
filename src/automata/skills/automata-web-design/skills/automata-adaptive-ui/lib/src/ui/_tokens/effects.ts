import { paletteEntries, type PaletteColor } from "./color.js";

/** Effects are not extra official swatches. Alpha colors derive from an official entry. */
export const colorEffects = {
  clear: { kind: "transparent" },
  shadow: { kind: "alpha", palette: "dark.4", opacity: 0.07 },
  appShadow: { kind: "alpha", palette: "dark.4", opacity: 0.05 },
} as const satisfies Record<string,
  { kind: "transparent" } | { kind: "alpha"; palette: PaletteColor; opacity: number }>;

export type EffectReference = `effect.${keyof typeof colorEffects}`;
export type ColorReference = PaletteColor | EffectReference;

export function resolveColor(reference: ColorReference): string {
  if (!reference.startsWith("effect.")) return paletteEntries[reference as PaletteColor];
  const effect = colorEffects[reference.slice(7) as keyof typeof colorEffects];
  if (effect.kind === "transparent") return "transparent";
  const hex = paletteEntries[effect.palette];
  const rgb = [1, 3, 5].map(offset => Number.parseInt(hex.slice(offset, offset + 2), 16));
  return `rgb(${rgb.join(" ")} / ${effect.opacity})`;
}

export function colorReferenceLabel(reference: ColorReference): string {
  if (!reference.startsWith("effect.")) return `Palette ${reference}`;
  const name = reference.slice(7) as keyof typeof colorEffects;
  const effect = colorEffects[name];
  return effect.kind === "transparent" ? `Effect ${name} (CSS transparent)`
    : `Effect ${name} (${effect.palette} × opacity ${effect.opacity})`;
}
