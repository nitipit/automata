const choices = new Set(["light", "dark", "system"]);
const preferenceKey = "anatomy-theme";
let preference = "system";
let resolved = null;
let appliedPreference = null;
let initialized = false;
let colorSchemeQuery;

function systemTheme() {
  return colorSchemeQuery?.matches ? "dark" : "light";
}

function applyTheme() {
  const nextResolved = preference === "system" ? systemTheme() : preference;
  const changed = resolved !== nextResolved || appliedPreference !== preference;
  resolved = nextResolved;
  appliedPreference = preference;
  document.documentElement.dataset.theme = resolved;

  if (changed) {
    document.dispatchEvent(new CustomEvent("anatomy-theme-change", {
      detail: { preference, resolved },
    }));
  }
}

/** Restore the saved choice once, apply it, and keep system mode in sync. */
export function initializeTheme() {
  if (!initialized) {
    try {
      const saved = localStorage.getItem(preferenceKey);
      if (choices.has(saved)) preference = saved;
    } catch {
      // Storage can be disabled; system mode remains a usable default.
    }

    if (typeof window.matchMedia === "function") {
      colorSchemeQuery = window.matchMedia("(prefers-color-scheme: dark)");
    }
    colorSchemeQuery?.addEventListener?.("change", handleSystemChange);
    // Older Safari exposes addListener instead of EventTarget methods.
    if (colorSchemeQuery && !colorSchemeQuery.addEventListener) {
      colorSchemeQuery.addListener(handleSystemChange);
    }
    initialized = true;
  }

  applyTheme();
  return preference;
}

function handleSystemChange() {
  if (preference === "system") applyTheme();
}

/** Set a validated preference and persist it when browser storage permits. */
export function setTheme(nextPreference) {
  if (!choices.has(nextPreference)) {
    throw new RangeError("Theme must be 'light', 'dark', or 'system'");
  }

  initializeTheme();
  try {
    localStorage.setItem(preferenceKey, nextPreference);
  } catch {
    // Apply in-memory even when persistence is unavailable.
  }
  if (preference === nextPreference) return;

  preference = nextPreference;
  applyTheme();
}

export function getTheme() {
  if (!initialized) initializeTheme();
  return { preference, resolved };
}
