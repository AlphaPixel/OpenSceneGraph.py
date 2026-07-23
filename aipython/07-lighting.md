# Getting PBR/IBL lighting going fast, via `osgx`

Confirmed 2026-07-22 building `examples/pyosg-voxelize.py` live: the first
working version hand-copied ~150 lines of PBR fragment-shader GLSL out of
`examples/pyosg-lighting/09-ibl.py` (the glTF material UBO contract, BRDF
math, hemisphere-ambient fallback) for the third time across this project's
examples. That copy is what got ported into `osgx` (`~/dev/osgdebug`,
symlinked into this repo's build as `osgx.cpython-*.so`) as reusable
`#pragma`-includable snippets -- this doc is "how to use that," not the
design rationale (see `osgx/PBR.hpp`/`osgx/IBL.hpp`/`osgx/GLTF.hpp` in that
repo for the comments on *why* each piece exists).

## The mechanism: `#pragma osgx::<namespace> LIB1, LIB2, ...` + `resolveShaderLibs()`

`osgx` registers named GLSL snippets under a few namespaces
(`osgx::pbr`, `osgx::ibl`, `osgx::gltf`). Write a `#pragma` line naming which
ones a shader wants, then resolve it in Python before compiling:

```python
import osgx

FRAG_SRC = """
#version 460 core
#pragma osgx::pbr D_GGX, G_SCHLICK, G_SMITH, F_SCHLICK, DIRECT_SPECULAR
...
"""

FRAG = osgx.resolveShaderLibs(FRAG_SRC)  # do this ONCE, before osg.Shader()

prog = osg.Program(shaders=(
	osg.Shader(osg.Shader.VERTEX, VERT_SRC),
	osg.Shader(osg.Shader.FRAGMENT, FRAG),  # the RESOLVED text, not FRAG_SRC
))
```

`resolveShaderLibs` just does text substitution -- each `#pragma` line gets
replaced by the concatenated source of the named libs, in the order
requested. `#pragma osgx::pbr *` pulls in everything registered under that
namespace.

## Gotcha: declare `PI` (and anything else a lib assumes) *before* the `#pragma` line

`osgx::pbr`'s math snippets (`D_GGX` etc.) reference a bare `PI` constant but
don't declare it themselves (a duplicate `const float PI` across two
snippets would be a compile error, not a harmless redefinition -- see
`osgx/PBR.hpp`'s top comment). Text substitution is literal and top-to-
bottom, so `PI` must already be visible *above* the pragma line, not below
it:

```glsl
// RIGHT
const float PI = 3.14159265359;
#pragma osgx::pbr D_GGX, G_SCHLICK, G_SMITH

// WRONG -- osgx_D_GGX's body references PI before it's declared
#pragma osgx::pbr D_GGX, G_SCHLICK, G_SMITH
const float PI = 3.14159265359;
```

This bit us once live: the fix was moving one `const float PI` line four
lines up, immediately confirmed via a Python-side round-trip check (resolve
the shader, find both strings' positions, assert `PI`'s index < the using
function's index) rather than waiting to discover it as a GLSL compile
error inside OSG.

## Fastest path: a lit glTF model, zero IBL assets

No KTX2 cubemap, no HDR, no BRDF LUT bake, no SH computation -- just
`osgx::gltf`'s material-reading glue + `osgx::ibl::HEMISPHERE_AMBIENT` (a
flat two-color sky/ground lerp, the exact fallback path
`09-ibl.py`'s full shader takes when `iblEnabled == 0`). This is the whole
"quick demo, no fuss" point: as much of the boilerplate as possible now
lives in `osgx`, not copy-pasted per example.

```glsl
#version 460 core

const float PI = 3.14159265359;  // must precede the pragma line below

#pragma osgx::pbr MATERIAL_STRUCT, D_GGX, G_SCHLICK, G_SMITH, F_SCHLICK, DIRECT_SPECULAR, TONEMAP_PBR_NEUTRAL
#pragma osgx::gltf MATERIAL_INPUTS, GET_MATERIAL, SHADING_NORMAL, EMISSIVE, ALPHA_COVERAGE
#pragma osgx::ibl HEMISPHERE_AMBIENT

in vec3 vNGeom; in vec3 vPosition; in vec4 vTangent; in vec2 vUV;
uniform vec3 skyColor; uniform vec3 groundColor; uniform mat4 osg_ViewMatrix;
out vec4 fragColor;

void main() {
	vec3 N = osgx_GLTFShadingNormal(vNGeom, vTangent, vPosition, vUV);
	vec3 V = normalize(-vPosition);
	osgx_Material mat = osgx_GLTFGetMaterial(vUV, N);
	float NdotV = max(dot(N, V), 0.0);

	vec3 worldUp = normalize(mat3(osg_ViewMatrix) * vec3(0.0, 0.0, 1.0));
	vec3 ambient = osgx_HemisphereAmbient(N, worldUp, mat.albedo, mat.ao, skyColor, groundColor);
	// ...add a direct-light loop here if the scene needs one; see
	// pyosg-voxelize.py's apply_gltf_fallback_pbr() for a full worked example
	// including that loop, or skip it entirely for ambient-only.

	vec3 color = osgx_TonemapPBRNeutral(ambient);
	fragColor = vec4(pow(color, vec3(1.0 / 2.2)), 1.0);
}
```

Full working reference (vertex shader, direct-light loop, uniform wiring,
scale-independent light-rig defaults derived from `node.bound`): see
`examples/pyosg-voxelize.py`'s `PBR_FALLBACK_VERTEX_SHADER` /
`PBR_FALLBACK_FRAGMENT_SHADER_SRC` / `apply_gltf_fallback_pbr()`.

**Reads directly off whatever `osgDB.readNodeFile()` returns for a glTF
model** -- no manual uniform setup needed for the material side. The
`osgGLTF_Material` UBO (binding 0) and the four fixed texture units
(baseColor=0, normal=1, orm=2, emissive=3) are populated automatically per
primitive by the C++ loader (`GLTFReader.hpp`'s `applyMaterial()`) the
moment the model loads -- `osgx::gltf::MATERIAL_INPUTS`/`GET_MATERIAL` are
just the GLSL-side contract for reading what's already there. Applying this
program to a loaded node (`node.stateSet.setAttributeAndModes(prog,
osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE)`) is enough; nothing
lower in that node's subtree needs touching.

## Gotcha: `osgx_DirectSpecular` already includes the `NdotL` multiply

If writing a direct-light loop by hand (rather than copying
`pyosg-voxelize.py`'s), don't multiply the whole `diffuse + specular` sum by
`NdotL` at the end the way a hand-rolled Cook-Torrance loop normally would --
`osgx_DirectSpecular` (`osgx::pbr::DIRECT_SPECULAR`) already folds `NdotL`
into its own `D*G*F*NdotL / denom` return value. Only the separate Lambert
diffuse term needs an explicit `* NdotL`:

```glsl
float NdotL = max(dot(N, L), 0.0);
vec3 diffuse = kD * mat.albedo / PI * NdotL;               // needs NdotL
vec3 specular = osgx_DirectSpecular(N, V, L, NdotV, mat.roughness, mat.F0);  // does NOT
Lo += (diffuse + specular) * lightColor[i] * atten;         // no extra NdotL here
```

## Going further: real IBL, the one-call way

`HEMISPHERE_AMBIENT` above is deliberately the cheapest possible ambient
term. Once an actual environment (a `.ktx2` prefiltered cubemap + its source
`.hdr`) is worth loading, **`osgx.gltf.setupFullPBR()` is the fastest path**
-- confirmed 2026-07-22 to reproduce, pixel-for-pixel, a hand-assembled
full-IBL shader (`osgx::gltf` material glue + `osgx::pbr`'s real
`IBL_SPECULAR`/`F_MULTISCATTER` + `osgx::ibl`'s `SH_IRRADIANCE`, one direct
light) against a real glTF model:

```python
model = osgDB.readNodeFile("scene.gltf")
setup = osgx.gltf.setupFullPBR(model, "papermill.ktx2", "papermill.hdr")

root = osg.Group(children=(setup.lutCamera, model))  # lutCamera MUST be in the graph
```

That's the entire "load this glTF model with full PBR/IBL using papermill"
request. `setup.valid()` is `False` (with an `OSG_WARN`) if either asset
path failed to load; `setup.envMap`/`.brdfLUT` are also returned in case the
same environment is wanted elsewhere (e.g. a skybox). One direct light,
positioned relative to `node`'s own bound (not absolute world coordinates,
so the defaults land reasonably regardless of model scale) -- optional
kwargs (`iblIntensity`, `lightDir`, `lightDistance`, `lightColor`,
`lightRadiusScale`, `lutSize`) tune it without dropping to hand-assembly.

**When to still hand-assemble instead:** more than one light, or genuinely
different wiring/uniform names than `setupFullPBR` hardcodes. Full
transparent reference for that path (the exact shader `setupFullPBR` itself
uses, so it's also the definitive worked example if extending it):
`osgx::gltf::detail::FULL_PBR_VERTEX_SHADER`/`FULL_PBR_FRAGMENT_SHADER_SRC`
in `~/dev/osgdebug/osgx/GLTF.hpp`. The older hand-assembled-from-Python
prototype (multiple lights, more manual control) is
`examples/pyosg-voxelize.py`'s `apply_gltf_fallback_pbr()` -- note that one
uses the no-IBL `HEMISPHERE_AMBIENT` fallback, not real IBL.

`osgx::pbr::OrbitLightRig` (an `osg.NodeCallback` subclass, assign directly
to `.updateCallback`) is a ready-made animated multi-light rig if a scene
wants moving point lights without hand-writing the orbit math -- usable
alongside `setupFullPBR`'s single fixed light or as part of a fully
hand-assembled shader.
