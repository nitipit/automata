import { Button, Card, Form } from "/lib/adaptive-ui.js";
import { ExampleNote } from "./_components/example-note.js";
import { pageStyles } from "./index.css.js";

// Document styles are separate from the sheets managed by Base/Adapter.
document.adoptedStyleSheets = [...document.adoptedStyleSheets, pageStyles];

ExampleNote.define("example-note");
Card.define("aui-card");
Button.define("aui-button");
Form.define("aui-form");

document.querySelector("#open-reactive").addEventListener("click", () => {
  globalThis.location.assign(
    new URL("./reactive-shadow.html", import.meta.url),
  );
});
