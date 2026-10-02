// One app-owned source watcher emits changes; requests always read canonical files.
const events = new EventSource('/__skill_builder/events');
events.addEventListener('change', () => location.reload());
addEventListener('pagehide', () => events.close(), { once: true });
