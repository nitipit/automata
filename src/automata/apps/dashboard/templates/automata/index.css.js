import '../shared/theme.js';
const style = document.createElement('style');
style.textContent = `
.destination-heading {display:flex; align-items:center; justify-content:space-between; gap:1rem; flex-wrap:wrap; margin-top:2rem;}
.destination-heading h1 {margin-bottom:.65rem;}
`;
document.head.append(style);
