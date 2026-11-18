// Private Web Chat bridge over Pi's documented session_start + RPC setStatus.
// A standalone extension keeps this signal independent of user extensions and UI tools.
export default function (pi) {
  const key = process.env.AUTOMATA_WEB_MODEL_SCOPE_KEY;
  if (!key) return;
  pi.on("session_start", (_event, ctx) => {
    const scope = ctx.scopedModels;
    const text = Array.isArray(scope) && scope.length <= 512
      ? JSON.stringify(scope.map(({ model, thinkingLevel }) => ({
          provider: model.provider, id: model.id, name: model.name, thinkingLevel,
        })))
      : "null";
    ctx.ui.setStatus(key, Buffer.byteLength(text) <= 128 * 1024 ? text : "null");
  });
}
