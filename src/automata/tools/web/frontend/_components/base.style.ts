/** Component-local root defaults inherited through Adapter class CSS. No page reset. */
export const baseStyle = `
  box-sizing: border-box;
  min-width: 0;
  font: inherit;
  line-height: 1.5;
  & *, & *::before, & *::after { box-sizing: border-box; }
`;
