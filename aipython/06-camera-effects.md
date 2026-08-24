# Temporary camera effects (shake, kick, scripted moves) without taking control

For layering a TEMPORARY effect on top of the user's live manipulator (e.g.
`TrackballManipulator`) without replacing it and without the user losing
control afterward. Different from [`05-camera-manipulator.md`](05-camera-manipulator.md)'s
fully-replacing self-driving manipulators — this is about *layering*
something temporary on top of whatever manipulator is already there.

## Why an update callback on `viewer.camera` cannot do this

`osgViewer::Viewer::updateTraversal()` (`src/osgViewer/Viewer.cpp`) always
runs, in this order, every frame:

```cpp
_scene->updateSceneGraph(*_updateVisitor);   // invokes a camera's update callback
...
_cameraManipulator->updateCamera(*_camera);  // ALWAYS runs after, unconditionally
                                              // overwriting whatever the update callback wrote
```

`CameraManipulator::updateCamera()`'s C++ default is
`camera.setViewMatrix(getInverseMatrix())`, and it runs unconditionally after
the scene graph's own update traversal. Anything an update callback writes to
`camera.viewMatrix` is clobbered the same frame.

There is also no `cullCallback` exposed on `osg.Camera` in these bindings
(only `updateCallback`/`preDrawCallback`/`postDrawCallback`/`DrawCallback`/
`initialDrawCallback`/`finalDrawCallback`), and a pre/post-draw callback would
be too late anyway — cull has already baked that frame's matrices into the
render bins by draw time.

## The mechanism: `updateCamera()` is virtual, and runs LAST on purpose

`updateCamera(osg::Camera&)` is `virtual` specifically so a manipulator
subclass can override what gets written into the camera each frame — OSG's
own extension point for exactly this. The pattern is a **decorator
manipulator**: wrap the user's real manipulator, forward every normal
interaction to it untouched, and override only `updateCamera()` to compose
something extra on top of the inner manipulator's own output.

`updateCamera()` is bound on `osgGA::CameraManipulator`'s trampoline
(`pyosg/pyosgGA.hpp`/`.cpp`) and exposed as a normal method, so a decorator
can call `self.inner.updateCamera(camera)` directly. Uses the same
`call_override` (not `PYBIND11_OVERRIDE`) pattern `home(ea, aa)` uses: `osg::Camera`
derives from `osg::Referenced` and isn't copyable, and `PYBIND11_OVERRIDE`'s
implicit copy-for-marshaling would crash the instant a Python subclass
overrides it.

## The pattern (`examples/pyosg-fire.py`'s `EffectManipulator`)

```python
class EffectManipulator(osgGA.CameraManipulator):
	def __init__(self, inner):
		super().__init__()
		self.inner = inner
		self.effects = []  # zero-arg callables -> None or an osg.Matrixd to compose
		self._node = None

	# Forward everything else untouched.
	def setNode(self, node):
		self._node = node
		self.inner.node = node
	def getNode(self): return self._node
	def home(self, *args): self.inner.home(0.0)  # NOT self.inner.home(*args) — see below
	def handle(self, ea, aa): return self.inner.handle(ea, aa)  # untested live, see below
	def getMatrix(self): return self.inner.matrix
	def getInverseMatrix(self): return self.inner.inverseMatrix
	def setByMatrix(self, m): self.inner.matrix = m
	def setByInverseMatrix(self, m): self.inner.inverseMatrix = m

	# The one method that matters: called LAST, once per frame. Nothing runs after this.
	def updateCamera(self, camera):
		self.inner.updateCamera(camera)

		m = camera.viewMatrix

		for effect in self.effects:
			delta = effect()
			if delta is not None:
				m = m * delta  # eye-space compose — see 01-core.md rule 9 for OSG's multiply order

		camera.viewMatrix = m
```

Usage:

```python
trackball = osgGA.TrackballManipulator()
effect_manip = EffectManipulator(trackball)
viewer.cameraManipulator = effect_manip   # installed ONCE, stays for the session

shake_effect, shake_trigger = make_shake_effect(viewer, duration=0.3, magnitude=0.1)
effect_manip.effects.append(shake_effect)

shake_trigger()  # fire it any time — orbiting/panning underneath keeps working
```

An "effect" is any zero-arg callable returning `None` (inactive) or a matrix
to compose — a punch-zoom, a forced-look-at, a scripted flourish, all
installed once and left there for the rest of the session.

## The `home(ea, aa)` forwarding trap

`View.setCameraManipulator(resetPosition=True)` calls `manip->home(ea, *this)`
internally — `*this` being the live `View`/`Viewer`, passed where C++ expects
`GUIActionAdapter&`. Python resolves that argument to a full
`osgViewer.Viewer` object; forwarding it into `self.inner.home(ea, aa)`
(typed `GUIActionAdapter&` too) fails, because pybind11 doesn't know
`View`/`Viewer` "is a" `GUIActionAdapter`.

**Not fixable by declaring `GUIActionAdapter` as a base of `View`**:
`osgGA::GUIActionAdapter` is not `osg::Referenced`-derived (no `ref()`/
`unref()`), so it can never take an `osg::ref_ptr` holder to match `View`'s —
pybind11 requires every base in a `py::class_`'s template list to agree on
holder type. Fails at import time (`ImportError: generic_type: type "View"
has a non-default holder type while its base "osgGA::GUIActionAdapter" does
not`). This is a hard wall in the binding model — don't re-attempt it.

**The actual fix**: `EffectManipulator.home()` never forwards `(ea, aa)` — it
always calls `self.inner.home(0.0)`, the overload that doesn't need a
`GUIActionAdapter`.

`handle()` (mouse drag/orbit input) has the identical exposure and no
equivalent no-`aa` overload — `GUIEventHandler::handle()`'s real C++
implementation resolves a real `GUIActionAdapter&` before calling the 2-arg
`handle(ea, aa)` this binding exposes to Python, likely the same forwarding
trap. **Not yet tested live** — verify by actually dragging the mouse through
an installed `EffectManipulator` before trusting it. If it crashes the same
way, the likely fix is making `EffectManipulator` *inherit* from the real
manipulator class instead of holding it as `self.inner` and forwarding —
inherited (non-overridden) C++ methods resolve through the trampoline via
real virtual dispatch, no Python-argument-marshaling boundary to cross.
