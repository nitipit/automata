import { Adapter } from "@devcapsule/adapter";
import { statusBadgeStyle } from "./status-badge.style";

/** Styled light-DOM status; usable inside a document or another shadow root. */
export class StatusBadge extends Adapter {}
StatusBadge.css = statusBadgeStyle;
StatusBadge.define("status-badge");
