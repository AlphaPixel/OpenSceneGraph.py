# `osgx` cursor handling: absolute position, unprojecting, visibility, and capture

Everything `osgx::Cursor.hpp` provides, in one place. Two genuinely different problem domains
share this header — don't conflate them:

- **Absolute position → world-space point**: "where in the 3D/2D scene is the mouse pointing,"
  for drawing/picking/placement. `CursorState`/`CursorHandler`/`CursorCallback` +
  `unprojectToPlane()`.
- **Relative motion → camera input**: "how far did the mouse move since last frame, unbounded," for
  turntable/FPS-style look controls that need to turn past the physical screen edge.
  `CursorCapture`.

Plus two bare one-liners (`setCursorVisible()`/`warpCursor()`) used by both.

## Absolute position: `CursorState`/`CursorHandler`/`CursorCallback` + `unprojectToPlane()`

This supports cursor-following drawing, picking, and placement effects. The gotchas below apply
when an effect converts cursor samples into world-space points.

### The API trio

`osgx.CursorState` is pure, thread-safe position state (atomic x/y/inWindow/
yIncreasingDownwards) — nothing about it requires a pick camera or rendering. Two ways to drive
it:

- `osgx.CursorHandler(state)`, added via `viewer.eventHandlers.append(...)`, updates `state` from
  every real `MOVE`/`DRAG` event — event-driven, lossless, always returns `False` so the active
  manipulator still sees the event too.
- `osgx.CursorCallback(state, fn)`, installed via `node.updateCallback = ...`, fires
  `fn(x, y)` once per **update traversal** (once per rendered frame) with `state`'s current
  position — convenient, but see "Sampling-rate gotcha" below before assuming this is the same
  thing as "every mouse event."

Canonical C++ reference: `osgx/examples/osgx-picking.cpp`'s own smoke test wires all three
together — read it before inventing a different composition.

To turn a tracked position into a world-space point, use `osgx.unprojectToPlane(camera, viewport,
x, y, yIncreasingDownwards, plane)` (one call) or its pieces — `windowToNDC()` +
`unprojectRay()` + `intersectRayPlane()` — if you need the ray itself for something else.
`yIncreasingDownwards` MUST come from `state.yIncreasingDownwards` (refreshed per-event from the
real `GUIEventAdapter.mouseYOrientation`), never a hardcoded literal — `osgx`'s own `Cursor.hpp`
comment documents a real prior bug from hardcoding this (osgx-aoe's Mode 1, a Y-inverted decal).

### Use the projection helpers instead of hand-rolled unprojection

Don't reconstruct a camera basis from `fovy`/`aspect` or repeat the per-event NDC math. Use
`unprojectToPlane()` or the lower-level helpers above; they derive the ray from the camera's actual
view and projection matrices.

### It works under perspective as well as ortho

`unprojectToPlane()` never special-cases orthographic projection; it inverts `view*projection` and
casts a real ray, so it works identically for any camera. A point on a z=0 plane can therefore be
found from an oblique 3D camera just as it can from a top-down orthographic camera; no caller
opt-in is needed.

### Sampling-rate gotcha: `CursorCallback` is once-per-frame, not once-per-event

If a consumer (e.g. a drawing/stamping effect) only samples position from `CursorCallback`'s `fn`,
it only ever sees the straight-line hop between the position at the *start* of a frame and the
position at the *end* of it. `CursorState` itself updates losslessly on every real `MOVE`/`DRAG`
event via `CursorHandler` — the gap is entirely in how often a consumer chooses to read it. Fast
cursor movement means more real events land between two frames, so the frame-to-frame hop can be
much larger than it looks like it "should" be, and any per-sample effect (e.g. "place a stamp
every N world units of travel") under-samples the true path at speed. A stamped trail can therefore
go from solid or overlapping at low speed to dotted or gappy at high speed, because each large
unsampled hop only produces one new stamp at its far end.

Fix, if the effect actually needs this to be speed-independent: react to every raw event directly
via a plain `GUIEventHandler` instead of `CursorCallback`, then linearly interpolate between
consecutive raw points and resample at fixed arc-length intervals along that segment — standard
polyline resampling, not a hard problem on its own. Smoothing "wonky"/jittery input well (rolling-
window curve fit, velocity-based density) is the actually-hard follow-up.

## OS cursor visibility and warping: `setCursorVisible()`/`warpCursor()`

Two plain actions, not get/set pairs — OSG's `GraphicsWindow` has no visibility getter of its own
(`useCursor()` is write-only), so `osgx` doesn't fake one either.

- `osgx.setCursorVisible(view, visible=True)` — shows/hides the OS cursor for `view`'s current
  window. No-op if the view has no realized `GraphicsWindow` yet (i.e. before the first
  `viewer.frame()`/`realize()`).
- `osgx.warpCursor(view, x, y)` — warps the OS pointer to `(x, y)` in view/event coordinates (the
  same space as `GUIEventAdapter.x/y`, NOT window-local pixels), without the jump itself being
  reported as motion to whatever reads the next delta. `CursorCapture` (below) uses this
  internally for its hide+warp+accumulate trick — reach for `CursorCapture` instead of calling
  `warpCursor()` by hand for that use case.

## Relative motion: `CursorCapture` — unbounded look-control input

A completely different problem from everything above: not "where is the cursor pointing in the
scene," but "how far did it move since I last asked," with no bound from the physical screen edge
— the standard hide+warp+accumulate trick FPS/turntable camera controls need. **Not** true OS-level
pointer confinement (nothing stops the cursor visibly darting to the screen edge for one frame on
some window managers/compositors) — real confinement needs `XGrabPointer` (Linux) and platform
equivalents, not yet implemented.

```python
capture = osgx.CursorCapture(view)   # starts disabled
capture.captured = True              # hides the cursor, starts warp+accumulate
capture.deadZone = 1.0               # pixels; filters sub-pixel warp/recenter jitter, default 1
delta = capture.drain()              # raw pixel units, resets the accumulator
delta = capture.drainNormalized(ea)  # same, rescaled to [-1,1]-ish window-normalized units
```

### Poll on `FRAME`, not `MOVE`/`DRAG`

The real composition pattern (`osgx-turntable.cpp`'s `OrbitCaptureBridge`,
`osgx-manipulator.cpp`'s equivalent): `drain()`/`drainNormalized()` only on
`GUIEventAdapter.FRAME` events, gated on `capture.isCaptured`, once per frame — NOT inside the
`MOVE`/`DRAG` branch. `drain()` already accumulates across however many raw events landed since
the last call and resets to zero, so polling once a frame on `FRAME` naturally captures everything
regardless of event rate; polling per-`MOVE`/`DRAG` event instead would drain a near-empty
accumulator on each one and fragment the real per-frame delta into noise.

### `drainNormalized()` needs real pixel-unit-to-normalized conversion — don't feed `drain()` raw

`drain()`'s raw pixel-unit delta fed directly into a manipulator expecting `[-1, 1]`-normalized
input (e.g. `performMouseDeltaMovement()`, `OrbitAxisManipulator.orbitByDelta()`) is a real,
previously-made mistake — sensitivity off by two or three orders of magnitude. Always use
`drainNormalized(ea)` for anything feeding a manipulator; it divides by half the window's
width/height and corrects for the event's own Y orientation, matching
`GUIEventAdapter.x_normalized`/`y_normalized`'s own convention exactly. `ea` only needs to be a
recent/current event (read purely for window extent and Y orientation, not its own position) — the
`FRAME` event being polled on works fine for this.

### Deliberately NOT wired into any manipulator directly

`CursorCapture` doesn't know about `OrbitAxisManipulator` (or any manipulator) and isn't composed
into one in `osgx` itself — compose them at the application level, as `OrbitCaptureBridge` does:
toggle `capture.captured` on a keypress, feed `drainNormalized()`'s result into the manipulator's
own delta-input method. This keeps the manipulator ignorant of which capture scheme (or none) is
driving it, so a different one can be swapped in without touching manipulator code.
