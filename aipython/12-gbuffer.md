# G-buffer contracts and deferred composition

A G-buffer is a geometry pass that stores reusable per-visible-pixel data for
later passes. It is not inherently PBR, IBL, glTF, or lighting: normal/depth
guided blur, outlines, SSAO, watercolor diffusion, and deferred lighting can
all consume the same kind of attachments.

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
