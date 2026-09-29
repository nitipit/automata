import { ReferencePage } from './components/reference-page.js';

class DiscoverPage extends ReferencePage {
  static {
    this.css = '.guide-heading { max-width: 68rem; }';
  }
}
DiscoverPage.define('message-router-page');
