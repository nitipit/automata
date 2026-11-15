import type { ResolvedTheme } from "../_theme/index";

export const statusBadgeStyle = `
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.4rem 0.7rem;
  border: 1px solid;
  border-radius: 999px;
  font: 600 0.8rem/1.2 system-ui, sans-serif;
  &::before {
    content: "";
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
  }
`;

export function statusBadgeTheme({ roles: r }: ResolvedTheme): string {
  return `
    border-color: ${r.border}; background: ${r.accentSoft}; color: ${r.text};
    &::before { background: ${r.accent}; }
    &[data-state="error"] { background: ${r.errorSurface}; border-color: ${r.errorBorder}; color: ${r.error}; }
    &[data-state="error"]::before { background: ${r.error}; }
  `;
}
