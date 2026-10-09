import { paletteEntries, paletteName, paletteSource, colorEffects, resolveColor,
  radius, spacing, typography, type PaletteColor } from "@adaptive/tokens";

/** Designer-facing specimens; the library primitives remain the source of values. */
export function mountTokenExamples(): void {
  const palette = document.querySelector("#palette-tokens");
  if (!palette) return;
  document.querySelector("#palette-source")?.setAttribute("href", paletteSource);
  const families = new Map<string, HTMLElement>();
  for (const [key, value] of Object.entries(paletteEntries)) {
    const name = paletteName(key as PaletteColor);
    const family = name.split(" ")[0];
    if (!families.has(family)) {
      const section = element("section", "palette-family");
      const grid = element("div", "palette-grid");
      section.append(element("h3", "", family), grid);
      palette.append(section);
      families.set(family, grid);
    }
    const swatch = element("div", "swatch");
    swatch.style.backgroundColor = value;
    const label = element("div", "swatch-label");
    label.append(element("span", "", name), element("code", "", value));
    const chip = element("div", "palette-chip");
    chip.title = key;
    chip.append(swatch, label);
    families.get(family)!.append(chip);
  }

  const type = document.querySelector<HTMLElement>("#typography-specimen")!;
  type.style.fontFamily = typography.family;
  type.style.lineHeight = typography.lineHeight;
  for (const sample of type.querySelectorAll<HTMLElement>(".type-heading, .type-label")) {
    sample.style.fontWeight = typography.weightMedium;
  }
  const typeValues = document.querySelector("#typography-values")!;
  for (const value of [typography.family, `Line height ${typography.lineHeight}`,
    `Weight ${typography.weightMedium}`, "Heading 2rem · Body 1rem · Label .85rem"]) {
    typeValues.append(element("span", "", value));
  }

  for (const [name, value] of Object.entries(spacing)) {
    const stage = element("div", "space-stage");
    stage.style.padding = value;
    const stack = element("div", "space-stack");
    stack.style.gap = value;
    stack.append(element("p", "space-title", "Daily notes"),
      element("p", "space-body", "A little room between the essentials."),
      element("p", "space-caption", "Today · Three entries"));
    stage.append(stack);
    const specimen = element("div");
    specimen.append(stage, materialLabel(name, value));
    document.querySelector("#spacing-tokens")!.append(specimen);
  }

  for (const [name, value] of Object.entries(radius)) {
    const surface = element("div", "radius-surface");
    surface.style.borderRadius = value;
    surface.style.padding = spacing.lg;
    surface.style.backgroundColor = paletteEntries["blue.1"];
    surface.append(element("strong", "", "Rounded edges"),
      element("p", "", "A clear boundary, with a little softness."));
    const label = materialLabel(name, value);
    label.classList.add("radius-caption");
    document.querySelector("#radius-tokens")!.append(surface, label);
  }

  for (const name of Object.keys(colorEffects) as (keyof typeof colorEffects)[]) {
    const effect = colorEffects[name];
    const value = resolveColor(`effect.${name}`);
    const stage = element("div", "effect-stage");
    const surface = element("div", "effect-surface");
    surface.style.borderRadius = radius.md;
    let caption: string;
    if (effect.kind === "transparent") {
      stage.classList.add("is-clear");
      const checker = paletteEntries["light.3"];
      stage.style.backgroundColor = paletteEntries["light.1"];
      stage.style.backgroundImage = `linear-gradient(45deg, ${checker} 25%, transparent 25%, transparent 75%, ${checker} 75%), linear-gradient(45deg, ${checker} 25%, transparent 25%, transparent 75%, ${checker} 75%)`;
      stage.style.backgroundPosition = "0 0, .5rem .5rem";
      surface.style.backgroundColor = value;
      surface.textContent = "Let the backdrop through";
      caption = value;
    } else {
      stage.style.backgroundColor = paletteEntries["light.2"];
      surface.style.backgroundColor = paletteEntries["light.1"];
      surface.style.boxShadow = `0 4px 12px ${value}`;
      surface.textContent = "A raised surface";
      caption = `${effect.opacity * 100}% alpha`;
    }
    stage.append(surface);
    const specimen = element("div");
    specimen.append(stage, materialLabel(name, caption));
    document.querySelector("#effect-tokens")!.append(specimen);
  }
}

function materialLabel(name: string, value: string): HTMLElement {
  const label = element("div", "material-label");
  label.append(element("span", "", name), element("code", "", value));
  return label;
}

function element(tag: string, className = "", text = ""): HTMLElement {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}
