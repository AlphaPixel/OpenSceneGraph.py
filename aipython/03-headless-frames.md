# Headless event and update frames

Do not create an `osgViewer.Viewer` merely to make OSG callbacks run in a
unit test. A Viewer brings windows, graphics contexts, event polling, camera
setup, cull traversal, and draw traversal — only pay that tax when the
behavior under test actually depends on one of those things. For update
callbacks, event callbacks, deterministic animation, or Python/C++
trampoline dispatch, use OSG's existing visitors directly.

## Pytest: use the fixture

`test/conftest.py` provides a fresh `simulate_frame` fixture per test. It
owns a `FrameStamp`, `EventQueue`, `EventVisitor`, `UpdateVisitor`, and a
recording Python `GUIActionAdapter`.

```python
def test_update_callback(simulate_frame):
	root = osg.Group()
	seen = []

	root.updateCallback = lambda node, visitor: seen.append(
		visitor.frameStamp.simulationTime
	)

	simulate_frame.advance(simulationTime=1.25)
	simulate_frame.traverseUpdate(root)

	assert seen == [1.25]
```

For event callbacks, queue events and traverse them:

```python
root.eventCallback = lambda node, visitor: ...

simulate_frame.advance(simulationTime=0.0)
simulate_frame.events.keyPress(ord("A"))
simulate_frame.events.frame(0.0)
simulate_frame.traverseEvents(root)
```

`simulate_frame.actions` records `requestRedraw()`,
`requestContinuousUpdate()`, and `requestWarpPointer()` calls. Assert against
`redraws`, `continuousUpdates`, or `pointerWarps`.

## Forcing a real C++ virtual call

A direct call such as `manip.handle(event, actions)` is not trampoline-proof
— ordinary Python attribute lookup can find a Python subclass method without
entering the C++ virtual-dispatch path. Call through the bound OSG base class
instead, so C++ uses the object's vtable and reaches the pybind trampoline
exactly as real OSG dispatch would:

```python
simulate_frame.dispatchEvent(manipulator, event)
CameraManipulator.updateCamera(manipulator, osg.Camera())
CameraManipulator.home(
	manipulator,
	simulate_frame.events.currentEventState,
	simulate_frame.actions
)
```

`test/osgGA_CameraManipulator.py` has the reference examples.

## Wall-clock-driven callbacks

Some animation callbacks track their own elapsed time via `time.time()`
directly instead of reading `nv.frameStamp.simulationTime`
(`LiveUpdateCallback`, `ShrinkCallback`/`FallCallback`).
`simulate_frame.advance(simulationTime=...)` has no effect on these;
monkeypatch `time.time` to a controllable fake clock instead:

```python
import time as time_module

class FakeClock:
	def __init__(self, t=0.0):
		self.t = t

	def __call__(self):
		return self.t

clock = FakeClock()
orig = time_module.time
time_module.time = clock

# ... build scene, attach callbacks ...

clock.t += 10.0  # jump well past any animation's duration
simulate_frame.traverseUpdate(root)

time_module.time = orig  # restore — other tests need the real clock
```

Still drive the tick through `simulate_frame.traverseUpdate(root)`, not by
calling each node's `updateCallback` directly — that exercises the real
`accept()`/traversal path instead of just the leaf callable in isolation.

## Testing an example script's OSG-dependent helpers

`examples/*.py` mix pure-Python logic, OSG-dependent helpers, and an
`if __name__ == "__main__":` block that opens a real window — only that last
part needs a display. To unit-test the helpers without constructing a
`Viewer`, `exec()` the file's source up to (not including) that guard:

```python
src = open("examples/pyosg-match4.py").read()
end = src.index('if __name__ == "__main__":')

ns = {"osg": osg, "osgGA": osgGA, "osgViewer": osgViewer, "__name__": "match4_headless"}

exec(src[:end], ns)

make_piece = ns["make_piece"]
ShrinkCallback = ns["ShrinkCallback"]
```

This works because constructing scene-graph objects (`osg.Sphere`,
`osg.Geode`, `osg.MatrixTransform`, `osg.Uniform`, ...) needs no GL context —
only `viewer.frame()` does. Combined with the fake-clock trick above, this is
enough to headlessly drive a whole multi-frame animation sequence end to end
against real OSG objects.

## Raw building blocks

- `osg.FrameStamp`
- `osgUtil.UpdateVisitor`
- `osgGA.EventQueue`
- `osgGA.EventVisitor`
- Python-subclassable `osgGA.GUIActionAdapter`
- `Node.updateCallback` and `Node.eventCallback`, each accepting either an
  OSG `NodeCallback` or a plain Python callable

For a manual update traversal, increment the frame number, set reference and
simulation time, set the visitor's `frameStamp` and `traversalNumber`, then
call `root.accept(visitor)`. Reset and feed each event to `EventVisitor`
before accepting it on the root.

## When a Viewer is still required

- a `View`'s own handler/manipulator ownership or scene/camera wiring;
- window/device polling, pointer-data reprojection, or close-window handling;
- cull traversal, camera ordering, render-to-texture execution, draw
  callbacks, OpenGL object compilation, readback, swap buffers, or any real
  GL state.

Headless simulation covers event and update traversal only — it is not fake
rendering.
