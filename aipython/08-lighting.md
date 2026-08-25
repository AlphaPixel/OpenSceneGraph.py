# Composing osgx::gltf materials with generic osgx lighting

`osgx::gltf` (formerly a separate `osgGLTF` module/repo, merged into `osgx.gltf` — there is
no `osgGLTF` Python module) is the glTF loader plus its optional PBR/IBL adapter. The ownership
boundary is:

- `osgx.gltf.shader` defines the state populated by the loader (attribute locations, sampler
  units, `configureProgram()`/`configureStateSet()`).
- `osgx.gltf.pbribl` provides glTF-specific material/shading GLSL snippets and the optional
  one-call renderer (`PBRIBLEnvironment`/`PBRIBLScene`).
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

Custom renderers should use `osgx.gltf.shader`'s public contract rather than repeat attribute
locations or sampler units:

```python
program = osg.Program(shaders=(
	osg.Shader(osg.Shader.VERTEX, vertex_source),
	osg.Shader(osg.Shader.FRAGMENT, fragment_shader),
))

state_set = model.stateSet
osgx.gltf.shader.configureProgram(program)
osgx.gltf.shader.configureStateSet(state_set)
state_set.setAttributeAndModes(
	program,
	osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE,
)
```

`configureProgram()` binds tangent and skin attributes to the locations populated by the loader.
`configureStateSet()` maps base-color, normal, ORM, and emissive samplers to the loader's texture
units. The loader owns the material data; the application still owns its renderer and Program.

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

For a pre-baked environment, load its `osgx_pbribl` manifest and use osgx's optional renderer —
`PBRIBLEnvironment`/`PBRIBLScene` are classes with static factory methods, not free functions (see
[`30-pbribl.md`](30-pbribl.md) for the full API, including the shadow/skinning/tonemap `hooks`
options and the deferred G-buffer variant for many-light scenes):

```python
model = osgDB.readNodeFile("scene.gltf")
environment = osgx.gltf.pbribl.PBRIBLEnvironment.load("papermill.gltf")
scene = osgx.gltf.pbribl.PBRIBLScene.create(model, environment)

if not environment.valid() or not scene.valid():
	raise RuntimeError("PBR/IBL setup failed")

root = osg.Group()

if environment.root is not None:
	root.children.append(environment.root)

root.children.append(scene.node)
```

The environment root must participate in the rendered scene graph when the manifest uses a built-in
LUT. For a fully dynamic setup, use `PBRIBLEnvironment.prepare("environment.hdr")`; it bakes
specular, diffuse, and the BRDF LUT from that one source. The helper is IBL-only and does not
invent authored/direct lights. Generic light rigs remain in `osgx` (see
[`40-typed-lights-gizmos.md`](40-typed-lights-gizmos.md)); glTF-authored camera and
`KHR_lights_punctual` support are separate loader work.

Use `examples/pyosg-khronos-viewer.py` (`osgx.gltf.pbribl.PBRIBLScene.create()`'s thin viewer
consumer) and `/home/cubicool/tmp/khronos/CODEX.md` for authoritative Khronos parity work.
