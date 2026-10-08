import { Button } from "@adaptive/button";
import { Card } from "@adaptive/card";
import { Form } from "@adaptive/form";
import { Chat } from "@adaptive/chat";
import { mountComponentExamples } from "./design/components/index.ts";
import { mountTokenExamples } from "./design/tokens/page.ts";
import { Counter } from "./design/components/counter.ts";
import { theme } from "./design/tokens/index.ts";
import { Theme, buttonThemeStyles, cardThemeStyles } from "@adaptive/theme";
import { pageThemeStyles } from "./base.css.ts";
import { mountThemeTokens } from "./design/tokens/theme.ts";

for (const [name, value] of Object.entries(theme)) {
  document.documentElement.style.setProperty(name, value);
}

// Register catalog components before mounting/upgrading composed components.
Button.define("ui-button");
Card.define("ui-card");
Counter.define("demo-counter");
// Chat composes the catalog's canonical aui-button tag; retain the app alias.
class ChatButton extends Button {}
ChatButton.define("aui-button");
Form.define("ui-form");
Chat.define("ui-chat");
Theme.define("ui-theme");
const applicationTheme = document.querySelector<Theme>("#application-theme")!;
applicationTheme.setStyleFactories([
  (scope, colors) => buttonThemeStyles(scope, colors, "ui-button"),
  (scope, colors) => cardThemeStyles(scope, colors, "ui-card"),
  pageThemeStyles,
]);
const toggle = document.querySelector("#theme-toggle")!;
toggle.addEventListener("click", () => {
  applicationTheme.mode = applicationTheme.mode === "light" ? "dark" : "light";
  toggle.setAttribute("label", applicationTheme.mode === "light" ? "Use dark theme" : "Use light theme");
  mountThemeTokens(applicationTheme.mode);
});
mountTokenExamples();
mountThemeTokens(applicationTheme.mode);
mountComponentExamples();
