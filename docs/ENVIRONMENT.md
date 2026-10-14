# Local toolchain

On 13 Oct 2026 the frontend checks stalled while more than one Vite process was already running. A `vite --host 127.0.0.1 --port 5173` dev server had been up for many hours. During that overlap:

- `vite build` printed `transforming...` and then sat idle, with the main thread in `kevent` and CPU near 0%.
- Vitest workers timed out, or failed because an export was missing at runtime (`generatedInterface.install`, `Scheduler.unstable_now`) even though the file on disk still contained it. The missing name changed between runs.
- `tsc` and `vite build` were sometimes killed with exit 137.
- A restarted dev server logged `RefreshRuntime.createSignatureFunctionForTransform is not a function` against `src/chart.tsx`.

Stopping the extra Vite and wedged Node processes, and deleting the Node compile cache under the temp directory, let the same commands finish. No package, lockfile, or source file was changed. Node 24.19.0 did not clear the missing-export failure by itself, so the runtime was not pinned.

After that cleanup, from `frontend/`: typecheck passed, Vitest passed 13 tests in 3 files, and the production build transformed 2506 modules. An isolated `vite build` finished in about 570 ms. One overlapping build took about 6 minutes and still exited 0. Vite still warns that the main chunk is over 500 kB.

This note records the overlap and the recovery. It does not establish a single cause. If a check stalls or reports a missing export from an intact package file, stop other Vite processes and retry the same command before changing dependencies or source.
