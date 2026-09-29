import { ReferencePage } from './components/reference-page.js';

class ConnectPage extends ReferencePage {
  static {
    this.css = `
.credential-shapes {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}
.credential-shapes > div { min-width: 0; }
@media (max-width: 760px) {
  .credential-shapes { grid-template-columns: 1fr; }
}
`;
  }
}
ConnectPage.define('message-router-page');
