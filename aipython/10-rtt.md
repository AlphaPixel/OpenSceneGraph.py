# Render-to-texture and multi-camera scene graphs, built live

Confirmed 2026-07-20 building a live "render model to texture, explode into
an instanced tile grid" effect entirely through a tmux `aipython` session.

## `osg.Camera()` has no `children=` constructor kwarg

Unlike `osg.Group`/`osg.Geode`, which support `Group(children=(a, b))`,
`osg.Camera()` only supports the zero-arg constructor:

```python
# BROKEN
cam = osg.Camera(children=(some_node,))
# TypeError: __init__(): incompatible constructor arguments.
# The following argument types are supported:
#     1. OpenSceneGraph.osg.Camera()

# WORKS
cam = osg.Camera()
cam.children.append(some_node)
```

## `Group.children` (and likely other `SequenceProxy`-backed containers) is currently append-only

`.append()`/`.extend()` exist; `.remove()`, `del container[i]`, and `.pop()`
do **not** yet:

```python
rtt_cam.children.remove(model)
# AttributeError: 'OpenSceneGraph.osg._Children' object has no attribute 'remove'
```

If a node needs to move to a different parent, don't try to remove-then-append
in place -- build a *fresh* replacement parent (new `Camera`/`Group`) with
only the children you actually want, and swap the whole thing into place via
its own parent's `.append()` (or by reassigning `viewer.sceneData` if it's
the scene root). This is more `osg.Camera()` construction boilerplate than
you'd expect, but it's the reliable path today. Worth a real binding fix
later -- flag if hit again.

## PRE_RENDER RTT cameras need `referenceFrame = osg.Transform.ABSOLUTE_RF`

If an RTT camera has its own explicit `viewMatrix`/`projectionMatrix` (i.e.
it's not meant to inherit the parent's transform, the normal case for an
offscreen "render this from a fixed angle" pass), set:

```python
rtt_cam.referenceFrame = osg.Transform.ABSOLUTE_RF
```

**Without this, the RTT camera's own `viewMatrix` (typically a `lookAt`
matrix with the eye far from the origin) gets composed into the *parent
scene's bound computation*** -- since `osg::Camera` IS-A `osg::Transform`,
and by default (`RELATIVE_RF`) a Transform's matrix is applied to its
children's bounds when computing the parent's overall bound, exactly like an
`osg::MatrixTransform`. This silently produces a wildly wrong combined scene
bound, and `TrackballManipulator`'s "home" framing ends up looking at nothing
-- the symptom is a screenshot/window that's just solid black (or shows
nothing recognizable), even though nothing else is actually broken. Confirm
by checking `root.bound` before and after setting `ABSOLUTE_RF`: it should
snap to a sane, origin-ish bound matching your *visible* geometry's own
bound, not something enormous or oddly offset.

This matches the same pattern shadow-map cameras in the Lighting Series use
(`08-shadows.py`'s `shadow_cam`) -- any RTT/shadow-style camera with its own
independent view should be `ABSOLUTE_RF`.

## Z-up convention: a quad grid built in the XY plane is invisible

This project's examples default to Z-up (`up = (0, 0, 1)` in `lookAt` calls,
matching `TrackballManipulator`'s default framing which looks roughly along
`-Y`). A fullscreen/instanced quad grid whose vertex shader writes
`vec4(x, y, z, 1.0)` with the 2D grid spread across `x`/`y` and depth along
`z` lies in the **XY plane** -- which, under this convention, is edge-on to
the default camera view and reads as a thin, nearly-invisible line rather
than a visible flat surface.

Build the grid in **X/Z**, with the "into/out of the screen" explode-depth
axis on **Y** instead:

```glsl
// WRONG for this project's Z-up default framing:
gl_Position = osg_ModelViewProjectionMatrix * vec4(gridX, gridY, depth, 1.0);

// RIGHT:
gl_Position = osg_ModelViewProjectionMatrix * vec4(gridX, -depth, gridZ, 1.0);
```

## Verified-working RTT setup shape (from `pyosg-rtt.py`)

```python
cb = osg.Texture2D()
cb.size = (w, h)
cb.internalFormat = GL_RGBA
cb.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)

db = osg.Texture2D()
db.size = (w, h)
db.internalFormat = GL_DEPTH_COMPONENT24
db.sourceFormat = GL_DEPTH_COMPONENT
db.sourceType = GL_FLOAT
db.filter = (osg.Texture.NEAREST, osg.Texture.NEAREST)

cam = osg.Camera()
cam.renderOrder = osg.Camera.PRE_RENDER
cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
cam.clearMask = GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT
cam.clearColor = osg.Vec4(0.1, 0.1, 0.1, 1.0)
cam.viewport = osg.Viewport(0, 0, w, h)
cam.attach(osg.Camera.COLOR_BUFFER, cb)
cam.attach(osg.Camera.DEPTH_BUFFER, db)
# If this camera has its own explicit view -- see ABSOLUTE_RF note above:
cam.referenceFrame = osg.Transform.ABSOLUTE_RF
cam.viewMatrix = osg.Matrix.lookAt(eye, center, osg.Vec3(0, 0, 1))
cam.projectionMatrix = osg.Matrix.perspective(40.0, aspect, near, far)
```

A downstream drawable samples `cb` as an ordinary texture:

```python
stateSet.textureAttributes[0] = cb
stateSet.uniforms["someTexUniform"] = 0  # texture UNIT index, not the texture object
```

## Reparenting a node without disturbing its own transform

If a loaded model (e.g. from glTF) is already an `osg.MatrixTransform`
holding a real, load-bearing matrix (commonly a Y-up-to-Z-up axis
conversion), do **not** overwrite `.matrix` directly to animate it -- that
destroys the conversion. Check first:

```python
print(model.matrix)  # if this isn't identity, it's doing real work
```

Wrap it in a **new** transform dedicated to the animation instead:

```python
spin_xform = osg.MatrixTransform()
spin_xform.children.append(model)
# parent.children.append(spin_xform), not model directly
spin_xform.updateCallback = lambda node, nv, osg=osg: setattr(
    node, "matrix", osg.Matrix.rotate(nv.frameStamp.simulationTime * 0.4, osg.Vec3(0, 0, 1))
)
```

(See [`01-core.md`](01-core.md) rule 2 for why `osg=osg` is required here,
not optional style.)
