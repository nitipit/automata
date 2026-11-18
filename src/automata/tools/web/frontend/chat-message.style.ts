import type { ResolvedTheme } from "./_theme/index";

export const chatMessageStyle = `
  display: block;
  max-width: 92%;
  padding: .8rem 1rem;
  border-radius: .9rem;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  &[data-speaker="user"] { align-self: flex-end; }
  & > article > .message-body { white-space: normal; }
  &[data-speaker="user"] > article > .message-body { white-space: pre-wrap; }
  & > article > .message-label { display: block; font-size: .72rem; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; margin-bottom: .3rem; }
  & > article > :is(.reply-activity, .reply-outcome) { font-size: .85rem; margin: .5rem 0 0; }
  & > article > .message-ui > .generated-content { min-width: 0; max-width: 100%; margin-top: .7rem; padding: 1rem; border: 1px solid; border-radius: .9rem; overflow-x: auto; overflow-wrap: anywhere; white-space: normal; }
  & > article > .message-ui > .inactive-ui { margin-top: .7rem; font-size: .85rem; }
`;

export function chatMessageThemeStyle({ roles: r }: ResolvedTheme): string {
  return `
    background: ${r.surfaceRaised};
    &[data-speaker="user"] { background: ${r.accentSoft}; }
    & > article > :is(.message-label, .reply-activity, .reply-outcome),
    & > article > .message-ui > .inactive-ui { color: ${r.mutedText}; }
    & > article > .message-ui > .generated-content { border-color: ${r.border}; }
  `;
}
