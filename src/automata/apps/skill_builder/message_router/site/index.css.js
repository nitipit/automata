import { ReferencePage } from './components/reference-page.js';

class IndexPage extends ReferencePage {
  static {
    this.css = '.lesson > p { max-width: 65rem; }';
  }
}
IndexPage.define('message-router-page');
