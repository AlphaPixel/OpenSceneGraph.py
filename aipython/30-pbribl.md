# Reflective PBR/IBL for ordinary OSG geometry

`osgx.gltf.pbribl.PBRIBLScene.create()` is not limited to glTF-loaded nodes —
it works with an ordinary `osg.ShapeDrawable`, provided the drawable carries
an `osgx.Material` (see [`29-material.md`](29-material.md)) — a real
`StateAttribute` — so there's a real `osgx_gltf_Material` buffer for the
renderer to read. This file covers the environment-loading and IBL-scene
side. `PBRIBLEnvironment`/`PBRIBLScene` are classes with static factory
methods (`.load()`/`.prepare()`/`.create()`), not free functions.

## Minimal live REPL setup

```python
import osgx

sphere = osg.Sphere(osg.Vec3(0.0, 0.0, 0.0), 2.0)
drawable = osg.ShapeDrawable(sphere, osg.TessellationHints(detailRatio=2.0))
geode = osg.Geode(drawables=(drawable,))

material = osgx.Material()
material.baseColor = osg.Vec4(0.95, 0.55, 0.12, 1.0)
material.roughness = 0.12
material.metallic = 1.0
drawable.stateSet.attributes.append(material)

environment = osgx.gltf.pbribl.PBRIBLEnvironment.load(
	"/home/cubicool/dev/osgx/BUILD-g++-13.3.0-NOASAN/env/papermill.gltf",
)
pbr = osgx.gltf.pbribl.PBRIBLScene.create(
	geode, environment, iblDiffuseIntensity=1.0, iblSpecularIntensity=1.0
)

if not environment.valid() or not pbr.valid():
	raise RuntimeError("PBR/IBL setup failed")

root = osg.Group()

# The environment root is present when the manifest uses a built-in BRDF LUT.
if environment.root is not None:
	root.children.append(environment.root)

root.children.append(pbr.node)
viewer.sceneData = root
viewer.camera.clearColor = osg.Vec4(48.0 / 255.0, 53.0 / 255.0, 66.0 / 255.0, 1.0)
viewer.cameraManipulator = osgGA.TrackballManipulator()
```

## Use a pre-baked `osgx_pbribl` environment manifest

The `.gltf` files in `osgx`'s build `env/` directory are not ordinary scene
models: they carry the custom `osgx_pbribl` extension pointing at matching
pre-baked specular and diffuse KTX2 cubemaps beside the manifest. Load one
directly instead of preparing from HDR:

```python
environment = osgx.gltf.pbribl.PBRIBLEnvironment.load(
	"/home/cubicool/dev/osgx/BUILD-g++-13.3.0-NOASAN/env/papermill.gltf",
)

if not environment.valid():
	raise RuntimeError("failed to load PBR/IBL environment")
```

Use `PBRIBLEnvironment.prepare("environment.hdr", lutSize=1024)` only when
the entire environment should be baked dynamically from one HDR source — it
bakes diffuse irradiance, GGX-prefiltered specular, and the BRDF LUT live
from that one source; add `environment.root` to the rendered graph so its
`PRE_RENDER` passes can populate the generated textures. The helper is
IBL-only and does not invent authored/direct lights; generic light rigs are
`osgx` (see [`40-typed-lights-gizmos.md`](40-typed-lights-gizmos.md)),
and glTF-authored camera/`KHR_lights_punctual` support is separate loader
work.

### Switch a running scene

Given the `geode`/`viewer` variables from the setup above:

```python
environment = osgx.gltf.pbribl.PBRIBLEnvironment.load(
	"/home/cubicool/dev/osgx/BUILD-g++-13.3.0-NOASAN/env/Cannon_Exterior.gltf",
)

if not environment.valid():
	raise RuntimeError("failed to load PBR/IBL environment")

pbr = osgx.gltf.pbribl.PBRIBLScene.create(
	geode, environment, iblDiffuseIntensity=1.0, iblSpecularIntensity=1.0
)

if not pbr.valid():
	raise RuntimeError("failed to apply PBR/IBL environment")

root = osg.Group()

if environment.root is not None:
	root.children.append(environment.root)

root.children.append(pbr.node)
viewer.sceneData = root
```

Do not merely replace `environment.root`: `PBRIBLScene.create()` owns the
program state and its environment texture bindings, so call it again for the
new environment. The material attached to `drawable` does not need to be
rebuilt.

## Extra `PBRIBLScene.create()` options

`create(node, environment, iblDiffuseIntensity=1.0, iblSpecularIntensity=1.0,
diagnostics=False, shadowMap=None, hooks=[])`:

- `diagnostics=True` builds `pbr.debugMode` for switching between
  combined/diffuse/specular/normal/roughness/diffuse-IBL-only visualizations
  (`examples/pyosg-khronos-viewer.py`'s `Diagnostics` event handler cycles
  it with number keys).
- `shadowMap` accepts an `osgx.ShadowMap` (see
  [`10-rtt.md`](10-rtt.md)) to shadow the light at `LightSet` index
  `shadowMap.casterIndex`; omit it for unshadowed direct light.
- `hooks` is a plain list of `(osgx.Hook, osg.Shader)` pairs
  substituting one of this Program's built-in shader slots (`osgx.Hook.Skinning`,
  `osgx.Hook.Tonemap`). Each hook *replaces* the built-in definition (GLSL
  allows one body per function; adding a second is a link error, not an
  override) — `osgx.gltf.shader.SKINNING_HOOK_LINEAR_BLEND` (wrapped in
  `osgx.gltf.pbribl.resolveShaderLibs()`) enables real joint-matrix skinning
  in place of the identity-passthrough default.

There is also a deferred, G-buffer-split path for scenes with many lights —
`PBRIBLGBuffer.create(node, width, height)` (material-only geometry pass) →
`PBRIBLLightingScene.create(gbuffer, environment, mainCamera, ...)`
(lighting pass reading the G-buffer) — not covered in the minimal setup
above; reach for it only once a scene's light count/overdraw makes the
single-pass `PBRIBLScene` genuinely too expensive.

## Hand-assembled shader (no `osgx.Material`)

`osgx.Material` is the supported way to populate the material data (see
[`29-material.md`](29-material.md)) — it's a real `StateAttribute`, not
something worth hand-rolling. If assembling a shader by hand regardless, the
buffer is `#pragma osgx::gltf MATERIAL_INPUTS`'s `osgx_gltf_Material`: a
`std430` SSBO (`baseColorFactor` vec4, `roughnessFactor`, `metallicFactor`,
then four map-presence float flags), plus a separate `GLTFTextures`
sampler-struct uniform and `osgx_gltf_alphaMode`/`osgx_gltf_alphaCutoff`
uniforms for texture-backed materials. Sampler units and UV arrays must
follow `osgx.gltf.shader`'s glTF interface — at that point
`osgx.Material` is almost always the clearer path.

The Program and IBL textures attach to `geode`; the material attaches to
`drawable`. That split lets one PBR scene contain several drawables with
independent materials.

## Verify a live result

Do not use bare `Image.readPixels()` from the prompt. Queue the capture on
the REPL controller instead:

```python
await _osg_repl_controller.capture_framebuffer("/tmp/pbr-sphere.png")
```

The sphere should show the environment reflected across its surface.
Increase roughness toward `1.0` for a blurrier reflection; lower metallic
toward `0.0` for a dielectric surface with a diffuse IBL term.
