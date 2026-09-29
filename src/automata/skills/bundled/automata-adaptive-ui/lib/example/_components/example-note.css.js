import { tokens } from "/lib/adaptive-ui.js";

// Base/Adapter scopes these declarations and nested selectors to the component.
export const noteCss = `
  display: block;
  overflow-wrap: anywhere;

  h2 {
    margin: 0;
    font-size: 1.125rem;
    line-height: 1.4;
  }

  p {
    margin: .5rem 0 0;
    color: ${tokens.mutedText};
  }
`;
