// Minimal public component contracts for the separately built Adaptive UI bundle.
declare module "@adaptive-ui" {
  export class Base extends HTMLElement {
    static css: string;
    static define(tagName: string): void;
    connectedCallback(): void;
    disconnectedCallback(): void;
  }
  export class Button extends Base {}
  export class Card extends Base {}
}
