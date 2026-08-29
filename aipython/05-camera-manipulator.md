# Camera manipulators in a live REPL session

## Custom `osgGA.CameraManipulator` subclasses: overrides that actually dispatch

- **`setNode()`/`getNode()` dispatch to a Python override.** `View.setCameraManipulator(manip, resetPosition=True)` calls `manip->setNode(scene)` internally.
- **`.node` doesn't leak on reassignment** — a replaced, not accumulated, property slot.
- **`home(ea, aa)` doesn't crash** on a Python subclass override.

A subclass that doesn't override `setNode`/`getNode` at all still needs
explicit overrides storing into e.g. `self._node` if you want `self.node` to
reflect the real bound scene (radius/center), not a `1.0`/origin fallback.

## Live camera-relative technique: aiming a light relative to the CURRENT view

Useful for interactively tuning a directional light "from the camera's
perspective" rather than in raw world-space azimuth, which looks different
every time the user orbits:

```python
eye, center, up_v = v.camera.viewMatrix.getLookAt(1.0)  # NOT the inverse — see gotcha below
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

Always recompute the camera basis fresh, immediately before use — a basis
read even one call ago is stale if the user is actively orbiting between REPL
calls.

**Directional-light caveat:** there is no "point at X" for a sun-type light
(no position, no falloff) — the only lever is elevation, which changes *what
surfaces catch light*, not *where* it's aimed. Translate "point down at the
subject" into "increase the up-component, decrease the frontal component,"
not literal aiming.

### Gotchas specific to this technique

- **`Matrixd.getLookAt(distance)` operates on the view matrix directly, NOT
  its inverse.** Calling it on `osg.Matrix.inverse(v.camera.viewMatrix)`
  silently returns plausible-looking-but-wrong eye/center/up, no error.
- **`Vec3.dot()`/arithmetic require matching types** — a uniform's `.value`
  is often `Vec3f` while matrix math returns `Vec3d`; mixing raises
  `TypeError: incompatible function arguments`. Cast explicitly:
  `osg.Vec3d(v.x, v.y, v.z)`.
- **No `^` cross-product operator** — use `.cross()`.
- **`osg.setNotifyLevel` set too high floods the tmux pane** with X11 event
  spam. Fix: `osg.setNotifyLevel(osg.NotifySeverity.WARN)`.

## There is no `viewer.home()`

`osgViewer::ViewerBase`/`Viewer` has no `home()` in these bindings —
`viewer.cameraManipulator.home` exists but wants `(ea, aa)` event-handler args
not trivially available outside actual event dispatch. In practice this
doesn't matter: assigning `viewer.cameraManipulator = ...` *after*
`viewer.sceneData` is already set triggers the manipulator's own
`autoComputeHomePosition` framing automatically — no explicit home call
needed for the common "just frame the scene" case.
