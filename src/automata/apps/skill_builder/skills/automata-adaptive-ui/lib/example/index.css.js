import { tokens } from "/lib/adaptive-ui.js";

// A document stylesheet: full selectors, not a Base component's scoped CSS body.
export const pageStyles = new CSSStyleSheet();
pageStyles.replaceSync(`
  :root {
    color-scheme: light;
    --aui-action: #2456a6;
    --aui-action-hover: #1d4585;
    --aui-focus: #2456a6;
  }

  body {
    margin: 0;
    background: #f1f5f9;
    color: ${tokens.text};
    font-family: system-ui, sans-serif;
    line-height: 1.5;
  }

  .catalog {
    box-sizing: border-box;
    width: min(68rem, 100%);
    margin-inline: auto;
    padding: clamp(1rem, 4vw, 3rem);
  }

  .catalog-heading {
    margin-bottom: 2rem;
  }

  .catalog-heading > img {
    display: block;
    margin-bottom: 1rem;
  }

  .catalog-heading > h1 {
    margin: 0;
    font-size: clamp(1.75rem, 4vw, 2.5rem);
    line-height: 1.2;
  }

  .catalog-heading > p {
    margin: 1rem 0 0;
    color: ${tokens.mutedText};
  }

  .catalog-content {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
    align-items: start;
    gap: 1.5rem;
  }

  .catalog-overview {
    display: grid;
    gap: 1.5rem;
    min-width: 0;
  }

  @media (max-width: 48rem) {
    .catalog-content {
      grid-template-columns: minmax(0, 1fr);
    }
  }
`);
