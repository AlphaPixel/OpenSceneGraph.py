# CPU depth readback for world-position reconstruction

The depth-flavored sibling of [`09-picking.md`](09-picking.md): instead of decoding an RGBA
pick ID, read back a raw depth sample at the cursor's pixel and turn it into a world-space
point via `osgx.unprojectPoint(camera, ndcX, ndcY, ndcDepth)` (`osgx/Projection.hpp`). A worked
example lives in `examples/pyosg-gbuffer.py`'s `AoECursorProbe`, against a real glTF model — the
motivating case is a decal on an arbitrary model surface via `osgx::GBuffer`.

Shape: a small fullscreen-quad camera copies the G-buffer's depth texture into its own
single-channel float attachment (`GL_RED`/`GL_FLOAT`, never `GL_RGBA8` — an 8-bit encode/decode
round-trip loses real precision `unprojectPoint()` needs), with a plain `osg.Image` also attached
for CPU readback (same SYNC mechanism as `osgx::PickReadbackSync` — one frame of latency, read
back from the update traversal one frame after render). `windowToNDC()` + that raw depth sample
feed `unprojectPoint()` directly; no linearization needed at all, unlike [`12-gbuffer.md`](12-gbuffer.md)'s
own depth-consumer guidance — `unprojectPoint()` wants the raw NDC depth exactly, not a distance.

## Depth textures must be sampled with `NEAREST`, never filtered

`osgx::GBuffer.create()` only documents attachment *format*, not sampling — the depth texture
is left at OSG's own `Texture2D` default (`LINEAR`, mipmapped) unless a caller overrides it.
Sampling a depth buffer with linear filtering blends two unrelated depth values together at
every edge (e.g. 0.3 and 1.0 average to a meaningless 0.65). Always set
`tex.filter = (osg.Texture.NEAREST, osg.Texture.NEAREST)` on any depth attachment used for
readback or unprojection.

This defect is static and per-frame-constant — a blur band a couple pixels wide at silhouette
edges that does not grow over time or change with mouse speed. A defect that IS
time/frame-dependent has a different cause; see the next section.

## FBO-targeted depth-copy quads need `GL_DEPTH_TEST` off

Same trap as [`10-rtt.md`](10-rtt.md): any fullscreen quad rendering into its own FBO (as
opposed to a composite/HUD pass drawing straight to the default framebuffer) must disable depth
test, or it renders correctly exactly once and then stops updating — every later readback
re-reads that one frozen frame's content regardless of camera movement. Because only the
*reconstructed point* tends to get inspected (not the raw buffer image), this presents as a
stale/out-of-sync matrix bug — the point matches wherever the camera was at the frame the
readback froze (e.g. correct at `home()`, wrong everywhere else) — rather than an obviously
frozen image. Fix: `quad.stateSet.modes[GL_DEPTH_TEST] = osg.StateAttribute.OFF`.

## Geometry positioned FROM a depth readback must not WRITE depth into the SAME pass

Any marker/gizmo repositioned each frame from a depth readback, and rendered into the SAME pass
whose depth gets read back, closes a feedback loop: frame N's readback repositions the marker ->
frame N+1 renders the marker into the shared depth texture at that pixel, at a depth that
differs slightly from the real surface (its own thickness, floating-point reconstruction noise)
-> the next readback picks up the marker's own depth instead of the model's, repositions it
again, slightly closer to the camera -> repeat.

Recognizable symptoms:
- Only appears once the cursor is over the model — off-model, the marker sits far away and
  never overlaps the sampled pixel.
- Converges over roughly 1-2 seconds to a "ceiling" that is actually the near clip plane. This
  is frame-count-based geometric convergence, not literally time-based, though at a steady frame
  rate it is indistinguishable from a time-based effect by eye.
- Moving the mouse fast masks it: a fast jump lands on a fresh, unpoisoned pixel, so that one
  readback is correct; slow motion keeps dwelling on pixels the marker already wrote into.

Fix: depth-test the marker against the real scene (so it still occludes correctly) but disable
depth *write* specifically — the same technique this project's `LightGizmos` overlay uses, for
the identical reason (an overlay must never corrupt the depth buffer a later pass depends on):

```python
geode.stateSet.attributes.append(osg.Depth(osg.Depth.LESS, 0.0, 1.0, False))  # test yes, write no
```

Generalizes: **any geometry whose position is derived from a depth (or G-buffer) readback, and
which is drawn into the same pass that readback samples, must disable depth write on itself.**
