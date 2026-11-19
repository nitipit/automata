const route = /^\/chat\/sessions\/([A-Za-z0-9_-]{1,256})\/$/;
const credential = /^[A-Za-z0-9_-]{1,256}$/;
const handoff = window as Window & { __automataChatAdmission?: string };
const supplied = handoff.__automataChatAdmission;
delete handoff.__automataChatAdmission;

export const sessionId = route.exec(location.pathname)?.[1];
export const sessionPath = sessionId ? `/chat/sessions/${sessionId}` : undefined;
const credentialKey = sessionId ? `automata.chat.admission.${sessionId}` : undefined;
const draftKey = "automata.chat.draft-transfer";

export function readAdmission() {
  if (!credentialKey) return undefined;
  if (supplied && credential.test(supplied)) {
    try { sessionStorage.setItem(credentialKey, supplied); } catch { /* volatile proof */ }
    return supplied;
  }
  try {
    const saved = sessionStorage.getItem(credentialKey);
    if (saved && credential.test(saved)) return saved;
  } catch { /* storage denied */ }
  return undefined;
}
export function clearAdmission() {
  if (!credentialKey) return;
  try { sessionStorage.removeItem(credentialKey); } catch { /* storage denied */ }
}

export function savedSessionURL(value: unknown, target: string): URL | undefined {
  if (typeof value !== "string") return;
  try {
    const url = new URL(value, location.origin);
    const fragment = new URLSearchParams(url.hash.slice(1));
    const proof = fragment.get("admission");
    if (url.origin === location.origin && !url.username && !url.password && !url.search &&
        route.exec(url.pathname)?.[1] === target && url.pathname === `/chat/sessions/${target}/` &&
        [...fragment].length === 1 && proof && credential.test(proof)) return url;
  } catch { /* invalid response */ }
  return undefined;
}

// Drafts are page-local except for this one-shot handoff when explicitly opening
// another saved session in the same tab. Normal reload is not a new draft store.
export function takeDrafts(): Map<string, string> {
  try {
    const raw = sessionStorage.getItem(draftKey);
    if (!raw) return new Map();
    sessionStorage.removeItem(draftKey);
    const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
    if (!supplied || navigation?.type === "reload") return new Map();
    const carry = JSON.parse(raw);
    if (carry.target === sessionId && Array.isArray(carry.drafts)) {
      return new Map(carry.drafts.filter((entry: unknown): entry is [string, string] =>
        Array.isArray(entry) && entry.length === 2 && typeof entry[0] === "string" && typeof entry[1] === "string"));
    }
  } catch { /* invalid transfer or storage denied */ }
  return new Map();
}
export function carryDrafts(target: string, drafts: Map<string, string>): boolean {
  if (!drafts.size) return true;
  try {
    sessionStorage.setItem(draftKey, JSON.stringify({ target, drafts: [...drafts] }));
    return true;
  } catch { return false; }
}
