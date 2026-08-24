# Render-to-texture and multi-camera scene graphs, built live

## `osg.Camera()` accepts the same kwargs constructor as `osg.Group`

`osg.Camera(children=(a, b), clearColor=..., renderOrder=..., viewport=...)`
works — `Camera`'s `kwargs_base` chain (`pyosg/pyosg.hpp`) runs through
`Transform` → `Group`, so `Group`'s `kwargs_init_own` (which handles
`children=`) applies to `Camera` too, on top of `Camera`'s own kwargs
(`viewport`, `clearColor`, `clearMask`, `projectionMatrix`, `viewMatrix`,
`renderOrder`, `graphicsContext`, `renderTargetImplementation`,
`allowEventFocus`, `computeNearFarMode`, `nearFarRatio`, draw callbacks —
see `pyosg/osg/Camera.cpp`). Building without kwargs is still fine:

```python
cam = osg.Camera()
cam.children.append(some_node)
```

## `Group.children.remove()`/`del`/`.pop()` work

`pyx::SequenceTraits<osg::Group>::del()` (`pyosg/osg/Group.hpp` →
`removeChild()`) backs `SequenceProxy`'s conditional deletable methods
(`remove`/`pop`/`del`/`clear`):

```python
rtt_cam.children.remove(model)  # works
```

If some OTHER `SequenceProxy`-backed container raises `AttributeError` on
`.remove()`/`.pop()`/`del container[i]`, that type's `SequenceTraits`
specialization likely doesn't implement `del()` yet — don't assume the whole
proxy mechanism is broken, check that one type's traits file first.

## PRE_RENDER RTT cameras need `referenceFrame = osg.Transform.ABSOLUTE_RF`

If an RTT camera has its own explicit `viewMatrix`/`projectionMatrix` (not
meant to inherit the parent's transform — the normal case for an offscreen
"render this from a fixed angle" pass), set:

```python
rtt_cam.referenceFrame = osg.Transform.ABSOLUTE_RF
```

Without this, the RTT camera's own `viewMatrix` (typically a `lookAt` matrix
with the eye far from the origin) gets composed into the *parent scene's
bound computation* — `osg::Camera` IS-A `osg::Transform`, and by default
(`RELATIVE_RF`) a Transform's matrix is applied to its children's bounds when
computing the parent's overall bound, exactly like `osg::MatrixTransform`.
This silently produces a wildly wrong combined scene bound, and
`TrackballManipulator`'s "home" framing ends up looking at nothing — the
symptom is a screenshot/window that's just solid black or shows nothing
recognizable, with nothing else actually broken. Confirm by checking
`root.bound` before/after setting `ABSOLUTE_RF`: it should snap to a sane
bound matching your *visible* geometry, not something enormous or offset.

Any RTT/shadow-style camera with its own independent view should be
`ABSOLUTE_RF` (matches `osgx::shadow::ShadowMap::create()`, `~/dev/osgx/src/Shadow.cpp`,
which sets it on its own `camera` — the Lighting Series' `08-shadows.py` builds
its shadow pass via `osgx.shadow.ShadowMap.create()` rather than a hand-rolled
`osg.Camera()`).

## A fullscreen-quad pass re-targeted to an FBO renders a single flat color

A fullscreen-quad camera (`ABSOLUTE_RF`, identity view/projection: composite,
SSAO, bloom, deferred lighting) must own its own depth state:

```python
cam.stateSet.modes[GL_DEPTH_TEST] = osg.StateAttribute.OFF
```

Without it, such a pass works only by accident while it draws to the
backbuffer — the main camera clears depth to 1.0 every frame, so the quad
happens to pass `GL_LESS`. Re-target that same camera to an FBO
(`renderOrder = PRE_RENDER` + `attach()`) and OSG attaches an implicit depth
renderbuffer that a color-only `clearMask` never clears. Undefined depth,
every fragment discarded, and the attachment keeps only its clear color.

The failure is silent: the FBO is valid, the viewport is right, the draw
call is issued, no GL errors — reads exactly like a broken shader.

> "It renders fine today" is not evidence a pass owns its depth state — only
> that something else cleared depth for it. Every backbuffer-only fullscreen
> pass is a latent instance of this bug; re-targeting is what exposes it.

### Diagnosing a pass that outputs one flat color

1. **Dump the texture and count distinct colors** rather than judging by
   eye — a "flat gray" that's exactly the *master camera's* clear color
   repeated proves you're looking at another framebuffer's contents:

   ```python
   from PIL import Image
   from collections import Counter
   px = list(Image.open("dump.png").convert("RGB").getdata())
   print(len(set(px)), Counter(px).most_common(5))
   ```

2. **Set a deliberately absurd clear color** (magenta) on the suspect camera
   — separates "FBO live but nothing drew," "never rendered," and "shaded to
   black," which are indistinguishable at the default black.

3. **Probe from a draw callback on the pass's own geometry** — proves
   whether the draw happens at all, and whether an FBO is really bound:

   ```python
   # GL_DRAW_FRAMEBUFFER_BINDING == 0x8CA6; 0 means the DEFAULT framebuffer
   ```

4. **Add a temporary flag/toggle to a known-good example** instead of
   writing a fresh repro, so the A/B differs by exactly one variable in one
   binary.

### A debug blit must not disable the camera that writes the texture

A "visualize mode" that `nodeMask`s off a pass and then blits that pass's own
RTT output samples an attachment nothing rendered into this frame —
undefined, spatially uniform, unaffected by camera movement. That looks
exactly like a broken render pass and is purely a broken instrument. Toggle
only cameras that draw to the **backbuffer**; leave every `PRE_RENDER`/FBO
stage running in all modes.

## Z-up convention: a quad grid built in the XY plane is invisible

This project's examples default to Z-up (`up = (0, 0, 1)` in `lookAt` calls,
matching `TrackballManipulator`'s default framing along `-Y`). A
fullscreen/instanced quad grid whose vertex shader writes `vec4(x, y, z, 1.0)`
with the 2D grid spread across `x`/`y` and depth along `z` lies in the **XY
plane** — edge-on to the default camera view, reading as a thin,
nearly-invisible line.

Build the grid in **X/Z**, with the explode-depth axis on **Y**:

```glsl
// WRONG for this project's Z-up default framing:
gl_Position = osg_ModelViewProjectionMatrix * vec4(gridX, gridY, depth, 1.0);

// RIGHT:
gl_Position = osg_ModelViewProjectionMatrix * vec4(gridX, -depth, gridZ, 1.0);
```

## Verified-working RTT setup shape (`pyosg-rtt.py`)

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
# If this camera has its own explicit view — see ABSOLUTE_RF note above:
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
conversion), do not overwrite `.matrix` directly to animate it — that
destroys the conversion. Check first:

```python
print(model.matrix)  # if this isn't identity, it's doing real work
```

Wrap it in a new transform dedicated to the animation instead:

```python
spin_xform = osg.MatrixTransform()
spin_xform.children.append(model)
# parent.children.append(spin_xform), not model directly
spin_xform.updateCallback = lambda node, nv, osg=osg: setattr(
    node, "matrix", osg.Matrix.rotate(nv.frameStamp.simulationTime * 0.4, osg.Vec3(0, 0, 1))
)
```

(See [`01-core.md`](01-core.md) rule 2 for why `osg=osg` is required here.)
