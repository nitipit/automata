/** No-provider integration fixture: native Pi RPC dialogs, not agent/human proof. */
export default function (pi: any) {
  pi.registerCommand("web-smoke", {
    description: "Exercise native browser dialogs without a model call",
    handler: async (_args: string, ctx: any) => {
      const confirmed = await ctx.ui.confirm("Smoke confirm", "Synthetic integration check");
      const selected = await ctx.ui.select("Smoke select", ["A", "B"]);
      const input = await ctx.ui.input("Smoke input", "Value");
      const edited = await ctx.ui.editor("Smoke editor", "Original");
      ctx.ui.notify(JSON.stringify({ confirmed, selected, input, edited }), "info");
    },
  });
}
