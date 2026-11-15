import type { ResolvedTheme } from "../_theme/index";

export const fieldStyle = `
  display: grid;
  min-width: 0;
  gap: 0.35rem;
  & > label { font-weight: 600; }
  & > input {
    box-sizing: border-box;
    width: 100%;
    min-width: 0;
    min-height: 2.5rem;
    padding: 0.55rem 0.7rem;
    border: 1px solid;
    border-radius: 0.4rem;
    font: inherit;
  }
  & > input:focus-visible { outline: 3px solid; outline-offset: 2px; }
  & > input:disabled { opacity: 0.6; cursor: not-allowed; }
  & > .field-help, & > .field-error { font-size: 0.875em; overflow-wrap: anywhere; }
  & > [hidden] { display: none; }
`;

export function fieldTheme(theme: ResolvedTheme): string {
  const { surface, text, border, mutedText, error, errorBorder, focus } = theme.roles;
  return `color: ${text};
    & > input { color: ${text}; background: ${surface}; border-color: ${border}; }
    & > input[aria-invalid="true"] { border-color: ${errorBorder}; }
    & > input:focus-visible { outline-color: ${focus}; }
    & > .field-help { color: ${mutedText}; }
    & > .field-error { color: ${error}; }`;
}
