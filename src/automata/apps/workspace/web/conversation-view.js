import { Base, tokens } from "/lib/adaptive-ui.js";
import "/modules/conversation/message.js";

export class ConversationView extends Base {
  static {
    this.css = `
      display:block;
      position:absolute;
      z-index:1;
      inset:auto var(--workspace-space-md) var(--workspace-space-md) auto;
      width:min(32rem, calc(100% - var(--workspace-space-md) - var(--workspace-space-md)));
      height:min(28rem, 70%);
      min-height:0;
      overflow:hidden;
      border:1px solid ${tokens.border};
      border-radius:var(--workspace-radius-sm);
      background:${tokens.surface};
      box-shadow:0 12px 36px rgb(24 32 40 / 18%);
      .panel {
        display:flex;
        flex-direction:column;
        width:100%;
        height:100%;
        min-height:0;
      }
      .heading {
        flex:none;
        margin:0;
        padding:var(--workspace-space-md) var(--workspace-space-lg);
        border-bottom:1px solid ${tokens.border};
        color:${tokens.text};
        font-size:1rem;
        font-weight:600;
      }
      .log {
        display:flex;
        flex:1;
        flex-direction:column;
        gap:var(--workspace-space-lg);
        min-height:0;
        overflow:auto;
        padding:var(--workspace-space-lg);
      }
      .message {
        max-width:min(78%, 600px);
        white-space:pre-wrap;
        overflow-wrap:anywhere;
        line-height:1.55;
      }
      .message.user { align-self:flex-end; text-align:right; }
      .speaker {
        display:block;
        margin-bottom:var(--workspace-space-xs);
        color:${tokens.mutedText};
        font-size:.84rem;
        font-weight:600;
      }
      .body { color:${tokens.text}; }
      .empty { margin:0; color:${tokens.mutedText}; font-size:.88rem; }
      @media(max-width:600px) {
        inset:auto var(--workspace-space-sm) var(--workspace-space-sm) var(--workspace-space-sm);
        width:auto;
        height:min(28rem, 70%);
        .log { padding:var(--workspace-space-md); }
        .message { max-width:90%; }
      }
    `;
  }

  constructor() {
    super();
    this.innerHTML = `
      <section class="panel" role="region" aria-label="Conversation">
        <h2 class="heading" tabindex="-1"></h2>
        <div class="log" role="log" aria-label="Conversation messages" aria-live="polite"></div>
      </section>`;
  }

  present(conversation, agentName) {
    const heading = this.querySelector(".heading");
    heading.textContent = `Conversation · ${agentName}`;
    const log = this.querySelector(".log");
    log.replaceChildren();
    for (const message of conversation.messages) {
      const row = document.createElement("wsp-message");
      row.present(message, agentName, conversation.id);
      log.append(row);
    }
    if (!conversation.messages.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "No messages yet.";
      log.append(empty);
    }
    log.scrollTop = log.scrollHeight;
  }

  focusHeading() {
    this.querySelector(".heading")?.focus({ preventScroll: true });
  }
}

ConversationView.define("wsp-conversation");
