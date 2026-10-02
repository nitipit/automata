/** Textarea layout only. CSS owns the 30vh cap; value and keyboard behavior stay native. */
export function createComposerSizing(textarea: HTMLTextAreaElement, form: HTMLFormElement,
  onReset: () => void) {
  let disposed = false, mounted = false, width: number | undefined;
  let observer: ResizeObserver | undefined;
  function resize() {
    if (disposed || !textarea.isConnected) return;
    // Reset first so deletion and restored shorter drafts shrink as well as grow.
    textarea.style.height = "auto";
    const style = getComputedStyle(textarea);
    const border = (parseFloat(style.borderTopWidth) || 0) + (parseFloat(style.borderBottomWidth) || 0);
    textarea.style.height = `${textarea.scrollHeight + border}px`;
  }
  function reset(event: Event) {
    // The reset event runs before native values reset. Do not outlive disposal.
    queueMicrotask(() => {
      if (disposed || event.defaultPrevented) return;
      resize();
      onReset();
    });
  }
  return {
    resize,
    mount() {
      if (disposed) return;
      if (!mounted) {
        mounted = true;
        textarea.addEventListener("input", resize);
        form.addEventListener("reset", reset);
        globalThis.addEventListener("resize", resize);
        observer = new ResizeObserver(entries => {
          const nextWidth = entries[0]?.contentRect.width;
          // Ignore our own height-only changes: no observer/measurement loop.
          if (nextWidth !== undefined && nextWidth !== width) { width = nextWidth; resize(); }
        });
        observer.observe(textarea);
      }
      resize(); // Includes restore-before-mount and later DOM movement.
    },
    dispose() {
      disposed = true;
      observer?.disconnect();
      textarea.removeEventListener("input", resize);
      form.removeEventListener("reset", reset);
      if (mounted) globalThis.removeEventListener("resize", resize);
    },
  };
}
