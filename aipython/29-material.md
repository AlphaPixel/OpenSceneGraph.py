# osgx.Material — one PBR material as a real StateAttribute

`osgx.Material` is a real `osg.StateAttribute` subclass: construct one,
set its properties, attach it to a `StateSet` like any other attribute. This
replaces hand-building a material UBO (`osg.FloatArray` +
`osg.UniformBufferBinding`) yourself.

```python
import osgx

material = osgx.Material()

material.baseColor = osg.Vec4(0.95, 0.55, 0.12, 1.0)
material.roughness = 0.12
material.metallic = 1.0

drawable.stateSet.attributes.append(material)
```

`StateSet.attributes[key] = value` (keyed by `osg.StateAttribute.Type`) also
works, but `.attributes.append(material)` is simplest — it reads the key off
the attribute's own `.type`.

## Properties

| Property | Meaning |
|---|---|
| `baseColor` | `osg.Vec4` RGBA factor, multiplied against `baseColorMap` when one is set. |
| `roughness` | float factor. `0.0`–`0.1` reads as a sharp mirror-like reflection; `1.0` is fully matte. |
| `metallic` | float factor. `1.0` tints specular by `baseColor` (real metal); `0.0` keeps a neutral white `F0=0.04` dielectric specular. |
| `hasOcclusion` | bool. No dedicated texture slot — occlusion is read from `metallicRoughnessMap`'s R channel, so this flag opts in explicitly. |
| `baseColorMap`, `normalMap`, `metallicRoughnessMap`, `emissiveMap` | `osg.Texture2D` or `None`. Bound at the `osgx::material.*` texture-unit slots (`lib.binding("osgx::material.baseColor")` etc.); a mesh's UVs for each map come from texcoord array `osgx.{BASE_COLOR,NORMAL,ORM,EMISSIVE}_UV_CHANNEL`. |

`hasBaseColorMap`/`hasMetallicRoughnessMap`/`hasNormalMap` are **not**
separate properties — derived automatically from whether the corresponding
`*Map` property is set. Setting `baseColorMap` and having the texture
actually sample are the same operation.

## Shader side: `osgx_materialInputs`

`Material` populates one `std140` uniform block, `osgx_materialInputs`
(`#pragma osgx::pbr MATERIAL_INPUTS`), at the `osgx::material` binding slot - the same
buffer the glTF loader populates for a loaded asset, since every glTF material
is an `osgx.Material`. Factors, emissive, and alpha mode/cutoff all live in
it; the four maps use samplers that declare their own texture units. A
minimal fragment shader:

```glsl
#pragma osgx::pbr MATERIAL_STRUCT, MATERIAL_INPUTS, GET_MATERIAL
#pragma osgx::light DIRECT_LIGHTING_DECL

osgx_Material mat = osgx_GetMaterial(vUV, vUV);
```

`osgx_DirectSpecular()` floors roughness at `0.045` itself - a true zero is a
0/0 in the GGX distribution term - so shaders using the stock direct-light
functions need no clamp of their own.

## Works on a plain `osg.ShapeDrawable`, not just osgx shapes

`Material` is a StateSet attribute like `osg.Program` or `osg.BlendFunc` — it
doesn't care what built the geometry. Confirmed on both `osgx.Icosahedron`
and a bare `osg.ShapeDrawable(osg.Sphere(...))`. One gotcha specific to
`ShapeDrawable`, unrelated to `Material` itself: it builds its geometry with
only classic `setVertexArray()`/`setNormalArray()` calls, not the extra
`setVertexAttribArray(0/1, ...)` calls `osgx.Polyhedron`-derived shapes
(`Cube`, `Icosahedron`) also make so a custom core-profile `Program` can rely
on fixed `position`/`normal` attribute locations. A vertex shader for a
`ShapeDrawable` should use OSG's own auto-aliased `osg_Vertex`/`osg_Normal`
attribute names instead — the same convention `pyosg-dynamic.py`/
`pyosg-hover.py`/`pyosg-picking.py` already use.

## One material per mesh, not per face or per object instance

Match how glTF (and every real exporter format) works: one `Material` per
mesh/primitive. `StateAttribute`s only apply at Drawable granularity. For
visibly different materials across the faces of one shape, either give each
face its own small Drawable/Geode, or keep one Drawable and drive the
variation through a per-vertex attribute feeding a shader-side branch/array
yourself — `pyosg-material.py`'s "glitter" scene's `GLITTER_MATERIAL_COMBOS` is the working
example of the second approach, and deliberately hand-rolls its own
`osgx_Material` struct from vertex data rather than using
`osgx.Material`.

## `StateAttribute::Type` and dedup

`Material.type` is `osg.StateAttribute.CAPABILITY` — its own claimed slot.
Two `Material`s with equal factors and identical texture objects compare
equal (`compare()` is real), so OSG's state-sorting can skip a redundant
re-apply between drawables that share one material — e.g. several primitives
loaded from the same glTF material, since the loader's `TextureLoader`
already caches/shares `Texture2D` objects by source index.

## Verify a live result

If reflections look completely absent at low roughness/high metallic,
suspect the geometry before the material: flat facets under a single
directional light (no IBL environment) rarely catch a legible specular
highlight or environment reflection, regardless of roughness. Add a smooth
`osg.ShapeDrawable(osg.Sphere(...))` "chrome ball" control (max metallic,
near-zero roughness, near-white base color) — if it shows a clear reflection
and the original shape doesn't, that's a geometry limitation, not a material
or shader bug. `examples/pyosg-material-lab.py` is exactly this setup, with
`--hdr`/`--env` wiring a real `osgx.Environment` (see [`30-pbribl.md`](30-pbribl.md)).
