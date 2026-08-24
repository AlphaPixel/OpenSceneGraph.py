# Async OSG.py: the pattern, the ceiling, and the glTF case study

Two reusable pieces (`examples/pyosg_async.py`): running `viewer.frame()` as
an ordinary `asyncio` task instead of a hand-rolled pump loop, and draining a
`.poll()`-shaped progress object from the coroutine already awaiting the
background work, instead of routing progress through a queue and a
`call_soon_threadsafe` bridge. `osgx.gltf.readNodeFile()` +
`osgx.gltf.AsyncProgress` is the concrete instance this grew out of and stays
the worked example throughout.

## The Node.js comparison

The intuitive model is Node's "fire and forget": kick off slow work on a
thread pool, keep the event loop responsive, `await` a result. Node's worker
threads never touch the JS engine while they work; they post exactly one
completion event back to the single JS thread.

OSG.py can genuinely match this — where it's real, it's *stronger*, since a
background thread doing off-GIL native work executes truly in parallel with
rendering on a second core, not just an I/O-completion callback on one
thread. But CPython's GIL is a sharper, stickier constraint than "the JS
engine" is in Node's model: it applies to *any* thread running *any* Python
bytecode, including a Python-written progress callback called from C++, not
just to a language-level boundary a worker can choose to respect.

## The mechanism: why a naive async loader can be slower than sync

`Viewer.frame()`'s pybind11 binding (`pyosg/pyosgViewer.cpp`) deliberately
does **not** release the GIL when `getThreadingModel() == SingleThreaded`
(this project's standing default) — see [`01-core.md`](01-core.md) rule 8.
A Python pump loop (`while not viewer.done: viewer.frame(); ...`) holds the
GIL, uninterrupted, for `frame()`'s entire C++ execution. Any background
thread that calls back into Python to report progress — including
`pybind11x::put_nowait()` (`etc/pybind11x.hpp`), which does
`py::gil_scoped_acquire` — cannot acquire the GIL until `frame()` returns. A
loader reporting progress dozens of times per load this way spends most of
its time waiting on the GIL, not working: measured as ~2x slower wall-clock
than sync loading the same model, despite the loader itself doing less work.

**Ruled out:** vsync/compositor pacing. Disabling vsync
(`__GL_SYNC_TO_VBLANK=0`) made no measurable difference — vsync caps the pump
loop's call rate, but each `frame()` call still costs real GIL-held C++ time
regardless, and the aggregate GIL saturation stays similar whether
distributed as few long holds (vsync-on) or many short ones (vsync-off).

## Two valid ways to get data out of a background thread

Both exist in this codebase for different situations. Neither is obsolete in
favor of the other.

**Push** (`pybind11x::StopEvent` + `pybind11x::put_nowait()`,
`examples/pyosg-async.py`'s `task_cpp_example`): the background thread calls
`put_nowait(loop, queue, ...)`, which acquires the GIL and schedules
`queue.put_nowait(...)` via `call_soon_threadsafe`. Correct when the thread
needs to hand back an irregular, genuinely Python-shaped value that doesn't
reduce to a few numbers, or that only happens occasionally — the GIL
acquisition cost is fine when infrequent.

**Poll** (`pybind11x::PollableProgress<Stage>`, `osgx.gltf.AsyncProgress`,
`examples/pyosg-async-gltf.py`): the background thread writes into
independent `std::atomic` fields — no GIL, ever, from that side. A poller
(which already owns the GIL) calls `.poll()` on its own schedule — a few
relaxed atomic loads, effectively free. Use this for a hot native loop's
simple, frequent, numeric tick (a progress bar) — pushing at that frequency
is exactly what produces the mechanism above.

Rule of thumb: if the background thread needs to call back into arbitrary
Python, push, rarely. If it's just numbers a poller can pull, poll — but on
a real cadence, not a busy-loop (next section).

## Gotcha: a poll loop still needs a real, positive sleep

`poll()` has no GIL cost, but `asyncio.sleep(0)` between checks isn't a real
sleep — it's a bare cooperative yield, so a loop built purely to poll with it
becomes an unthrottled busy-loop: near 100% of one CPU core spinning on
polling overhead, real OS-level contention with the background thread's
actual work. Measured **~75% slower** than the push-based version this
pattern was meant to improve on, before being fixed with a real default
poll interval. "Poll as often as convenient" only holds when the loop
already exists for another reason (a render loop polling implicitly via its
own 60fps cadence is free) — a loop whose only job is polling needs its own
real `asyncio.sleep(dt)`. `run_with_progress()`'s default `poll_interval` is
`1.0 / 60.0` — no reason to poll progress faster than it could be displayed.

## Make the render loop an ordinary `asyncio` task

Don't hand-roll the event loop pump:

```python
while not viewer.done:
    viewer.frame()
    loop.run_until_complete(asyncio.sleep(0))
    # ...manually drain a queue...
```

An ordinary `async def` wrapping `viewer.frame()` already works — between
calls, control genuinely returns to the Python bytecode eval loop, same as
any other coroutine's await point. `examples/pyosg_async.py`'s `run()`:

```python
async def run(viewer, *coros, fps=60, max_frames=None):
    async def render():
        while not viewer.done:
            viewer.frame()
            await asyncio.sleep(1.0 / fps)

    # NOT asyncio.gather(render(), *coros) — that waits for every task to finish,
    # so a coros task outliving the window closing would hang the session open.
    # The window closing (render_task finishing) must always end the session
    # immediately, cancelling coros; a coros task finishing must never end the
    # session by itself.
    render_task = asyncio.ensure_future(render())
    other_tasks = [asyncio.ensure_future(c) for c in coros]
    pending = {render_task, *other_tasks}
    try:
        while True:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                if not t.cancelled() and t.exception() is not None:
                    raise t.exception()
            if render_task not in pending:
                break  # the window closed — the only thing that ends the session
    finally:
        for t in (render_task, *other_tasks):
            if not t.done():
                t.cancel()
        ...
```

Loading code then reads close to plain `await`:

```python
async def load(viewer, path, stop, progress):
    node = await asyncio.to_thread(osgx.gltf.readNodeFile, path, stop, progress)
    viewer.sceneData.children.append(node)

asyncio.run(pyosg_async.run(viewer, load(viewer, path, stop, progress), bar.watch(progress)))
```

Two shapes for reacting to progress, both built on `run()`:

- `pyosg_async.run_with_progress(blocking_fn, *args, progress=, on_progress=, stop=, poll_interval=1.0/60.0)`
  — inline-callback shape: starts `blocking_fn` via `asyncio.to_thread`,
  polls progress itself, forwards to `on_progress`, returns the result.
  Right when the wait and the reaction naturally belong together (console
  output).
- `Progress.watch(progress, poll_interval=1.0/60.0)` — decoupled-task shape:
  its own coroutine, added directly to `run()`'s task list alongside the
  load, neither aware of the other. Right for a separate visual progress bar
  (`Progress`/`ProgressBar` — a real `osg.Camera` subclass, POST_RENDER +
  `clearMask=0` + identity view/projection, same shape as `pyosg-fire.py`'s
  `build_flash_camera()`).

**Only one poller per `AsyncProgress`.** Its "last seen generation" cursor
lives inside the C++ object itself (`AsyncProgress::seen`,
`~/dev/osgx/ext/python/osgx-gltf.cpp`), not per caller — two independent
consumers calling `.poll()` on the same instance steal updates from each
other; whichever polls first consumes that tick for both. Pick exactly one
poller per progress object.

## The glTF case study: `readNodeFile()` + `AsyncProgress`

`osgx.gltf.readNodeFile(location, stop_event, progress)` is a plain blocking
call, meant to run via `asyncio.to_thread(...)`, returning its result
normally — there is no `readNodeFileAsync()`; that queue/loop-based function
no longer exists. It never touches Python once it starts, not even to report
progress — progress is written into an `osgx.gltf.AsyncProgress` purely
through atomics, read back via `.poll()`.

**Expected overhead: ~1.25x, not parity.** Isolating the loader entirely (no
Viewer, no `frame()` calls at all) shows its wall-clock time is within noise
of a sync `osgDB.readNodeFile()` call on the same model — the pure
background load has no more headroom to give. The remaining ~1.25x gap in a
real windowed async run is the genuine cost of rendering hundreds of
concurrent `frame()` calls *while* the load runs — the actual point of async
loading (a responsive, rendering viewer while data loads), not overhead left
to eliminate. Don't chase this ratio to 1.0x. Validate any change to this
path on a real model (dozens+ of nodes, load time comfortably over a
second) — a tiny model's load is too fast/noisy to show a signal either way.

**Unrelated:** a model with very large source textures (tens of MB PNGs) can
show multi-second stalls inside `building_nodes` that are pure
single-threaded CPU cost in `osgDB::readImageFile()`'s decode — identical in
both sync and async loaders, nothing to do with GIL/threading. If
`building_nodes` looks slow, check texture file sizes before assuming
scene-graph construction is the cost.

## What this actually buys you

- A window that stays responsive immediately while a multi-second load
  happens fully concurrently — real hardware parallelism, not a
  cooperative-scheduling illusion.
- Ordinary `asyncio` composition: `await`, `gather`, cancellation
  propagation, once the render loop is just another task.
- One idiom (`run_with_progress`, `Progress.watch()`) reusable across every
  future "blocking native call + simple progress ticks" operation, instead
  of re-deriving queue-draining boilerplate per feature.

## Where the ceiling is

- **The GIL is coarser than Node's model** — enforced on any thread running
  any Python bytecode, including a Python-written progress callback passed
  into C++. The poll design only avoids contention because the hot
  reporting loop is pure C++ all the way down.
- **`frame()` not releasing the GIL is a hard wall, not a tuning knob** — see
  [`01-core.md`](01-core.md) rule 8. Async design works *around* this
  window, not by changing it.
- **Real CPU contention doesn't go away.** Two genuinely busy threads on
  finite cores still cost real time together — the residual ~1.25x above is
  concurrent rendering's actual cost, not a GIL artifact.
- **Cancellation stays cooperative.** A stop flag can only be checked
  between units of native work — it cannot interrupt one opaque blocking
  call already in flight (one `tinygltf` parse, one texture decode). Same
  limitation as Node's `AbortController` against synchronous native work.

## Where the pieces live

- `etc/pybind11x.hpp` — `StopEvent`, `put_nowait()` (push),
  `PollableProgress<Stage>` (poll). Shared infra, used by both the core
  pyosg bindings and osgx.
- `~/dev/osgx/ext/python/osgx-gltf.cpp` — `AsyncProgress` (the glTF-specific
  `PollableProgress` binding) and `readNodeFile()`.
- `examples/pyosg_async.py` — `run()`, `run_with_progress()`, and
  `Progress`/`ProgressBar`. Not yet part of the `OpenSceneGraph` package —
  see `[[project_native_package_split]]`.
- `examples/pyosg-async.py` — push-based demo.
- `examples/pyosg-async-gltf.py` — poll-based demo, `load()` and
  `bar.watch(progress)` as independent entries in `run()`'s task list.
