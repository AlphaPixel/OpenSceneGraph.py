# Reflective PBR/IBL for ordinary OSG geometry

`osgx.gltf.pbribl.createPBRIBLScene()` is not limited to glTF-loaded nodes.
It works with an ordinary `osg.ShapeDrawable`, provided the drawable supplies
the small glTF-material interface the renderer expects: a material UBO and
its two alpha uniforms.

This was verified live on 2026-08-06 with a `Sphere`/`ShapeDrawable`, a
metallic gold material, and the pre-baked Papermill environment. The captured
frame showed a clear indoor environment reflection.

## Minimal live REPL setup

Start from the empty `examples/pyosg_repl.py` session. Before sending a
multi-line block through tmux, run `%autoindent off`; see `01-core.md`.

```python
import osgx

osg.DisplaySettings.instance.numMultiSamples = 8

hints = osg.TessellationHints()
hints.detailRatio = 2.0

sphere = osg.Sphere(osg.Vec3(0.0, 0.0, 0.0), 2.0)
drawable = osg.ShapeDrawable(sphere, hints)
geode = osg.Geode(drawables=(drawable,))

# std140 osgGLTF_Material layout:
# baseColor RGBA, roughness, metallic, then four texture-presence flags,
# then two padding floats. All flags are zero because this is factor-only.
material_data = osg.FloatArray([
	0.95, 0.55, 0.12, 1.0,
	0.12, 1.0,
	0.0, 0.0, 0.0, 0.0,
	0.0, 0.0,
])
material_data.bufferObject = osg.UniformBufferObject()

drawable.stateSet.setAttributeAndModes(
	osg.UniformBufferBinding(0, material_data, 0, material_data.totalDataSize),
	osg.StateAttribute.ON,
)
drawable.stateSet.uniforms["osgGLTF_alphaMode"] = 0.0
drawable.stateSet.uniforms["osgGLTF_alphaCutoff"] = 0.5

environment = osgx.gltf.pbribl.loadPBRIBLEnvironment(
	"/home/cubicool/dev/osgx/BUILD-g++-13.3.0-NOASAN/env/papermill.gltf",
)
pbr = osgx.gltf.pbribl.createPBRIBLScene(
	geode,
	environment,
	iblIntensity=1.0,
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

The manifest references its matching pre-baked specular and diffuse KTX2
cubemaps. Use `preparePBRIBLEnvironment("environment.hdr")` only when the
entire environment should be baked dynamically from one HDR source.

## Use a pre-baked `osgx_pbribl` environment manifest

The `.gltf` files in `osgx`'s build `env/` directory are not ordinary scene
models: they are small manifests carrying the custom `osgx_pbribl` extension.
They point at the matching pre-baked specular and diffuse KTX2 cubemaps beside
the manifest. Load one directly instead of preparing from HDR:

```python
environment = osgx.gltf.pbribl.loadPBRIBLEnvironment(
	"/home/cubicool/dev/osgx/BUILD-g++-13.3.0-NOASAN/env/papermill.gltf",
)

if not environment.valid():
	raise RuntimeError("failed to load PBR/IBL environment")
```

This path was verified live with `papermill.gltf` on 2026-08-06. It printed
`loaded pre-baked environment manifest`, and the resulting sphere reflected
Papermill's bright indoor lighting. The manifest's built-in BRDF-LUT is still
created by the environment root; include that root in the rendered graph as
normal.

### Switch a running scene

Given the `geode`, `viewer`, and `osgx` variables from the setup above, this
reapplies the renderer with the new textures and replaces the rendered root:

```python
environment = osgx.gltf.pbribl.loadPBRIBLEnvironment(
	"/home/cubicool/dev/osgx/BUILD-g++-13.3.0-NOASAN/env/Cannon_Exterior.gltf",
)

if not environment.valid():
	raise RuntimeError("failed to load PBR/IBL environment")

pbr = osgx.gltf.pbribl.createPBRIBLScene(
	geode,
	environment,
	iblIntensity=1.0,
)

if not pbr.valid():
	raise RuntimeError("failed to apply PBR/IBL environment")

root = osg.Group()

if environment.root is not None:
	root.children.append(environment.root)

root.children.append(pbr.node)
viewer.sceneData = root
```

Do not merely replace `environment.root`: `createPBRIBLScene()` owns the
program state and its environment texture bindings, so call it again for the
new environment. The material UBO remains on `drawable` and does not need to
be rebuilt.

## Material values

The 12-float UBO is exactly the `osgGLTF_Material` std140 block expected by
the one-call shader:

| Float range | Meaning |
|---|---|
| `0:4` | `baseColorFactor` RGBA |
| `4` | `roughnessFactor` (`0.12` is strongly reflective) |
| `5` | `metallicFactor` (`1.0` is metal) |
| `6:10` | Base-color, metallic-roughness, occlusion, and normal-map flags |
| `10:12` | Required std140 padding |

For a texture-free material, leave the four flags at `0.0`; the renderer then
uses the color, roughness, and metallic factors directly. To add textures,
the relevant sampler units and UV arrays must also follow `osgx.gltf.shader`'s
glTF interface, so a hand-assembled shader is usually the clearer path.

The Program and IBL textures attach to `geode`; the material UBO attaches to
`drawable`. That split lets one PBR scene contain several drawables with
independent factor-only materials.

## Verify a live result

Do not use bare `Image.readPixels()` from the prompt. Queue the capture on
the REPL controller instead:

```python
await _osg_repl_controller.capture_framebuffer("/tmp/pbr-sphere.png")
```

The sphere should show the environment reflected across its surface. Increase
roughness (float 4) toward `1.0` for a blurrier reflection; lower metallic
(float 5) toward `0.0` for a dielectric surface with a diffuse IBL term.
