# Multiple render targets, depth, and pass timing

`pyosg-mrt.py` proves one geometry pass writing multiple color attachments;
`pyosg-guided-blur.py` builds on that with normal/depth-guided post-processing.
Read this before treating a G-buffer depth texture as a simple linear distance
field.

## Raw depth is correct, but it is not linear distance

Attach depth normally and let the geometry pass write it through the ordinary
depth test:

```python
cam.attach(osg.Camera.COLOR_BUFFER0, paint_tex)
cam.attach(osg.Camera.COLOR_BUFFER1, normal_tex)
cam.attach(osg.Camera.DEPTH_BUFFER, depth_tex)
```

The sampled `depth_tex` value is post-projection depth. It is excellent for
visibility and has most precision near the camera, but comparing two samples
as though `abs(a - b)` were a world-space distance gives depth-dependent
results. A post-process needs the near/far parameters from the *same effective
projection* that wrote the texture:

```glsl
float linearizeDepth(float d, float znear, float zfar) {
	float z = d * 2.0 - 1.0;
	return (2.0 * znear * zfar) / (zfar + znear - z * (zfar - znear));
}
```

The raw-depth display may be nearly white; that is normal perspective-depth
distribution, not proof the attachment is empty. Always expose both a raw
depth debug view and a linear-depth debug view while bringing up a pass.

## OSG's nominal camera projection is not necessarily the depth projection

`viewer.camera.projectionMatrix` commonly remains the nominal lens (for
example `0.1 - 1000`), while cull traversal tightens the actual projection
used for a camera pass to improve depth precision. Do not use the nominal
matrix to linearize an RTT depth texture when the pass uses OSG's automatic
near/far computation.

The reliable observation point is the depth-writing camera's **post-draw**
callback: its `RenderInfo::State` still holds the cull-adjusted projection,
and later render-order passes can consume uniforms updated there. Pre-draw is
too early; its state can still be the preceding pass's projection.

```python
def update_depth_parameters(ri):
	_fovy, _aspect, near, far = ri.state.projectionMatrix.getPerspective()
	composite.stateSet.uniforms["znear"] = float(near)
	composite.stateSet.uniforms["zfar"] = float(far)

gbuffer_cam.postDrawCallback = update_depth_parameters
```

For a later guided blur, use a relative difference so the control has a stable
meaning across distance:

```glsl
float delta = abs(zCenter - zSample) / max(zCenter, 0.001);
float depthWeight = exp(-delta * depthRejection);
```

Use the same continuous shape for normal rejection. `pow(dot(N0, N1),
strength)` has a misleading zero special case: any positive strength rejects a
perpendicular sample completely, making `0` look like a binary mode switch.
This bilateral form makes strength zero genuinely disable the guide and raises
rejection smoothly:

```glsl
float normalDifference = 1.0 - clamp(dot(centerNormal, sampleNormal), 0.0, 1.0);
float normalWeight = exp(-normalDifference * normalRejection);
```

## Draw callback slots have one owner

`osg::Camera` has one pre-draw and one post-draw callback slot. Assigning
`camera.preDrawCallback = other` replaces the existing callback; it does not
append or compose it. `osgx.imgui.Widget` installs its own `PreDraw` and
`PostDraw` callbacks on its configured draw camera during initialization, so
installing another callback on that same camera before constructing the Widget
silently loses it (and releases the replaced callback immediately).

Use `osgx.CallbackGroup` when multiple systems must share a draw slot, or put
a pass-specific callback on the pass camera instead. In the guided-blur
example, the G-buffer camera's post-draw callback is the better location: it
cannot collide with the Widget's composite-camera callbacks and it sees the
right projection at the right time.

## G-buffer debugging order

When a depth-aware pass looks wrong, establish these facts in order:

1. The raw depth attachment changes with the scene (`depthTex` debug view).
2. The live `znear`/`zfar` values are not constructor defaults.
3. Linearized depth has visible structure before tuning any rejection slider.
4. With normal rejection at zero, depth rejection alone changes overlap/layer
   behavior; then test normal rejection independently.

Do not node-mask the G-buffer camera to inspect a later pass: its texture then
contains no current-frame data. Keep every producer pass running and switch
only the final backbuffer composite's display mode.
