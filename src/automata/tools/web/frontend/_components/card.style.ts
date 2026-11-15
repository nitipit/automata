import type { ResolvedTheme } from "../_theme/index";

export const cardStyle = `
  display: block;
  box-sizing: border-box;
  min-width: 0;
  max-width: 100%;
  padding: 1rem;
  border: 1px solid;
  border-radius: 0.75rem;
  overflow-wrap: anywhere;
  & > :first-child { margin-top: 0; }
  & > :last-child { margin-bottom: 0; }
`;

export function cardTheme(theme: ResolvedTheme): string {
  const { surface, text, border } = theme.roles;
  return `background: ${surface}; color: ${text}; border-color: ${border};`;
}
