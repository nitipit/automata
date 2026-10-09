import { Button } from "@adaptive/button";
import { Card } from "@adaptive/card";
import { Form } from "@adaptive/form";
import { mountComponentExamples } from "./design/components/index.ts";
import { mountTokenExamples } from "./design/tokens/index.ts";

Button.define("ui-button");
Card.define("ui-card");
Form.define("ui-form");
mountTokenExamples();
mountComponentExamples();
