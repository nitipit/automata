import { Button, Card, Chat } from "/lib/adaptive-ui.js";
import { ExampleNote } from "./_components/example-note.js";
import { pageStyles } from "./index.css.js";

// Document styles are separate from the sheets managed by Base/Adapter.
document.adoptedStyleSheets = [...document.adoptedStyleSheets, pageStyles];

ExampleNote.define("example-note");
Card.define("aui-card");
// Chat composes the catalog Button; register it before Chat.
Button.define("aui-button");
Chat.define("aui-chat");

document.querySelector("#open-reactive").addEventListener("click", () => {
  globalThis.location.assign(
    new URL("./reactive-shadow.html", import.meta.url),
  );
});
