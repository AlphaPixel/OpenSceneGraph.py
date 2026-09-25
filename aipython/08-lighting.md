# Composing osgx::gltf materials with generic osgx lighting

`osgx::gltf` (formerly a separate `osgGLTF` module/repo, merged into `osgx.gltf` — there is
no `osgGLTF` Python module) is the glTF loader plus its optional PBR/IBL adapter. The ownership
boundary is:

- `osgx.gltf.shader` defines the glTF-specific vertex state populated by the loader (tangent and
  skinning attribute locations, `configureProgram()`). Materials are plain `osgx.Material`s.
- `osgx.gltf.pbribl` provides the optional one-call renderer (`PBRIBLScene`), the manifest loader
  `loadEnvironment()`, and `KHRONOS_ENVIRONMENT_ROTATION`.
- `osgx` and `osgx` provide generic rendering and environment-processing facilities.
- `osgx.resolveShaderLibs()` expands generic catalogs (`osgx::pbr`, `osgx::ibl`, `osgx::shadow`).
- `osgx.gltf.pbribl.resolveShaderLibs()` registers and expands the `osgx::gltf` catalog together
  with those generic osgx catalogs, in one call.

Import `osgx` before resolving a hand-assembled glTF shader — it registers every catalog
(`osgx.gltf.pbribl.resolveShaderLibs()` calls the PBR/IBL/shadow/gltf registration functions
itself, so nothing else needs to be imported separately):

```python
import osgx

fragment_source = """
#version 460 core

const float PI = 3.14159265359;

#pragma osgx::pbr MATERIAL_STRUCT, D_GGX, G_SCHLICK, G_SMITH, F_SCHLICK, DIRECT_SPECULAR, TONEMAP_PBR_NEUTRAL
#pragma osgx::gltf MATERIAL_INPUTS, GET_MATERIAL, SHADING_NORMAL, EMISSIVE, ALPHA_COVERAGE
#pragma osgx::ibl HEMISPHERE_AMBIENT

// application-specific lighting and main()
"""

fragment_shader = osgx.gltf.pbribl.resolveShaderLibs(fragment_source)
```

Catalog and library names are case-insensitive. Unknown entries in a registered namespace fail
immediately; unrelated pragmas remain intact for OSG or other tooling.

## Required program and StateSet setup

Custom renderers should use `osgx.gltf.shader`'s public contract rather than repeat the tangent/
skinning attribute locations:

```python
program = osg.Program(shaders=(
	osg.Shader(osg.Shader.VERTEX, vertex_source),
	osg.Shader(osg.Shader.FRAGMENT, fragment_shader),
))

state_set = model.stateSet
osgx.gltf.shader.configureProgram(program)
state_set.setAttributeAndModes(
	program,
	osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE,
)
```

`configureProgram()` binds tangent and skin attributes to the locations populated by the loader.
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

For a pre-baked environment, load its `osgx_pbribl` manifest as an `osgx.Environment` and use osgx's
optional renderer (see [`30-pbribl.md`](30-pbribl.md) for the full API, including the
shadow/skinning/tonemap `hooks` options and the deferred G-buffer variant for many-light scenes):

```python
model = osgDB.readNodeFile("scene.gltf")
environment = osgx.gltf.pbribl.loadEnvironment("papermill.gltf")

if environment is None:
	raise RuntimeError("failed to load PBR/IBL environment")

scene = osgx.gltf.pbribl.PBRIBLScene.create(model, environment)

if not scene.valid():
	raise RuntimeError("PBR/IBL setup failed")

root = osg.Group()

if environment.bakeRoot is not None:
	root.children.append(environment.bakeRoot)

root.children.append(scene.node)
```

`environment.bakeRoot` must participate in the rendered scene graph when it is not `None`. For a
fully dynamic setup, build `osgx.Environment(osgDB.readImageFile("environment.hdr"))` and set its
`rotation` to `osgx.gltf.pbribl.KHRONOS_ENVIRONMENT_ROTATION`; it bakes specular, diffuse, and the
BRDF LUT from that one source. The helper is IBL-only and does not
invent authored/direct lights. Generic light rigs remain in `osgx` (see
[`40-typed-lights-gizmos.md`](40-typed-lights-gizmos.md)); glTF-authored camera and
`KHR_lights_punctual` support are separate loader work.

Use `examples/pyosg-khronos-viewer.py` (`osgx.gltf.pbribl.PBRIBLScene.create()`'s thin viewer
consumer) and `/home/cubicool/tmp/khronos/CODEX.md` for authoritative Khronos parity work.
