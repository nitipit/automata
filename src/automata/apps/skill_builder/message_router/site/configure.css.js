import { ReferencePage } from './components/reference-page.js';

class ConfigurePage extends ReferencePage {
  static {
    this.css = '.guide-heading { max-width: 68rem; }';
  }
}
ConfigurePage.define('message-router-page');
