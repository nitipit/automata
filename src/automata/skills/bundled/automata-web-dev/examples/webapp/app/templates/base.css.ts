import { resolveThemeColors, themeTypography, type ThemeStyleFactory } from "@adaptive/theme";

/** Page-owned typography/chrome only; Button/Card paint stays in the library. */
export const pageThemeStyles: ThemeStyleFactory = (scope, colors) => {
  const legacy = resolveThemeColors("light");
  return `
    ${scope} a { color: ${colors.action}; }
    ${scope} a:focus-visible, ${scope} summary:focus-visible { outline-color: ${colors.focus}; }
    ${scope} .headerbar { color: ${colors.text}; background: ${colors.surface}; border-color: ${colors.border}; }
    ${scope} .headerbar a { color: ${colors.text}; }
    ${scope} .headerbar a:hover { background: ${colors.background}; }
    ${scope} .design-nav, ${scope} .layer, ${scope} .token-row { border-color: ${colors.border}; }
    ${scope} .shell > h1 { font-size: ${themeTypography.heading}; }
    ${scope} .intro, ${scope} .layer, ${scope} .design-nav, ${scope} .app-title {
      font-size: ${themeTypography.body};
    }
    ${scope} .intro, ${scope} .layer small, ${scope} footer, ${scope} .token-row small { color: ${colors.mutedText}; }
    ${scope} .section-title { font-size: clamp(1.25rem, calc(1rem + 0.666667vw), 1.5rem); }
    ${scope} footer { font-size: clamp(0.75rem, calc(0.625rem + 0.333333vw), 0.875rem); }
    ${scope} .legacy-preview { color-scheme: light; background: ${legacy.surface}; color: ${legacy.text}; }
    ${scope} .theme-probe input { font: inherit; color: ${colors.text}; background: ${colors.surface}; border: 1px solid ${colors.border}; }
  `;
};
