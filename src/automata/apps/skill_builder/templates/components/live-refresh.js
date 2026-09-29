// Native Engrave SSE reports completed builds; no router or external requests.
const events = new EventSource('/__engrave/watch');
events.addEventListener('change', () => location.reload());
addEventListener('pagehide', () => events.close(), { once: true });
