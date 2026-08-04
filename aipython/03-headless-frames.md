# Headless event and update frames

Do not create an `osgViewer.Viewer` merely to make OSG callbacks run in a
unit test. A Viewer brings windows, graphics contexts, event polling, camera
setup, cull traversal, and draw traversal with it. That is a **Viewer tax**:
only pay it when the behavior under test actually depends on one of those
things.

For scene-graph update callbacks, event callbacks, deterministic animation,
or Python/C++ trampoline dispatch, use OSG's existing visitors directly.

## Pytest: use the fixture

`test/conftest.py` provides a fresh `simulate_frame` fixture for every test.
It owns a `FrameStamp`, `EventQueue`, `EventVisitor`, `UpdateVisitor`, and a
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

For scene event callbacks, queue events and traverse them:

```python
root.eventCallback = lambda node, visitor: ...

simulate_frame.advance(simulationTime=0.0)
simulate_frame.events.keyPress(ord("A"))
simulate_frame.events.frame(0.0)
simulate_frame.traverseEvents(root)
```

`simulate_frame.actions` records `requestRedraw()`,
`requestContinuousUpdate()`, and `requestWarpPointer()` requests made by OSG
handlers. Assert against `redraws`, `continuousUpdates`, or `pointerWarps`
when that behavior matters.

## Forcing a real C++ virtual call

A direct call such as `manip.handle(event, actions)` is not trampoline proof:
ordinary Python attribute lookup can find a Python subclass method without
ever entering the C++ virtual-dispatch path.

Call through the appropriate bound OSG base class instead. This makes C++ use
the object's vtable and reaches the pybind trampoline exactly as real OSG
dispatch would:

```python
simulate_frame.dispatchEvent(manipulator, event)
CameraManipulator.updateCamera(manipulator, osg.Camera())
CameraManipulator.home(
	manipulator,
	simulate_frame.events.currentEventState,
	simulate_frame.actions
)
```

The camera-manipulator regression tests in `test/osgGA_CameraManipulator.py`
are the reference examples.

## Raw building blocks

The bindings intentionally expose the underlying OSG pieces too:

- `osg.FrameStamp`
- `osgUtil.UpdateVisitor`
- `osgGA.EventQueue`
- `osgGA.EventVisitor`
- Python-subclassable `osgGA.GUIActionAdapter`
- `Node.updateCallback` and `Node.eventCallback`, each accepting either an
  OSG `NodeCallback` or a normal Python callable

For a manual update traversal, increment the frame number, set reference and
simulation time, set the visitor's `frameStamp` and `traversalNumber`, then
call `root.accept(visitor)`. Reset and feed each event to `EventVisitor` before
accepting it on the root.

## When a Viewer is still required

Use a real Viewer when the test depends on any of the following:

- a `View`'s own handler/manipulator ownership or scene/camera wiring;
- window/device polling, pointer-data reprojection, or close-window handling;
- cull traversal, camera ordering, render-to-texture execution, draw callbacks,
  OpenGL object compilation, readback, swap buffers, or any actual GL state.

Headless simulation deliberately covers event and update traversal only. It is
not fake rendering.
