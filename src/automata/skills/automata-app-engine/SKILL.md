---
name: automata-app-engine
description: Use for creating, rejoining, inspecting and stopping a task-owned Python-kernel app across turns, with or without a user interface or subprocesses.
---

# Automata App Engine

Use a persistent Python kernel as the app engine. The app's purpose is generic; its engine is not a per-task choice. Keep app state and references to owned workers in the kernel. A browser view is optional. If a suitable kernel is unavailable, report the prerequisite rather than silently switching engines or installing dependencies.

1. **Identify the instance.** Agree on purpose, inputs, allowed effects, owner and lifetime. Before starting, check for the task's existing instance. Record the app identity, kernel identity, working directory, private reconnect location and cleanup owner outside installed assets. Use the Python kernel guidance for authenticated setup and reconnection; never publish connection credentials.
2. **Start once; demonstrate readiness.** Create a dedicated kernel for a new instance. Initialize app state once and check an app-level result. A live process or a visible page alone does not prove readiness. When launching a subprocess, apply background-process guidance to its output, readiness, ownership and shutdown.
3. **Return without replay.** Verify the same live kernel and app before reading or changing it. Do not silently rerun initialization, start another worker, or attach another chat's kernel. If state was lost, distinguish saved results from live state and report the loss. Closing a view only detaches the view.
4. **Stop by ownership.** Stop owned workers and the kernel; verify both, including surviving children if the kernel died unexpectedly. Leave borrowed services and other apps alone. Stopping does not authorize deleting saved results.
