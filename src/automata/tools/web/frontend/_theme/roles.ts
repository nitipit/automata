import { palette, type PaletteFamily } from "../_tokens/color";

export type ThemeMode = "light" | "dark";
export type SemanticRoles = {
  canvas: string; surface: string; surfaceRaised: string;
  text: string; mutedText: string; border: string;
  accent: string; accentText: string; accentSoft: string; focus: string;
  error: string; errorSurface: string; errorBorder: string;
  success: string; successSurface: string; successBorder: string;
  warning: string; warningSurface: string; warningBorder: string;
  info: string; infoSurface: string; infoBorder: string;
};
export type ResolvedTheme = { mode: ThemeMode; accent: PaletteFamily; roles: SemanticRoles };
export type ThemeOverrides = {
  mode?: ThemeMode | "system";
  accent?: PaletteFamily;
  roles?: Partial<SemanticRoles>;
};

/** Coordinated text/surface/border roles. Contrast applies to role pairs, not arbitrary shades. */
export function semanticRoles(mode: ThemeMode, accent: PaletteFamily): SemanticRoles {
  const p = palette, dark = mode === "dark";
  const status = (family: PaletteFamily) => ({
    text: p[family][dark ? 200 : 800],
    surface: p[family][dark ? 950 : 50],
    border: p[family][dark ? 500 : 600],
  });
  const error = status("red"), success = status("green"), warning = status("yellowOrange"), info = status("blue");
  return {
    canvas: p.neutral[dark ? 950 : 50], surface: dark ? p.neutral[900] : p.neutral.white,
    surfaceRaised: p.neutral[dark ? 800 : 100],
    text: p.neutral[dark ? 50 : 950], mutedText: p.neutral[dark ? 300 : 700],
    border: p.neutral[dark ? 500 : 500],
    accent: p[accent][dark ? 300 : 700], accentText: dark ? p.neutral[950] : p.neutral.white,
    accentSoft: p[accent][dark ? 950 : 100], focus: p.blue[dark ? 300 : 600],
    error: error.text, errorSurface: error.surface, errorBorder: error.border,
    success: success.text, successSurface: success.surface, successBorder: success.border,
    warning: warning.text, warningSurface: warning.surface, warningBorder: warning.border,
    info: info.text, infoSurface: info.surface, infoBorder: info.border,
  };
}
