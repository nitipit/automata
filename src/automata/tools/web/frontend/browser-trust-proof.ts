/** Browser-origin scoped create proof only. Admission and pair tickets never enter this store. */
const DATABASE = "automata-web-chat-browser-trust";
const STORE = "browser";
const KEY = "create-proof";
const PROOF = /^[a-f0-9]{64}$/;

export function browserTrustProof(initialize: boolean): Promise<string | undefined> {
  return new Promise((resolve, reject) => {
    if (!window.isSecureContext || !window.indexedDB) { resolve(undefined); return; }
    const opening = indexedDB.open(DATABASE, 1);
    opening.onblocked = () => reject(new Error("Browser trust storage is blocked"));
    opening.onupgradeneeded = () => {
      if (!initialize) { opening.transaction?.abort(); return; }
      opening.result.createObjectStore(STORE);
    };
    opening.onerror = () => {
      if (!initialize && opening.error?.name === "AbortError") resolve(undefined);
      else reject(opening.error);
    };
    opening.onsuccess = () => {
      const db = opening.result;
      try {
        const tx = db.transaction(STORE, initialize ? "readwrite" : "readonly");
        const store = tx.objectStore(STORE);
        let proof: string | undefined;
        tx.oncomplete = () => { db.close(); resolve(proof); };
        tx.onabort = () => { db.close(); reject(tx.error); };
        const current = store.get(KEY);
        current.onsuccess = () => {
          if (typeof current.result === "string" && PROOF.test(current.result)) {
            proof = current.result;
          } else if (initialize) {
            proof = Array.from(crypto.getRandomValues(new Uint8Array(32)),
              (byte) => byte.toString(16).padStart(2, "0")).join("");
            store.put(proof, KEY);
          }
        };
      } catch (error) { db.close(); reject(error); }
    };
  });
}
