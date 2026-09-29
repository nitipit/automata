import { ReferencePage } from './components/reference-page.js';

class FailuresPage extends ReferencePage {
  static {
    this.css = '.guide-heading { max-width: 68rem; }';
  }
}
FailuresPage.define('message-router-page');
