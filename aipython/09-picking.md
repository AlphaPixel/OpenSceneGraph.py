# `osgx` + `osgx.imgui`: the mouse-capture race

Sibling to [`07-camera-manual.md`](07-camera-manual.md)'s Rule 3, which
covers a different, earlier picking fix (window-origin subtraction). This
file is about `osgx` coexisting with an `osgx.imgui.Widget` panel in
the same window: three independent guards, all in `~/dev/osgx`
(`Picking.cpp`/`Picking.hpp`) — needs a rebuild to take effect; check
`PYOSG_OSGX_SOURCE_DIR` in your build dir's `CMakeCache.txt` first (see the
repo's `CLAUDE.md`).

Ship all three together. Each closes a different failure mode; removing any
one reopens a real, reproducible bug.

## Guard 1: `PickHandler` must check `ea.getHandled()` itself

`osgViewer::Viewer::eventTraversal()` calls **every** handler in the list for
**every** event — it never stops early just because an earlier handler
returned `true`. Every stock OSG handler
(`StatsHandler`/`HelpHandler`/the manipulators) opens `handle()` with
`if (ea.getHandled()) return false;` for exactly this reason. Without the
same check, `PickHandler` keeps recording mouse position from events an
`osgx.imgui.Widget` already claimed (`Widget` registers at the front of the
handler list via `push_front`, so it always runs first for a given event —
ordering is never the problem here).

## Guard 2: a one-shot `invalidate()` isn't enough — suspend continuously

`PickCameraSync`'s continuous per-frame readback re-samples whatever
`mouseX()`/`mouseY()` currently is, every frame, regardless of events. Guard
1 stops `PickHandler` from updating that position while ImGui has capture,
but the frozen position is still real, valid geometry — so the next
continuous-readback frame re-detects it as hovered, undoing a single
`invalidate()` call (visible as flickering tint, not a clean off).

Fix: `PickReadback::setSuspended(bool)`/`isSuspended()`, set from
`PickHandler::handle()` on every dispatched event, and
`PickCameraSync::operator()` calls `invalidate()` every frame for as long as
`isSuspended()` stays true — the same pattern already used for "cursor left
the OS window" (`platform::isCursorInWindow()`).

## Guard 3: `WantCaptureMouse` itself lags one frame behind the event that set it

The subtlest guard, and the one that survives Guards 1+2. `osgx::imgui::Widget`'s
MOVE/DRAG handler does, in one call:

```cpp
io.AddMousePosEvent(ea.getX(), io.DisplaySize.y - ea.getY());
return io.WantCaptureMouse;
```

Dear ImGui only *recomputes* `WantCaptureMouse` inside its own `NewFrame()`
(run later, from `Widget`'s `PreDraw` callback), so this read reflects the
**previous** frame's hover result. The first MOVE event whose coordinates
land on an ImGui panel is still judged against the old (still-`false`)
capture state, so it comes through with `ea.getHandled() == false`.
`isSuspended()` never gets set for that event, and `PickHandler` stores that
real but genuinely out-of-viewport coordinate as `mouseX()`/`mouseY()`. If
the cursor stops moving right there, picking stays pinned to that bad sample
indefinitely — an inherent one-frame lag in immediate-mode GUI input, not an
event-ordering bug, so don't re-chase Guard 1/2 if this specific symptom
recurs.

Fix: a third, purely geometric guard in `PickCameraSync::operator()`, immune
to the lag because it depends only on this frame's own numbers:

```cpp
int localX = _rb->mouseX() - originX;
int localY = _rb->mouseY() - originY;
bool cursorInViewport = localX >= 0 && localX < width && localY >= 0 && localY < height;

if (!cursorInViewport) _rb->invalidate();
```

The pick1x1 sub-frustum block only runs when `cursorInViewport` is true;
otherwise the pick camera gets the plain (un-aimed) projection matrix, since
nothing downstream observes it.

## Why not JUST the geometric check?

It's tempting to drop Guards 1/2 and rely on Guard 3 alone — simpler, no
lag, no `ea.getHandled()`/event-chain reasoning. It would even fix a
fixed-dock ImGui layout, where the dock exactly coincides with "outside
`camera.viewport`". But a floating/undocked ImGui window, a popup, a
tooltip, or a context menu drawn ON TOP of the 3D viewport's own rectangle
puts the cursor geometrically *inside* the viewport while ImGui still
legitimately has capture — Guard 3 alone waves that through (click-fallthrough
again), while Guard 1/2's `ea.getHandled()`-driven `isSuspended()` still
correctly reflects "some handler already claimed this," regardless of screen
position. Keep both: the event-based guard generalizes across UI layouts, the
geometric guard closes the timing hole the event-based one cannot.
