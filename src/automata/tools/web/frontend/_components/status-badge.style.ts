import { color } from "../_tokens/color";

export const statusBadgeStyle = `
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.4rem 0.7rem;
  border: 1px solid ${color.line};
  border-radius: 999px;
  background: ${color.accentSoft};
  color: ${color.ink};
  font: 600 0.8rem/1.2 system-ui, sans-serif;
  &[data-state="error"] { background: #fff0eb; border-color: #f1c5b6; }
  &[data-state="error"]::before { background: #ad3b21; }
  &::before {
    content: "";
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: ${color.accent};
  }
`;
