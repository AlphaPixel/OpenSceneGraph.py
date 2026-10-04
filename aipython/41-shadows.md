# Shadow mapping (`osgx.ShadowMap` / `osgx.ShadowSet`)

Check `git log -1 -- src/osgx/Shadow.hpp` in the configured osgx source dir
(see the repo's `CLAUDE.md` on `PYOSG_OSGX_SOURCE_DIR`) if anything here looks
stale.

## What this is

`osgx.ShadowMap` (C++: `src/osgx/Shadow.hpp`/`src/Shadow.cpp`) is one light's
shadow — a directional/spot map (a single depth-only `osg.Camera`) or a point
map (an omnidirectional distance cube, six capture cameras). `osgx.ShadowSet`
aggregates however many `ShadowMap`s a scene has (any mix of directional/spot
and point, up to `osgx.MAX_SHADOWED_2D` directional/spot maps and
`osgx.MAX_SHADOWED_CUBE` point maps — both 2 today) into the uniform data one
shared shader hook reads. Any combination of light types can be shadowed
simultaneously in one `Program`; nothing requires picking a single shadowed
light up front.

Shadowing is a separate hook contract from direct lighting, not bundled into
it: `osgx_DirectLighting()` (`osgx.DIRECT_LIGHTING_HOOK_DEFAULT`, see
[`40-typed-lights-gizmos.md`](40-typed-lights-gizmos.md)) is unconditional —
every Program uses the identical lighting loop whether or not anything is
shadowed. Per-light shadow attenuation is a second, independent hook,
**`osgx_ShadowFactorForLight(lightIndex, worldPos, N)`**
(`osgx.SHADOW_FACTOR_DECL`), called once per light from inside that loop. A
Program that attaches `osgx.DIRECT_LIGHTING_HOOK_DEFAULT` must ALSO attach a
`Hook.ShadowFactor` definition — there is no implicit default the way C++
callers get from `applyHooks()`:

- No shadows at all: `osgx.makeShadowFactorNoneHookShader()` (always returns
  `1.0`, declares no shadow-map uniforms/samplers).
  `osgx.PBRScene`/`osgx.PBRLightingPass` add this automatically when
  `shadowSet=None`.
- Real shadows: a built `osgx.ShadowSet`'s own `.shader` property.

```python
program = osg.Program(name="my-shader", shaders=(
	osg.Shader(osg.Shader.VERTEX, vertex_source),
	osg.Shader(osg.Shader.FRAGMENT, osgx.resolveShaderLibs(fragment_source)),
	osgx.makeDirectLightingHookShader(),
	shadow_set.shader if shadow_set is not None else osgx.makeShadowFactorNoneHookShader(),
))
```

## Minimal live REPL setup (one directional light, shadowed)

```python
import osgx

lib = osgx.initialize()

lights = osgx.LightSet()
root.stateSet.attributes.append(lights)

direction = osg.Vec3(0.3, 0.2, -1.0)
lights.setDirectional(0, direction, osg.Vec3(1.0, 0.96, 0.88), 3.0)

# Coverage: the CASTER bound (what must be rendered into the shadow map) and an
# optional, separate RECEIVER bound (what must be able to SAMPLE it) -- see
# "Coverage: caster vs. receiver" below before reaching for this on a floor/room.
coverage = osgx.ShadowMap.Coverage()
coverage.center = osg.Vec3(0.0, 0.0, 0.0)
coverage.radius = 2.5

shadow_map = osgx.ShadowMap.create(direction, coverage)
shadow_map.casterIndex.set(0)  # which LightSet index this map shadows

shadow_map.camera.children.append(casters)  # casters: an osg.Group/Geode subgraph

shadow_set = osgx.ShadowSet.create()
shadow_set.add(shadow_map)
shadow_set.apply(root.stateSet)  # binds textures/uniforms; call once after every add()

root.children.append(shadow_map.camera)
root.children.append(receivers)  # the lit, shadowed scene -- NOT the same subgraph as casters
```

`shadow_map.camera` is a `PRE_RENDER` depth-only camera — add whatever subgraph
should CAST shadows as its child, separately from the main lit scene graph
(which receives shadows via `shadow_set.apply()`'s StateSet uniforms). Reusing
the same subgraph for both is fine (OSG nodes support multiple parents); just
add it to both `shadow_map.camera` and the lit root.

## `create()`/`createSpot()`/`createPoint()`

Match `osgx.LightSet`'s own setter conventions (ray TRAVEL direction for
directional/spot, radians for angles):

```python
# Directional -- orthographic frustum, `direction` is ray travel direction (KHR_lights_punctual)
shadow_map = osgx.ShadowMap.create(direction, coverage)

# Spot -- perspective frustum from `position`, covering `outerConeAngle` (radians)
shadow_map = osgx.ShadowMap.createSpot(position, direction, outer_cone_radians, coverage)

# Point -- omnidirectional distance cube (CaptureCubeMap, 6 cameras); cubeSize defaults to 256
shadow_map = osgx.ShadowMap.createPoint(position, coverage, cubeSize=256)
```

A point map has no single `.camera` — add casters to `shadow_map.casters`
(shared by all six capture cameras) instead, and the whole rig to the scene
via `shadow_map.cubeCapture.root`:

```python
shadow_map = osgx.ShadowMap.createPoint(position, coverage)
shadow_map.casterIndex.set(1)
shadow_map.casters.children.append(casters)

shadow_set.add(shadow_map)
root.children.append(shadow_map.cubeCapture.root)
```

`shadow_map.camera` being `None`/invalid vs. set is exactly how `ShadowSet.add()`
tells a point map from a directional/spot one — nothing else to configure.

## Coverage: caster vs. receiver

`osgx.ShadowMap.Coverage` has two bounds, not one:

- `center`/`radius` — the CASTER bound. Geometry outside this is never
  rendered into the shadow map and simply never casts, full stop.
- `receiverCenter`/`receiverRadius` — the (optional) RECEIVER bound.
  `receiverRadius=0.0` (the default) means "receivers never extend past the
  caster bound itself." A receiver point OUTSIDE whatever bound was actually
  used silently reads as unshadowed (`1.0`, "no shadow") — not an error, not
  a visible glitch, just wrong-looking: a floor/room receiving a cast shadow
  needs `receiverCenter`/`receiverRadius` covering the full receiving area,
  not just the casting model's own bound. `Coverage.bound()` returns the
  merged `osg.BoundingSphere` both bounds together produce.

```python
coverage = osgx.ShadowMap.Coverage()
coverage.center = model_bound.center()
coverage.radius = model_bound.radius()
coverage.receiverCenter = osg.Vec3(0.0, 0.0, 0.0)
coverage.receiverRadius = floor_half_size * 1.42  # sqrt(2) covers a square floor's own corners
```

Widening receiver coverage costs resolution: each shadow-map texel then
covers more world space, so edges get blockier and `bias`/`normalOffset` both
need to grow. Real remedies are a bigger `Options.size`, a wider box at the
same size (`Options.extent`/`margin`), or cascades (not implemented) — not
something to "fix" by raising bias alone.

## Live repositioning — the `ShadowSet.sync()` gotcha

`shadow_map.reposition()`/`repositionSpot()`/`repositionPoint()` move an
EXISTING map in place (no camera/FBO/texture rebuild — cheap enough for every
GUI-slider tick or per-frame light drag). But the shader reads `ShadowSet`'s
OWN combined uniform arrays, not `ShadowMap`'s directly — **every
reposition call, and every direct `bias`/`normalOffset`/`strength` edit, needs
a matching `shadow_set.sync()` afterward**, or the shader keeps using stale
data:

```python
shadow_map.reposition(new_direction, coverage)
shadow_set.sync()  # <-- easy to forget; shadow silently stops tracking the light otherwise

shadow_map.bias.set(0.002)
shadow_set.sync()
```

`shadow_set.apply(stateSet)` only needs calling ONCE, after every `add()` this
`ShadowSet` will ever receive — `sync()` alone is enough for all live updates
after that.

## Gizmos

`osgx.FrustumGizmo`/`osgx.CaptureCubeGizmo` (C++: `src/osgx/Gizmos.hpp`,
Python: flat under `osgx`) visualize the SHADOW CAMERA's own setup — a
depth-tested wireframe frustum (directional/spot) or a wireframe cube at the
capture's far-plane range (point). This is different data from
`osgx.LightGizmos`/`LightMarkers` (which visualize the LIGHT itself — see
[`40-typed-lights-gizmos.md`](40-typed-lights-gizmos.md)) and exists
independently — a `ShadowMap` has no light-gizmo equivalent and vice versa:

```python
root.children.append(osgx.FrustumGizmo(shadow_map.camera, osg.Vec3(1.0, 0.96, 0.88)))
# Point: osgx.CaptureCubeGizmo(shadow_map.cubeCapture.cameras[0], color)
```

Both also take a generic callable instead of a live `osg.Camera` (returns
`(view_matrix, proj_matrix)` or `(center, radius)` each call) for a data
source that isn't a real OSG camera at all — not needed for ordinary
`ShadowMap` use.

## `osgx.PBRScene`/`osgx.PBRLightingPass` integration

```python
pbr = osgx.PBRScene.create(geode, osgx.PBRScene.Options(
	environment=environment,
	shadowSet=shadow_set,
))
```

`Options.shadowSet` (NOT `shadowMap` — that field name was removed, no
compatibility alias) takes the built `osgx.ShadowSet`, not an individual
`ShadowMap`. Build and `add()` every `ShadowMap` the scene needs first, then
pass the one `ShadowSet` here; `shadow_set.apply()` is called internally, no
separate call needed when going through `PBRScene`/`PBRLightingPass`.

## Known gaps

`MAX_SHADOWED_2D`/`MAX_SHADOWED_CUBE` are both 2 — a hard cap on
simultaneously-shadowed directional/spot vs. point lights; `ShadowSet.add()`
raises once either is full. No PCF-equivalent softening for the cube/point
comparison (`osgx_ShadowFactorCube()` is a single tap — the 2D kind's 3x3
offset pattern doesn't translate directly to a cube's non-uniform texel
spacing at the seams). The depth-only casting Program has no alpha/discard
logic — a cutout/masked glTF material casts a solid shadow, not a
punched-through one. No cascades — a directional light covering a very large
receiver at a single map size loses resolution; splitting into multiple maps
at different distance bands isn't implemented.
