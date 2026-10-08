import { componentColorRoles, paletteEntries, paletteSource, paletteName,
  colorEffects, resolveColor, colorReferenceLabel, semanticColorRoles, tokens,
  type SemanticColorRole } from "@adaptive/colors";
import { alternateChatPalette, appColorRoles, themePalette } from "./index.ts";

/** One metadata hierarchy supplies every list, relationship and CSS value. */
export function mountTokenExamples(): void {
  const semantic = document.querySelector("#semantic-tokens");
  const overrides = document.querySelector("#app-overrides");
  const primitives = document.querySelector("#palette-tokens");
  const components = document.querySelector("#component-tokens");
  const demo = document.querySelector("#demo-overrides");
  if (!semantic || !overrides || !primitives || !components || !demo) return;

  document.querySelector("#palette-source")?.setAttribute("href", paletteSource);
  for (const [name, value] of Object.entries(paletteEntries)) {
    const row = tokenRow(`${paletteName(name as keyof typeof paletteEntries)} · ${name}`, value);
    row.dataset.palette = name;
    primitives.append(row);
    resolveSwatch(row);
  }
  for (const [role, definition] of Object.entries(semanticColorRoles)) {
    const key = role as SemanticColorRole;
    const row = tokenRow(role, tokens[key]);
    row.dataset.role = role;
    row.dataset.color = definition.color;
    if (!definition.color.startsWith("effect.")) row.dataset.palette = definition.color;
    row.dataset.variable = definition.variable;
    describe(row, definition.description);
    describe(row, `${colorReferenceLabel(definition.color)} → semantic ${role}`);
    const consumers = Object.entries(componentColorRoles).flatMap(([component, roles]) =>
      Object.entries(roles).filter(([, semantic]) => semantic === role)
        .map(([name]) => `${component}.${name}`));
    describe(row, consumers.length ? `Used by: ${consumers.join(", ")}` : "Shared foundation role");
    describe(row, overrideDescription(key));
    semantic.append(row);
    resolveSwatch(row);
  }
  for (const [component, roles] of Object.entries(componentColorRoles)) {
    for (const [name, role] of Object.entries(roles)) {
      const row = tokenRow(`${component}.${name}`, tokens[role]);
      row.dataset.component = component;
      row.dataset.semantic = role;
      row.dataset.color = semanticColorRoles[role].color;
      describe(row, `${colorReferenceLabel(semanticColorRoles[role].color)} → semantic ${role} → ${component}.${name}`);
      describe(row, overrideDescription(role));
      components.append(row);
      resolveSwatch(row);
    }
  }
  for (const [role, palette] of Object.entries(themePalette)) {
    const variable = semanticColorRoles[role as SemanticColorRole].variable;
    const row = tokenRow(variable, paletteEntries[palette]);
    describe(row, `App palette ${palette} → semantic ${role}`);
    overrides.append(row);
    resolveSwatch(row);
  }
  for (const [role, palette] of Object.entries(alternateChatPalette)) {
    const variable = semanticColorRoles[role as SemanticColorRole].variable;
    const row = tokenRow(variable, paletteEntries[palette]);
    describe(row, `Demo palette ${palette} → semantic ${role} (only when toggled locally)`);
    demo.append(row);
    resolveSwatch(row);
  }
  for (const [role, definition] of Object.entries(appColorRoles)) {
    const row = tokenRow(definition.variable, resolveColor(definition.color));
    describe(row, `${colorReferenceLabel(definition.color)} → app ${role} (not a library role)`);
    overrides.append(row);
    resolveSwatch(row);
  }
  const effects = document.querySelector("#color-effects");
  for (const name of Object.keys(colorEffects) as (keyof typeof colorEffects)[]) {
    const reference = `effect.${name}` as const;
    const row = tokenRow(name, resolveColor(reference));
    describe(row, colorReferenceLabel(reference));
    effects?.append(row);
    resolveSwatch(row);
  }
}

function overrideDescription(role: SemanticColorRole): string {
  const selected = (themePalette as Partial<Record<SemanticColorRole, keyof typeof paletteEntries>>)[role];
  return selected ? `App override: ${selected} (${paletteEntries[selected]})`
    : "App override: none (library fallback)";
}

function describe(row: HTMLElement, text: string): void {
  const description = document.createElement("small");
  description.textContent = text;
  row.append(description);
}

function resolveSwatch(row: HTMLElement): void {
  const resolved = document.createElement("code");
  resolved.className = "resolved";
  resolved.textContent = `Resolved: ${getComputedStyle(row.querySelector(".swatch")!).backgroundColor}`;
  row.append(resolved);
}

function tokenRow(name: string, value: string): HTMLElement {
  const row = document.createElement("div");
  row.className = "token-row";
  const heading = document.createElement("div");
  heading.className = "token-heading";
  const swatch = document.createElement("span");
  swatch.className = "swatch";
  swatch.setAttribute("aria-hidden", "true");
  swatch.style.backgroundColor = value;
  const label = document.createElement("strong");
  label.textContent = name;
  heading.append(swatch, label);
  const definition = document.createElement("code");
  definition.textContent = value;
  row.append(heading, definition);
  return row;
}
