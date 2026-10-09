import { paletteEntries, paletteName, resolveColor,
  lift, radius, spacing, typography, type PaletteColor } from "@adaptive/tokens";

/** Designer-facing specimens; the library primitives remain the source of values. */
export function mountTokenExamples(): void {
  const palette = document.querySelector("#palette-tokens");
  if (!palette) return;
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

  for (const [level, value] of Object.entries(lift)) {
    const surface = element("div", "lift-surface", "Surface");
    surface.style.borderRadius = radius.md;
    surface.style.backgroundColor = paletteEntries["light.1"];
    surface.style.filter = value;

    const shape = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    shape.setAttribute("viewBox", "0 0 100 100");
    shape.setAttribute("aria-hidden", "true");
    shape.classList.add("lift-shape");
    shape.style.filter = value;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M50 4 62 34 95 36 70 58 78 91 50 73 22 91 30 58 5 36 38 34Z");
    path.setAttribute("fill", paletteEntries["blue.2"]);
    shape.append(path);

    for (const [target, sample] of [["#lift-surfaces", surface], ["#lift-shapes", shape]] as const) {
      const stage = element("div", "lift-stage");
      stage.append(sample);
      const specimen = element("div", "lift-specimen");
      specimen.append(stage, element("p", "lift-label", `Lift ${level}`));
      document.querySelector(target)!.append(specimen);
    }
  }

  const stage = element("div", "effect-stage is-clear");
  const checker = paletteEntries["light.3"];
  stage.style.backgroundColor = paletteEntries["light.1"];
  stage.style.backgroundImage = `linear-gradient(45deg, ${checker} 25%, transparent 25%, transparent 75%, ${checker} 75%), linear-gradient(45deg, ${checker} 25%, transparent 25%, transparent 75%, ${checker} 75%)`;
  stage.style.backgroundPosition = "0 0, .5rem .5rem";
  const surface = element("div", "effect-surface", "Let the backdrop through");
  surface.style.borderRadius = radius.md;
  surface.style.backgroundColor = resolveColor("effect.clear");
  stage.append(surface);
  const specimen = element("div");
  specimen.append(stage, materialLabel("clear", "transparent"));
  document.querySelector("#effect-tokens")!.append(specimen);
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
