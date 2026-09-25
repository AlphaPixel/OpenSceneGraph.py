# Composing osgx::gltf materials with generic osgx lighting

`osgx::gltf` (formerly a separate `osgGLTF` module/repo, merged into `osgx.gltf` — there is
no `osgGLTF` Python module) is the glTF loader plus its optional PBR/IBL adapter. The ownership
boundary is:

- The loader produces only generic osgx data: materials are plain `osgx.Material`s, and tangents
  and joint indices/weights go to the generic attribute locations `osgx.TANGENT_ATTRIBUTE`,
  `osgx.JOINT_INDICES_ATTRIBUTE`, `osgx.JOINT_WEIGHTS_ATTRIBUTE` (`osgx.bindMeshAttributes()`).
- `osgx.PBRScene` is the forward renderer; `osgx.gltf` provides the `osgx_environment` manifest
  loader `loadEnvironment()` and `KHRONOS_ENVIRONMENT_ROTATION`.
- `osgx.PBRGBuffer`/`osgx.PBRLightingPass` are the deferred renderer; custom lighting shaders read
  the G-buffer through the `osgx::gbuffer` catalog.
- `osgx.resolveShaderLibs()` expands every catalog the live `osgx.Library` registered
  (`osgx::pbr`, `osgx::light`, `osgx::environment`, `osgx::ibl`, `osgx::shadow`,
  `osgx::skinning`, `osgx::gbuffer`, ...).

Create the Library (`lib = osgx.initialize()`) before resolving a hand-assembled shader; it
registers every catalog:

```python
import osgx

lib = osgx.initialize()

fragment_source = """
#version 460 core

const float PI = 3.14159265359;

#pragma osgx::pbr MATERIAL_STRUCT, MATERIAL_INPUTS, GET_MATERIAL, GET_SHADING_NORMAL, GET_EMISSIVE, GET_ALPHA
#pragma osgx::ibl HEMISPHERE_AMBIENT

// application-specific lighting and main()
"""

fragment_shader = osgx.resolveShaderLibs(fragment_source)
```

Catalog and library names are case-insensitive. Unknown entries in a registered namespace fail
immediately; unrelated pragmas remain intact for OSG or other tooling.

## Required program and StateSet setup

Custom renderers should use `osgx.bindMeshAttributes()` rather than repeat the tangent/skinning
attribute locations:

```python
program = osg.Program(shaders=(
	osg.Shader(osg.Shader.VERTEX, vertex_source),
	osg.Shader(osg.Shader.FRAGMENT, fragment_shader),
))

state_set = model.stateSet
osgx.bindMeshAttributes(program)
state_set.setAttributeAndModes(
	program,
	osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE,
)
```

`osgx.bindMeshAttributes()` binds tangent and skin attributes to the locations populated by the loader.
Material data needs no setup: every glTF material is an `osgx.Material`, read with
`#pragma osgx::pbr MATERIAL_INPUTS, GET_MATERIAL`, and its samplers declare their own texture units.
The loader owns the material data; the application still owns its renderer and Program.

`examples/pyosg-voxelize2d.py` is a complete hand-assembled fallback example (its
`PBR_FALLBACK_FRAGMENT_SHADER`).

## GLSL dependency gotcha

Some generic PBR snippets reference a caller-owned `PI`. Because pragma expansion is literal and
ordered, declare it before the pragma:

```glsl
const float PI = 3.14159265359;
#pragma osgx::pbr D_GGX, G_SCHLICK, G_SMITH
```

## Direct-light gotcha

`osgx_DirectSpecular()` already includes its `NdotL` factor. Apply `NdotL` to the separate Lambert
diffuse term, not to the combined diffuse-plus-specular result:

```glsl
float NdotL = max(dot(N, L), 0.0);
vec3 diffuse = kD * mat.albedo / PI * NdotL;
vec3 specular = osgx_DirectSpecular(N, V, L, NdotV, mat.roughness, mat.F0);
Lo += (diffuse + specular) * lightColor[i] * attenuation;
```

## One-call PBR/IBL renderer

For a pre-baked environment, load its `osgx_environment` manifest as an `osgx.Environment` and use
`osgx.PBRScene` (see [`30-pbr.md`](30-pbr.md) for the full API, including the
shadow/skinning/tonemap `hooks` options and the deferred G-buffer variant for many-light scenes):

```python
model = osgDB.readNodeFile("scene.gltf")
environment = osgx.gltf.loadEnvironment("papermill.gltf")

if environment is None:
	raise RuntimeError("failed to load PBR/IBL environment")

scene = osgx.PBRScene.create(model, osgx.PBRSceneOptions(environment=environment))

if not scene.valid():
	raise RuntimeError("PBR/IBL setup failed")

root = osg.Group()

if environment.bakeRoot is not None:
	root.children.append(environment.bakeRoot)

root.children.append(scene.node)
```

`environment.bakeRoot` must participate in the rendered scene graph when it is not `None`. For a
fully dynamic setup, build `osgx.Environment(osgDB.readImageFile("environment.hdr"))` and set its
`rotation` to `osgx.gltf.KHRONOS_ENVIRONMENT_ROTATION`; it bakes specular, diffuse, and the
BRDF LUT from that one source. The helper is IBL-only and does not
invent authored/direct lights. Generic light rigs remain in `osgx` (see
[`40-typed-lights-gizmos.md`](40-typed-lights-gizmos.md)); glTF-authored camera and
`KHR_lights_punctual` support are separate loader work.

Use `examples/pyosg-khronos-viewer.py` (`osgx.PBRScene.create()`'s thin viewer
consumer) and `/home/cubicool/tmp/khronos/CODEX.md` for authoritative Khronos parity work.
