import type { ResolvedTheme } from "../_theme/index";

export const markdownStyle = `
  display: block; min-width: 0; max-width: 100%; line-height: 1.65;
  white-space: normal; overflow-wrap: anywhere;
  & > :first-child { margin-top: 0; } & > :last-child { margin-bottom: 0; }
  & p, & ul, & ol, & blockquote, & table, & pre { margin-block: .7rem; }
  & h1, & h2, & h3, & h4, & h5, & h6 { margin-block: 1.2em .5em; line-height: 1.3; font-weight: 700; }
  & h1 { font-size: 1.6em; } & h2 { font-size: 1.35em; } & h3 { font-size: 1.15em; }
  & h4, & h5, & h6 { font-size: 1em; }
  & ul, & ol { padding-inline-start: 1.6em; } & li + li { margin-top: .2rem; }
  & blockquote { padding-inline-start: 1rem; margin-inline: 0; border-inline-start: 3px solid; }
  & a { text-decoration: underline; text-underline-offset: .15em; }
  & a:focus-visible { outline: 2px solid; outline-offset: 2px; }
  & :not(pre) > code { padding: .1em .3em; border-radius: .25rem; font-size: .9em; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; white-space: break-spaces; }
  & table { display: block; max-width: 100%; overflow-x: auto; border-collapse: collapse; }
  & th, & td { padding: .4rem .65rem; border: 1px solid; text-align: start; }
  & hr { margin-block: 1rem; border: 0; border-top: 1px solid; }
  & img { max-width: 100%; height: auto; }
  & ui-codeblock { white-space: normal; }
`;

export function markdownThemeStyle(theme: ResolvedTheme): string {
  const r = theme.roles;
  return `
    color: ${r.text};
    & a { color: ${r.accent}; } & a:focus-visible { outline-color: ${r.focus}; }
    & blockquote { color: ${r.mutedText}; border-color: ${r.border}; }
    & :not(pre) > code { background: ${r.surfaceRaised}; }
    & th, & td, & hr { border-color: ${r.border}; }
    & th { background: ${r.surfaceRaised}; }
  `;
}
