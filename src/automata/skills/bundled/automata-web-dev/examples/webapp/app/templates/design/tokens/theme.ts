import { themeTokens, resolveThemeColors, type ThemeMode } from "@adaptive/theme";
import { colorReferenceLabel } from "@adaptive/colors";

/** Small Theme palette selections and concrete resolved values, not legacy vars. */
export function mountThemeTokens(mode: ThemeMode): void {
  const host = document.querySelector("#theme-tokens");
  if (!host) return;
  host.replaceChildren();
  const colors = resolveThemeColors(mode);
  for (const [role, entry] of Object.entries(themeTokens[mode])) {
    const row = document.createElement("div");
    row.className = "token-row";
    row.dataset.themeRole = role;
    const heading = document.createElement("strong");
    heading.textContent = `${role} · ${mode}`;
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.setAttribute("aria-hidden", "true");
    swatch.style.backgroundColor = colors[role as keyof typeof colors];
    const relationship = document.createElement("code");
    relationship.textContent = `${colorReferenceLabel(entry)} → Theme.${role}`;
    const alternatives = document.createElement("small");
    const key = role as keyof typeof colors;
    alternatives.textContent = `Light: ${themeTokens.light[key]} · Dark: ${themeTokens.dark[key]}`;
    row.append(heading, swatch, relationship, alternatives);
    host.append(row);
    const resolved = document.createElement("code");
    resolved.className = "theme-resolved";
    resolved.textContent = `Resolved: ${getComputedStyle(swatch).backgroundColor}`;
    row.append(resolved);
  }
}
