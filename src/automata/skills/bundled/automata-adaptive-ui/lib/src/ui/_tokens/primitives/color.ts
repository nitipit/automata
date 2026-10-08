/** Official GNOME palette: intended for icons/illustrations; UI use is an app choice. */
export const paletteSource = "https://developer.gnome.org/hig/reference/palette.html";
export const paletteEntries = {
  "blue.1": "#99c1f1", "blue.2": "#62a0ea", "blue.3": "#3584e4", "blue.4": "#1c71d8", "blue.5": "#1a5fb4",
  "green.1": "#8ff0a4", "green.2": "#57e389", "green.3": "#33d17a", "green.4": "#2ec27e", "green.5": "#26a269",
  "yellow.1": "#f9f06b", "yellow.2": "#f8e45c", "yellow.3": "#f6d32d", "yellow.4": "#f5c211", "yellow.5": "#e5a50a",
  "orange.1": "#ffbe6f", "orange.2": "#ffa348", "orange.3": "#ff7800", "orange.4": "#e66100", "orange.5": "#c64600",
  "red.1": "#f66151", "red.2": "#ed333b", "red.3": "#e01b24", "red.4": "#c01c28", "red.5": "#a51d2d",
  "purple.1": "#dc8add", "purple.2": "#c061cb", "purple.3": "#9141ac", "purple.4": "#813d9c", "purple.5": "#613583",
  "brown.1": "#cdab8f", "brown.2": "#b5835a", "brown.3": "#986a44", "brown.4": "#865e3c", "brown.5": "#63452c",
  "light.1": "#ffffff", "light.2": "#f6f5f4", "light.3": "#deddda", "light.4": "#c0bfbc", "light.5": "#9a9996",
  "dark.1": "#77767b", "dark.2": "#5e5c64", "dark.3": "#3d3846", "dark.4": "#241f31", "dark.5": "#000000",
} as const satisfies Record<string, `#${string}`>;

export type PaletteColor = keyof typeof paletteEntries;
export type PaletteFamily = "blue" | "green" | "yellow" | "orange" | "red" | "purple" | "brown" | "light" | "dark";
export type PaletteShade = 1 | 2 | 3 | 4 | 5;

/** Nested view uses only the same canonical family/shade names. Old mixed keys are removed. */
export const palette = Object.fromEntries(
  Object.entries(paletteEntries).reduce((families, [key, value]) => {
    const [family, shade] = key.split(".");
    if (!families.has(family)) families.set(family, {});
    families.get(family)![Number(shade)] = value;
    return families;
  }, new Map<string, Record<number, string>>()),
) as { readonly [Family in PaletteFamily]: { readonly [Shade in PaletteShade]: (typeof paletteEntries)[`${Family}.${Shade}`] } };

export function paletteName(color: PaletteColor): string {
  const [family, shade] = color.split(".");
  return `${family[0].toUpperCase()}${family.slice(1)} ${shade}`;
}
