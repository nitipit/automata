import '../shared/theme.js';
// Page-local layout; shared semantic tokens live in shared/theme.js.
const style = document.createElement('style');
style.textContent = '.guide-heading { max-width: 68rem; }';
document.head.append(style);
