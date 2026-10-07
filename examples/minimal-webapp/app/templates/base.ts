import { Button } from "@adaptive/button";
import { Card } from "@adaptive/card";
import { Counter } from "./design/components/counter.ts";
import { theme } from "./design/tokens/index.ts";

for (const [name, value] of Object.entries(theme)) {
  document.documentElement.style.setProperty(name, value);
}

// Register catalog components before mounting/upgrading composed components.
Button.define("ui-button");
Card.define("ui-card");
Counter.define("demo-counter");
