# Temporary camera effects (shake, kick, scripted moves) without taking control

The recurring ask this is for: "make the camera shake/punch-zoom/orbit-for-a-
moment," WITHOUT replacing the user's live `TrackballManipulator` (or whatever
they're actively driving) and without them losing control afterward. This is
different from [`05-camera-manipulator.md`](05-camera-manipulator.md)'s
`CinematicOrbitManipulator`, which fully *replaces* the manipulator (a
self-driving camera with nothing underneath it) -- this doc is about *layering*
something temporary on top of whatever manipulator is already there.

## Why an update callback on `viewer.camera` cannot do this

The instinct is to perturb `viewer.camera.viewMatrix` from an `updateCallback`
on the camera each frame. **Confirmed this can never work**, by reading real
OSG source (`src/osgViewer/Viewer.cpp`, `Viewer::updateTraversal()`) and then
confirming empirically:

```cpp
_scene->updateSceneGraph(*_updateVisitor);   // line ~1152 -- this is what invokes
                                              // a camera's update callback
...
_cameraManipulator->updateCamera(*_camera);  // line ~1213 -- ALWAYS runs after,
                                              // unconditionally overwriting
                                              // whatever the update callback wrote
```

`CameraManipulator::updateCamera()`'s C++ default (`include/osgGA/
CameraManipulator`) is `camera.setViewMatrix(getInverseMatrix())`. It runs
**after** the scene graph's own update traversal, every single frame, no
exceptions. Anything an update callback writes to `camera.viewMatrix` is
clobbered moments later, same frame. Confirmed empirically too, not just by
reading source: an update callback was firing every frame (~70 calls over
0.3s, verified via a call counter), yet sampling the decomposed eye position
(`viewMatrix.getLookAt(1.0)`) every ~40ms during an active "shake" window
showed **zero change** -- the writes were real, they just never survived.

There is also no `cullCallback` exposed on `osg.Camera` in these bindings
(only `updateCallback`/`preDrawCallback`/`postDrawCallback`/`DrawCallback`/
`initialDrawCallback`/`finalDrawCallback`) -- and a pre/post-draw callback
would be too late anyway (cull has already baked that frame's matrices into
the render bins by draw time; a draw-time write only affects the *next*
frame's cull, a one-frame lag).

## The actual mechanism: `updateCamera()` is virtual, and runs LAST on purpose

`updateCamera(osg::Camera&)` is declared `virtual` specifically so a
manipulator subclass can override what gets written into the camera each
frame -- it's not a fixed pipeline step, it's OSG's own extension point for
exactly this. The idiomatic pattern is a **decorator manipulator**: wrap the
user's real manipulator, forward every normal interaction to it untouched, and
override only `updateCamera()` to compose something extra on top of the
inner manipulator's own output -- in the one place nothing can overwrite it
afterward, because it *is* the last thing that runs.

**Binding gap found and fixed this session** (2026-08-02, needs a rebuild to
take effect): `updateCamera()` was entirely missing from this project's
`osgGA::CameraManipulator` trampoline (`pyosg/pyosgGA.hpp`) -- a Python
override would have been silently ignored, same shape as the `setNode()`/
`getNode()`/`home()` gaps `05-camera-manipulator.md` already documents (fixed
2026-07-16). Also added `.def("updateCamera", ...)` to the `py::class_` binding
itself (`pyosg/pyosgGA.cpp`), so a decorator can call `self.inner.updateCamera
(camera)` directly. Uses the same `call_override` (not `PYBIND11_OVERRIDE`)
pattern `home(ea, aa)` uses, for the same reason: `osg::Camera` derives from
`osg::Referenced` and isn't copyable, and `PYBIND11_OVERRIDE`'s implicit
copy-for-marshaling would crash the instant a Python subclass overrides it.

## The pattern (`examples/pyosg-fire.py`'s `EffectManipulator`)

```python
class EffectManipulator(osgGA.CameraManipulator):
	def __init__(self, inner):
		super().__init__()
		self.inner = inner
		self.effects = []  # zero-arg callables -> None or an osg.Matrixd to compose
		self._node = None

	# Forward everything else untouched -- inner behaves exactly as if it were
	# the manipulator directly.
	def setNode(self, node):
		self._node = node
		self.inner.node = node
	def getNode(self): return self._node
	def home(self, *args): self.inner.home(*args)
	def handle(self, ea, aa): return self.inner.handle(ea, aa)
	def getMatrix(self): return self.inner.matrix
	def getInverseMatrix(self): return self.inner.inverseMatrix
	def setByMatrix(self, m): self.inner.matrix = m
	def setByInverseMatrix(self, m): self.inner.inverseMatrix = m

	# The one method that matters: called LAST, once per frame, by
	# osgViewer::Viewer::updateTraversal() -- nothing runs after this.
	def updateCamera(self, camera):
		self.inner.updateCamera(camera)

		m = camera.viewMatrix

		for effect in self.effects:
			delta = effect()
			if delta is not None:
				m = m * delta  # eye-space compose, see feedback_osg_matrix_order

		camera.viewMatrix = m
```

Usage:

```python
trackball = osgGA.TrackballManipulator()
effect_manip = EffectManipulator(trackball)
viewer.cameraManipulator = effect_manip   # installed ONCE, stays for the session

shake_effect, shake_trigger = make_shake_effect(viewer, duration=0.3, magnitude=0.1)
effect_manip.effects.append(shake_effect)

shake_trigger()  # fire it any time -- orbiting/panning underneath keeps working
```

This generalizes past shake: an "effect" is just a zero-arg callable returning
`None` (inactive) or a matrix to compose. A punch-zoom, a brief forced-look-at,
a scripted flourish that eases back to whatever the user was doing -- all the
same shape, all installed once as an `EffectManipulator` and left there for
the rest of the session.

**Status: `updateCamera()` trampoline fix rebuilt and confirmed working.**
`EffectManipulator.home()` needed one adjustment first -- see next section.
`handle()` (mouse drag/orbit input) has the same theoretical exposure but is
UNTESTED as of this writing; verify live before trusting it.

## The `home(ea, aa)` forwarding trap, and why the "real" fix is impossible

The first live test crashed immediately on `viewer.cameraManipulator =
effect_manip`:

```
TypeError: home(): incompatible function arguments...
Invoked with: <TrackballManipulator>, <GUIEventAdapter>, <osgViewer.Viewer object at ...>
```

`View.setCameraManipulator(resetPosition=True)` calls `manip->home(ea, *this)`
internally -- `*this` being the live `View`/`Viewer`, passed where C++ expects
`GUIActionAdapter&`. `EffectManipulator.home()`'s Python override correctly
receives that as a full `osgViewer.Viewer` Python object (pybind11 resolves
return/callback values to their most-derived *registered* type) -- but
forwarding that same object into `self.inner.home(ea, aa)` (another bound C++
method also typed `GUIActionAdapter&`) fails, because pybind11 doesn't know
`View`/`Viewer` "is a" `GUIActionAdapter` at all.

**Tried the obvious real fix and confirmed it's structurally impossible**:
re-declared `osgGA::GUIActionAdapter` as a pybind11 base for `osgViewer::View`
(`pyosg/pyosgViewer.cpp`) -- same shape `GraphicsWindow` originally had before
it was removed. Failed at **import time**, not subtly, with exactly the error
predicted from reading pybind11's own holder-consistency check
(`pybind11/attr.h`) before even trying:

```
ImportError: generic_type: type "View" has a non-default holder type while
its base "osgGA::GUIActionAdapter" does not
```

Root cause confirmed via the real OSG header: `osgGA::GUIActionAdapter` is
**not** `osg::Referenced`-derived (no `ref()`/`unref()`), so it can never take
an `osg::ref_ptr` holder to match `View`'s. pybind11 requires every base in a
`py::class_`'s template argument list to agree on holder type. This is a hard
wall in this binding model, not a smarter-declaration problem -- reverted,
and the comment in `pyosgViewer.cpp` above the `View` binding now documents
this as **confirmed**, not just suspected, so it's never re-attempted from
scratch.

**The actual fix**: `EffectManipulator.home()` doesn't forward `(ea, aa)` at
all -- it always calls `self.inner.home(0.0)`, the overload that doesn't need
a `GUIActionAdapter`:

```python
def home(self, *args):
	self.inner.home(0.0)  # NOT self.inner.home(*args) -- see above
```

**`handle()` has the identical exposure and no equivalent escape hatch** --
`GUIEventHandler::handle(Event*, Object*, NodeVisitor*)`'s real C++
implementation (`src/osgGA/GUIEventHandler.cpp`) resolves a real
`GUIActionAdapter&` via `nv->asEventVisitor()->getActionAdapter()` before
calling the 2-arg `handle(ea, aa)` our trampoline exposes to Python -- almost
certainly the same live Viewer object, same forwarding trap, but this one
doesn't have a same-purpose no-`aa` overload to fall back to. **Not yet
tested live** (verify by actually dragging the mouse to orbit through an
installed `EffectManipulator` before trusting it works) -- if it crashes the
same way, the likely real fix is making `EffectManipulator` *inherit* from
the real manipulator (e.g. `class EffectManipulator(osgGA.TrackballManipulator)`)
instead of holding it as a separate `self.inner` and forwarding calls to it --
inherited (non-overridden) C++ methods resolve through the trampoline via
real virtual dispatch, with no Python-argument-marshaling cast boundary to
cross at all.

## VSG comparison (recalled, not verified this session)

VulkanSceneGraph's camera model separates `vsg::Camera` from a pluggable
`vsg::ViewMatrix` interface (`vsg::LookAt`/`vsg::Trackball` are two concrete
implementations) -- structurally similar in spirit (something else produces
the matrix, the Camera just holds whatever it's given), but this is from
training knowledge, not something checked against an actual VSG source tree
in this session. Worth a real look if a VSG-flavored comparison ever matters
enough to justify checking out the source -- not done here.
