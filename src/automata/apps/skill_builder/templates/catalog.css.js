import { ReferencePage } from './components/reference-page.js';

class CatalogPage extends ReferencePage {
  static { this.css = 'li { margin: 1rem 0; } main { max-width: 70ch; }'; }
}
CatalogPage.define('catalog-page');
