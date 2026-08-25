# Fixed camera, no `osgGA.CameraManipulator` at all

Sibling to [`05-camera-manipulator.md`](05-camera-manipulator.md): that file
covers driving/customizing a manipulator; this one is a camera that should
never move (an orthographic front-on layout, a locked cinematic angle),
driven by directly assigning `viewer.camera.viewMatrix`/`projectionMatrix`
with no manipulator attached at all.

## Rule 1: `viewer.realize()` BEFORE setting view/projection, not after

```python
viewer = osgViewer.Viewer()
viewer.sceneData = root
viewer.realize()                              # FIRST

viewer.camera.viewMatrix = osg.Matrix.lookAt(eye, center, up)
viewer.camera.projectionMatrix = osg.Matrix.ortho(l, r, b, t, near, far)
```

Setting the projection matrix before `realize()`/the first `frame()` gets its
horizontal extent silently zeroed on the next frame:
`osg::Camera::ProjectionResizePolicy` (default `HORIZONTAL`) rescales the
projection against a "reference" viewport size that is wrong (effectively
unset) if a custom projection was assigned before the window had a real size.
An `ortho(-3, 3, -2, 2, 0.1, 100)` matrix's `element[0]` (`0.333`) goes to
`0.0` after one `frame()` call; vertical extent (`element[5]`) is untouched,
matching `HORIZONTAL`'s asymmetry. Once corrupted, nothing from that camera
renders — no diagnostic, just the clear color, indistinguishable from an
unrelated bug.

The reorder above is the real fix. No per-frame reassertion is needed once
ordered correctly — a correctly-ordered fixed camera should never need its
matrices touched again after setup; if a "reassert every frame" band-aid
feels necessary, that's a signal the ordering is still wrong, not a reason to
ship the band-aid.

`viewer.realize()` alone is enough, no full `frame()` needed first.

## Rule 2: disable automatic near/far unless you actually want it

`osg::Camera`'s default `computeNearFarMode` is
`COMPUTE_NEAR_FAR_USING_BOUNDING_VOLUMES` — it recomputes near/far from the
cull-visible scene bounds every frame, independent of whether a manipulator
is attached. This is a needless per-frame cost for a camera that never moves,
and a sharp edge for genuinely flat (zero-depth) geometry where the
recomputed range can be degenerate. Fix:

```python
viewer.camera.computeNearFarMode = osg.Camera.DO_NOT_COMPUTE_NEAR_FAR
```

## Rule 3: confining the camera to part of the window is not automatically viewport-aware everywhere

`viewer.camera.viewport = osg.Viewport(x, y, w, h)` works exactly as expected
for geometry — MVP-transformed vertex positions map into that sub-rectangle,
no extra setup needed. Two things are NOT automatically viewport-aware,
though:

- **`gl_FragCoord` in a fragment shader is WINDOW-absolute, not
  viewport-relative.** A shader that derives spatial patterns from
  `gl_FragCoord`/a resolution uniform samples a shifted, wrong region once the
  viewport's origin isn't `(0, 0)`. Don't patch this with a manual
  origin-correction uniform — don't depend on `gl_FragCoord` at all: derive
  the spatial domain from a vertex-shader `out` varying (object/world-space
  position) instead, which is genuinely view-independent. See
  `pyosg-noise.py`'s `VERTEX_SHADER`/`FRAGMENT_SHADER_NOISE` (`vPos`) for the
  pattern.
- **`osgx` needs the main camera's viewport origin subtracted from
  window-absolute mouse coordinates.** `PickReadback::setWindowOrigin(x, y)`
  (alongside `setWindowSize(w, h)`) is refreshed every frame by
  `PickCameraSync` from the live viewport; both the pick1x1 sub-frustum math
  and full-image CLICK-mode pixel mapping subtract it. Not Python-bound
  (driven automatically). If picking/hover looks offset by a consistent pixel
  amount after confining a camera's viewport, check whether the running osgx
  build has this fix (see the repo's `CLAUDE.md` on `PYOSG_OSGX_SOURCE_DIR`)
  before re-debugging from scratch. If instead picking triggers UNDER an
  ImGui panel, or hover sticks/flickers near one, that's a different bug —
  see [`09-picking.md`](09-picking.md).

## What a manipulator gives you that a fixed camera does not

Just initial framing, nothing else. `viewer.cameraManipulator = ...` after
`sceneData` is set auto-computes a reasonable home position from the scene
bounds (see [`05-camera-manipulator.md`](05-camera-manipulator.md)'s "There
is no `viewer.home()`"); a fixed camera has no equivalent, the view is
hand-computed. Rules 1–2 apply identically whether or not a manipulator is
attached; a manipulator doesn't make viewport-offset picking correct either —
that fix lives in `osgx` regardless of what drives the camera.
