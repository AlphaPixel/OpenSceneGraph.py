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

## A fullscreen-quad pass re-targeted to an FBO renders a single flat color

Confirmed 2026-08-20, the second time this exact root cause cost a session
(see also `feedback_fullscreen_quad_depth_test` -- the first variant showed up
as "correct for frame 0, solid black forever after").

A fullscreen-quad camera (`ABSOLUTE_RF`, identity view/projection: composite,
SSAO, bloom, deferred lighting) **must own its own depth state**:

```python
cam.stateSet.modes[GL_DEPTH_TEST] = osg.StateAttribute.OFF
```

Without it, such a pass works **only by accident while it draws to the
backbuffer** -- the main camera clears depth to 1.0 every frame, so the quad
happens to pass `GL_LESS`. Re-target that same camera to an FBO
(`renderOrder = PRE_RENDER` + `attach()`, which is what you must do the moment
anything downstream needs its output as a *texture*) and OSG attaches an
**implicit depth renderbuffer** that a color-only `clearMask` never clears.
Undefined depth, every fragment discarded, and the attachment keeps nothing
but its clear color.

The failure is silent and misleading: the FBO is valid, the viewport is right,
the draw call is issued, no GL errors. It reads as a broken shader, and you
will debug the shader for hours.

> **"It renders fine today" is not evidence a pass owns its depth state** --
> only that something else cleared depth for it. Every backbuffer-only
> fullscreen pass is a latent instance of this bug; re-targeting is what
> exposes it.

### Diagnosing a pass that outputs one flat color

Generalizes past this bug -- this sequence beat several rounds of reading and
hypothesizing:

1. **Dump the texture and count distinct colors** rather than judging by eye.
   "Flat gray" turned out to be exactly `(48,53,66)` x 1024000 -- precisely the
   *master camera's* clear color, which is what proved we were looking at
   another framebuffer's contents rather than bad shading. (After the fix:
   1797 distinct colors.)

   ```python
   from PIL import Image
   from collections import Counter
   px = list(Image.open("dump.png").convert("RGB").getdata())
   print(len(set(px)), Counter(px).most_common(5))
   ```

2. **Set a deliberately absurd clear color** (magenta) on the suspect camera.
   At the default black, "FBO live but nothing drew", "never rendered", and
   "shaded to black" are indistinguishable; magenta separates all three.

3. **Probe from a draw callback on the pass's own geometry** -- proves in one
   run whether the draw happens at all, and whether an FBO is really bound or
   OSG silently fell back to the default framebuffer:

   ```python
   # GL_DRAW_FRAMEBUFFER_BINDING == 0x8CA6; 0 means the DEFAULT framebuffer
   ```

4. **Add a flag to a known-good example** instead of writing a fresh repro, so
   the A/B differs by exactly one variable inside one binary
   (`osgx-gbuffer --rtt` is the worked example).

### A debug blit must not disable the camera that writes the texture

A "visualize mode" that `nodeMask`s off a pass and then blits that pass's own
RTT output samples an attachment nothing rendered into this frame -- undefined,
spatially uniform, unaffected by camera movement. That looks *exactly* like a
broken render pass, and it is purely a broken instrument. Toggle only the
cameras that draw to the **backbuffer**; leave every `PRE_RENDER`/FBO stage
running in all modes.

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
