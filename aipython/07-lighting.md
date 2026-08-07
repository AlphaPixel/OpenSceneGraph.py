# Composing osgGLTF materials with generic osgx lighting

The ownership boundary is:

- `osgGLTF.shader` defines the state populated by the loader.
- `osgGLTF.pbr` provides glTF-specific material/shading helpers and the optional one-call renderer.
- `osgx.pbr` and `osgx.ibl` provide generic rendering and environment-processing facilities.
- `osgx.resolveShaderLibs()` expands generic catalogs.
- `osgGLTF.pbr.resolveShaderLibs()` registers and expands both osgGLTF and generic osgx catalogs.

Import both modules before resolving a hand-assembled glTF shader. Importing `osgx` registers its
generic catalogs; importing `osgGLTF` registers the `osgGLTF` material catalog.

```python
import osgx
import osgGLTF

fragment_source = """
#version 460 core

const float PI = 3.14159265359;

#pragma osgx::pbr MATERIAL_STRUCT, D_GGX, G_SCHLICK, G_SMITH, F_SCHLICK, DIRECT_SPECULAR, TONEMAP_PBR_NEUTRAL
#pragma osgGLTF MATERIAL_INPUTS, GET_MATERIAL, SHADING_NORMAL, EMISSIVE, ALPHA_COVERAGE
#pragma osgx::ibl HEMISPHERE_AMBIENT

// application-specific lighting and main()
"""

fragment_shader = osgGLTF.pbr.resolveShaderLibs(fragment_source)
```

Catalog and library names are case-insensitive. Unknown entries in a registered namespace fail
immediately; unrelated pragmas remain intact for OSG or other tooling.

## Required program and StateSet setup

Custom renderers should use osgGLTF's public contract rather than repeat attribute locations or
sampler units:

```python
program = osg.Program(shaders=(
	osg.Shader(osg.Shader.VERTEX, vertex_source),
	osg.Shader(osg.Shader.FRAGMENT, fragment_shader),
))

state_set = model.stateSet
osgGLTF.shader.configureProgram(program)
osgGLTF.shader.configureStateSet(state_set)
state_set.setAttributeAndModes(
	program,
	osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE,
)
```

`configureProgram()` binds tangent and skin attributes to the locations populated by the loader.
`configureStateSet()` maps base-color, normal, ORM, and emissive samplers to the loader's texture
units. The loader owns the material data; the application still owns its renderer and Program.

`examples/pyosg-voxelize.py` is the complete hand-assembled fallback example.

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

For a pre-baked environment, load its `osgx_pbribl` manifest and use osgx's optional renderer:

```python
model = osgDB.readNodeFile("scene.gltf")
environment = osgx.gltf.pbribl.loadPBRIBLEnvironment("papermill.gltf")
scene = osgx.gltf.pbribl.createPBRIBLScene(model, environment)

if not environment.valid() or not scene.valid():
	raise RuntimeError("PBR/IBL setup failed")

root = osg.Group()

if environment.root is not None:
	root.children.append(environment.root)

root.children.append(scene.node)
```

The environment root must participate in the rendered scene graph when the manifest uses a built-in
LUT. For a fully dynamic setup, use `preparePBRIBLEnvironment("environment.hdr")`; it bakes
specular, diffuse, and the BRDF LUT from that one source. The helper is IBL-only and does not invent
authored/direct lights. Generic light rigs remain in `osgx.pbr`; glTF-authored camera and
`KHR_lights_punctual` support are separate loader work.

Use `examples/pyosg-khronos-viewer2.py` for the thin one-call renderer consumer. Use
`examples/pyosg-khronos-viewer.py` and `/home/cubicool/tmp/khronos/CODEX.md` for authoritative
Khronos parity work.
