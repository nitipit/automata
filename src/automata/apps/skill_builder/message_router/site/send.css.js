import { ReferencePage } from './components/reference-page.js';

class SendPage extends ReferencePage {
  static {
    this.css = '.guide-heading { max-width: 68rem; }';
  }
}
SendPage.define('message-router-page');
