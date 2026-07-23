# Camera manipulators in a live REPL session

## Custom `osgGA.CameraManipulator` subclasses: known-fixed binding gaps

All confirmed fixed and tested as of 2026-07-16 -- listed here so a fix isn't
mistakenly re-attempted, and so the *shape* of these bugs is recognizable if
something similar turns up in a different binding:

- **`setNode()`/`getNode()` now actually dispatch to a Python override.**
  `View.setCameraManipulator(manip, resetPosition=True)` calls
  `manip->setNode(scene)` internally; the trampoline used to not intercept
  this at all, so `self.node` was silently always `None` regardless of what
  a Python subclass defined.
- **`.node` no longer leaks on reassignment.** Previously used
  `py::keep_alive<>`, which has no way to release a *previous* patient --
  reassigning `.node` repeatedly (e.g. swapping scenes) leaked every prior
  node until the manipulator itself died. Now a replaced, not accumulated,
  property slot.
- **`home(ea, aa)` no longer crashes.** Used to raise `return_value_policy =
  copy, but type osgGA::GUIEventAdapter is non-copyable!` the instant a
  Python subclass defined a `home()` override and something triggered
  `resetPosition=True`. Reproducible fully headless, no window/realize()
  needed.

**Nuance if writing a new manipulator subclass:** the trampoline fix makes
overriding `setNode()`/`getNode()` *possible*, but doesn't give free storage
if a subclass doesn't override them at all -- you still need explicit
`setNode`/`getNode` overrides storing into e.g. `self._node` if you want
`self.node` to reflect the real scene bound (radius/center), not a `1.0`/
origin fallback.

## Live camera-relative technique: aiming a light relative to the CURRENT view

Useful pattern for interactively tuning a directional light "from the
camera's perspective" (e.g. matching a reference render) rather than in raw
world-space azimuth, which looks different every time the user orbits:

```python
eye, center, up_v = v.camera.viewMatrix.getLookAt(1.0)  # NOT the inverse -- see gotcha below
fwd = center - eye; fwd.normalize()
right = fwd.cross(up_v); right.normalize()
up_v.normalize()

# Decompose an existing direction against this basis:
offset = osg.Vec3d(light_dir_u.value.x, light_dir_u.value.y, light_dir_u.value.z)
screen_right = offset.dot(right)      # + = camera's right
screen_up    = offset.dot(up_v)       # + = above
toward_camera = -offset.dot(fwd)      # + = pointing back at the viewer

# Build a new direction directly in this basis, e.g. 45deg upper-right, 45deg off-axis:
L_world = right * 0.5 + up_v * 0.5 - fwd * 0.70710678
L_world.normalize()
new_offset = L_world * offset.length()  # preserve the original magnitude
```

**Always recompute the camera basis fresh, immediately before use** -- if the
user is actively orbiting between REPL calls (likely, since they're usually
comparing against a reference image live), a basis read even one call ago is
stale.

**Directional-light caveat:** there is no "point at X" for a sun-type light
(no position, no falloff) -- the only lever is elevation (how overhead it
is), which changes *what surfaces catch light*, not *where* it's aimed.
Translate "point down at the subject" into "increase the up-component,
decrease the frontal component," not literal aiming.

### Gotchas specific to this technique

- **`Matrixd.getLookAt(distance)` operates on the view matrix directly, NOT
  its inverse.** Calling it on `osg.Matrix.inverse(v.camera.viewMatrix)`
  silently returns plausible-looking-but-wrong eye/center/up, no error.
- **`Vec3.dot()`/arithmetic require matching types** -- a uniform's `.value`
  is often `Vec3f` while matrix math returns `Vec3d`; mixing raises
  `TypeError: incompatible function arguments`. Cast explicitly:
  `osg.Vec3d(v.x, v.y, v.z)`.
- **No `^` cross-product operator** -- use `.cross()`.
- **`osg.setNotifyLevel` set too high floods the tmux pane** with X11 event
  spam (`FocusIn`/`KeymapNotify`/etc.), making the pane unreadable. Fix live:
  `osg.setNotifyLevel(osg.NotifySeverity.WARN)`.

## There is no `viewer.home()`

`osgViewer::ViewerBase`/`Viewer` has no `home()` in these bindings --
`viewer.cameraManipulator.home` exists but wants `(ea, aa)` event-handler
args that aren't trivially available outside actual event dispatch. In
practice this doesn't matter: assigning `viewer.cameraManipulator = ...`
*after* `viewer.sceneData` is already set triggers the manipulator's own
`autoComputeHomePosition` framing automatically (confirmed live) -- no
explicit home call needed for the common "just frame the scene" case.
