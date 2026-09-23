# G-buffer contracts and deferred composition

A G-buffer is a geometry pass that stores reusable per-visible-pixel data for
later passes. It is not inherently PBR, IBL, glTF, or lighting: normal/depth
guided blur, outlines, SSAO, watercolor diffusion, and deferred lighting can
all consume the same kind of attachments.

## The two main modes

[`examples/pyosg-gbuffer.py`](../examples/pyosg-gbuffer.py) demonstrates the
two supported shapes. Pick one deliberately; do not start by hand-assembling
an FBO camera.

1. **Generic, no implicit lighting**: `osgx.GBuffer.create(node, width,
   height, formats)` owns an `osgx.RTT` PRE_RENDER geometry pass, color
   attachments, and native depth. Its public `gbuffer.camera` field is typed
   as `osg.Camera`, but its concrete implementation is `osgx.RTT`; add that
   field to the scene graph, rather than constructing a replacement camera.
   The caller owns the Program and attachment meaning. The example's default
   mode writes raw RGBA color and has no PBR, IBL, glTF, or fallback-lighting
   contract.
2. **Deferred PBR/IBL**:
   `osgx.gltf.pbribl.PBRIBLGBuffer.create(node, width, height)` is the
   specialized wrapper around `osgx.GBuffer`. It owns the same RTT geometry
   pass but writes the fixed PBR material layout. Feed it to
   `PBRIBLLightingScene.create(gbuffer, environment, mainCamera, ...)` for
   the terminal fullscreen PBR/IBL pass. The example selects this path when
   `--env manifest.gltf` or `--hdr environment.hdr` is present; with neither,
   it demonstrates the generic path. This path's shaders require the
   example's GL 4.6 context; generic G-buffer work may use a lower version
   when its own shaders and attachment formats permit it.

In both modes, a camera that merely samples an RTT texture and draws to the
real backbuffer remains a plain POST_RENDER `osg.Camera`. That is not a
missing use of `osgx.RTT`: RTT means a pass *writes an FBO attachment*, not
any camera participating in a multi-pass scene.

Add a generic attachment only when a consumer needs it. For example, SSAO
needs view-space normal and position attachments, while a depth-only consumer
can use `gbuffer.depthTexture` directly.

## Generic G-buffer versus PBRIBL

`GBuffer.create()` is deliberately neutral: it creates the RTT camera,
attachments, and depth texture, but it does not choose a shader or lighting
model. The skeleton supplies a tiny Program whose fragment shader writes raw
color and contains no lighting calculation; that is why its shapes are
flat-colored. OSG fallback behavior is separate and depends on the active
render state/context, so do not use it as this pipeline's lighting contract.

`osgx.gltf.pbribl` offers two different PBR/IBL conveniences:

- `PBRIBLScene.create(node, environment)` is the forward path: one shader on
  geometry calculates PBR/IBL lighting directly.
- `PBRIBLGBuffer.create(node, width, height)` is the specialized deferred
  path: its geometry pass stores glTF material data in a fixed multi-attachment
  layout, still without lighting. Feed it to
  `PBRIBLLightingScene.create(...)` for the fullscreen lighting pass.

`PBRIBLScene.create()` is forward PBR/IBL, not a G-buffer mode. Use it when a
single geometry shader is sufficient. Use `PBRIBLGBuffer` plus
`PBRIBLLightingScene` when the scene specifically needs deferred PBR/IBL or
its G-buffer seams. See [`30-pbribl.md`](30-pbribl.md).

## Keep stored data canonical; derive interpretations in consumers

Store the native depth attachment as raw depth. A consumer that needs linear
camera distance should request the camera depth parameters and linearize it;
one needing a full view-space position can reconstruct it from depth plus an
inverse projection, or use a deliberately stored position attachment. This
keeps `osgx::GBuffer` neutral and lets each pass choose the representation its
algorithm actually needs.

Likewise, normals are a geometric guide rather than an outline instruction.
A guided blur can compare `dot(centerNormal, sampleNormal)` to preserve a
crease, while an NPR edge pass can turn that same difference into an ink line.

## Minimal useful layout

The smallest general deferred/post-process layout is often:

```text
COLOR_BUFFER0  paint/albedo/working color
COLOR_BUFFER1  view-space normal
DEPTH_BUFFER   native visibility depth
```

Add attachments only for a demonstrated consumer: material factors for
deferred PBR, emissive data for lighting, position for algorithms where
reconstruction is inconvenient or too imprecise, IDs for picking, and so on.
`pyosg-mrt.py` proves simultaneous color writes; `pyosg-guided-blur.py` proves
the first downstream normal/depth-aware pass.

## Deferred pipeline shape

```text
geometry -> G-buffer attachments
G-buffer -> one or more RTT post-process passes
all results -> final POST_RENDER composite/debug display
```

Every RTT producer must remain enabled while a later pass samples it. Debug
by changing the final composite output, not by disabling the producer whose
texture you are trying to inspect. For depth timing and callback ownership,
read [`11-mrt.md`](11-mrt.md).
