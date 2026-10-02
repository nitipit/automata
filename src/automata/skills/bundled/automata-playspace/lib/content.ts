// @ts-types="./adaptive-ui.d.ts"
import { Base, Model, defineField } from "./adaptive-ui.js";
import type { JSONValue, ComponentDefinition } from "./types.js";
import { cloneJSON, testModel } from "./contracts.js";

export const textContract = "automata-playspace/lib/content.js: ps-text props {text:string}";
export const jsonContract = "automata-playspace/lib/content.js: ps-json props {value:JSON}";
class TextProps extends Model {}
TextProps.define({ text: defineField({ required: true }).instance("string") });
class JSONProps extends Model {}
JSONProps.define({ value: defineField({ required: true }) });

export class TextComponent extends Base<{ text: string }> {
  static { this.css = "display: block; white-space: pre-wrap; overflow-wrap: anywhere;"; }
  static validateData(value) { return testModel(TextProps, value, textContract, { text: "Literal text required" }); }
  applyData(props) { this.textContent = props.text; }
}
export class JSONComponent extends Base<{ value: JSONValue }> {
  static { this.css = "display: block; white-space: pre-wrap; overflow-wrap: anywhere; font-family: monospace; font-size: .9rem;"; }
  static validateData(value) {
    const props = testModel(JSONProps, value, jsonContract, { value: "Serializable JSON required" });
    return { value: cloneJSON(props.value) };
  }
  applyData(props) { this.textContent = JSON.stringify(props.value, null, 2); }
}
function definition(Component, contract: string, propsExample, description: string): ComponentDefinition {
  return { contract, validate: value => Component.validateData(value), events: {},
    catalog: { description, sources: ["./lib/content.js"], propsExample },
    create(props, context) {
      const element = Component.create({ data: props });
      element.id = context.componentId;
      return { element };
    },
  };
}
export const textDefinition = definition(TextComponent, textContract, { text: "Example literal text" }, "Literal text, never HTML");
export const jsonDefinition = definition(JSONComponent, jsonContract, { value: { example: [null, true, 42] } }, "Inspectable serializable JSON");
