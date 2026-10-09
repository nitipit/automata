import { paletteEntries, paletteName, paletteSource, colorEffects, resolveColor,
  radius, spacing, typography, type PaletteColor } from "@adaptive/tokens";

/** Visual samples of the current primitives, not a model of component appearance. */
export function mountTokenExamples(): void {
  const palette = document.querySelector("#palette-tokens");
  if (!palette) return;
  document.querySelector("#palette-source")?.setAttribute("href", paletteSource);
  const families = new Map<string, HTMLElement>();
  for (const [key, value] of Object.entries(paletteEntries)) {
    const name = paletteName(key as PaletteColor);
    const family = name.split(" ")[0];
    if (!families.has(family)) {
      const section = document.createElement("section");
      section.className = "palette-family";
      const heading = document.createElement("h3");
      heading.textContent = family;
      const grid = document.createElement("div");
      grid.className = "palette-grid";
      section.append(heading, grid);
      palette.append(section);
      families.set(family, grid);
    }
    const swatch = document.createElement("div");
    swatch.className = "swatch";
    swatch.style.backgroundColor = value;
    const tile = sample(name, value, swatch);
    tile.title = key;
    families.get(family)!.append(tile);
  }
  for (const name of Object.keys(colorEffects) as (keyof typeof colorEffects)[]) {
    const value = resolveColor(`effect.${name}`);
    const specimen = document.createElement("div");
    specimen.className = "effect-sample";
    if (colorEffects[name].kind === "transparent") specimen.style.backgroundColor = value;
    else specimen.style.boxShadow = `0 4px 12px ${value}`;
    appendPhysical("effect", name, value, specimen);
  }
  for (const [name, value] of Object.entries(radius)) {
    const specimen = document.createElement("div");
    specimen.className = "radius-sample";
    specimen.style.borderRadius = value;
    appendPhysical("radius", name, value, specimen);
  }
  for (const [name, value] of Object.entries(spacing)) {
    const specimen = document.createElement("div");
    specimen.className = "spacing-sample";
    specimen.style.width = value;
    appendPhysical("spacing", name, value, specimen);
  }
  for (const [name, value] of Object.entries(typography)) {
    const specimen = document.createElement("span");
    specimen.textContent = name === "lineHeight" ? "Aa\nBb" : "Aa";
    specimen.style.whiteSpace = "pre-line";
    if (name === "family") specimen.style.fontFamily = value;
    if (name === "lineHeight") specimen.style.lineHeight = value;
    if (name === "weightMedium") specimen.style.fontWeight = value;
    appendPhysical("typography", name, value, specimen);
  }
}

function appendPhysical(group: string, name: string, value: string, specimen: HTMLElement): void {
  const canvas = document.createElement("div");
  canvas.className = "physical-sample";
  canvas.append(specimen);
  document.querySelector(`#${group}-tokens`)!.append(sample(name, value, canvas));
}

function sample(name: string, value: string, specimen: HTMLElement): HTMLElement {
  const tile = document.createElement("div");
  tile.className = "token-sample";
  const label = document.createElement("strong");
  label.textContent = name;
  const code = document.createElement("code");
  code.textContent = value;
  tile.append(specimen, label, code);
  return tile;
}
