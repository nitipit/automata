/** Non-secret page preference only: an explicit target ID, never auth or a send queue. */
export const validTargetParticipant = (value: unknown): value is string =>
  typeof value === "string" && /^[A-Za-z0-9_-]{1,128}$/.test(value);

export function createTargetPreference({ key, getStorage = () => globalThis.localStorage,
  onState = (_message: string) => {} }: {
  key: string;
  getStorage?: () => Pick<Storage, "getItem" | "setItem">;
  onState?: (message: string) => void;
}) {
  return {
    restore(current: string): string {
      try {
        const stored = getStorage().getItem(key);
        if (stored === null) return current;
        if (!validTargetParticipant(stored)) {
          onState("Saved target preference invalid · current selection retained; select explicitly");
          return current;
        }
        onState(`Restored selected target ${stored} · no connection or message sent`);
        return stored;
      } catch {
        onState("Target preference storage unavailable · current selection retained; select again after restart");
        return current;
      }
    },
    save(target: string): boolean {
      if (!validTargetParticipant(target)) throw new Error("Select a valid target participant ID");
      try {
        getStorage().setItem(key, target);
        onState(`Selected target ${target} saved locally · no credentials stored`);
        return true;
      } catch {
        onState("Target preference not saved · current selection retained; select again after restart");
        return false;
      }
    },
  };
}
