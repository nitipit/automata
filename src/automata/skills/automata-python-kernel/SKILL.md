---
name: automata-python-kernel
description: Use for persistent Python execution and retaining live objects across interactions through IPython/Jupyter kernels. Not for one-shot scripts or repeatable batch execution.
---

# Automata Python Kernel

Use an IPython kernel with `jupyter_client` when retaining live objects helps;
prefer scripts for repeatable work. Reuse available clients and consult API
documentation as needed, rather than building another runtime framework.

1. **Own the kernel.** Use a task-owned environment and private connection file
   outside installed assets. Record the kernel identity, connection location, CWD
   and lifecycle owner. Reconnect to that kernel across calls; unrelated Python
   processes do not share its objects. Confirm setup and persistent-process
   authority; do not silently install dependencies or attach to another task's
   kernel. Preserve Jupyter's security defaults and protect connection credentials.
   Keep the connection-file owner alive: a temporary `KernelManager` can unlink
   the file when destroyed. For an independently owned kernel, the public
   `write_connection_file` with a fresh `Session().key` avoids that manager lifetime;
   never use an empty key. Keep loopback binding and restrictive file permissions.
   A kernel is not a sandbox.

2. **Keep execution observable.** Correlate replies using Jupyter's message IDs
   and confirm completion. Bound waits and output, disable interactive stdin and
   coordinate clients rather than competing for replies. Inspect only needed state;
   object inspection can execute code. Minimize sensitive output and retention.

3. **Recover without replay.** Errors, timeouts and interrupts can leave partial
   mutations or uncertain outcomes. Inspect before retrying consequential code;
   interruption is best effort. Restart loses live objects but undoes no external
   effects. Confirm valuable-state loss unless authorized, then verify the new
   kernel's identity and readiness rather than trusting stale handles.

4. **Finish or hand off.** Save useful results as artifacts, scripts or tests;
   live state is not durable memory. Leave a kernel running only for authorized use
   with ownership and reconnect details; otherwise shut down the owned kernel and
   verify it stopped. Account separately for spawned processes. Stopping does not
   authorize deleting history or artifacts.
