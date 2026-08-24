# osgx typed direct lights (`osgx.pbr.LightSet`) + light gizmos

Check `git log -1 -- src/osgx/PBR.hpp` in the configured osgx source dir (see
the repo's `CLAUDE.md` on `PYOSG_OSGX_SOURCE_DIR`) if anything here looks
stale — this describes an SSBO-backed contract that may still be uncommitted
in some checkouts.

## What this is

`osgx::pbr::LightSet` (C++: `src/osgx/PBR.hpp`/`src/PBR.cpp`, Python:
`osgx.pbr.LightSet`) is a typed direct-light rig. Per-light data
(`osgx.pbr.MAX_LIGHTS` == 6 slots) lives in a single `std430` Shader Storage
Buffer Object (`osgx_LightBuffer`/`osgx_lights[]`, binding 3 — C++
`osgx::LIGHT_BINDING`, not currently exposed to Python) plus one
`osgx_lightCount` uniform — not parallel flat uniform arrays. Three real
types — Point, Directional, Spot — plus a "Sphere" light that is NOT a
fourth type: it's `setPoint(..., sourceRadius>0)`, see below.

Every consumer shader reaches the light array through one hook call,
**`osgx_DirectLighting(N, V, worldPos, mat)`** — declared by
`osgx.pbr.DIRECT_LIGHTING_DECL` (splice into your fragment shader's
`#pragma osgx::pbr ...` line, alongside `MATERIAL_STRUCT`) and defined by
`osgx.pbr.DIRECT_LIGHTING_HOOK_DEFAULT`, a second self-contained FRAGMENT
shader object added to the same `Program`.
`osgx.pbr.makeDirectLightingHookShader()` returns that shader object ready
to append:

```python
program = osg.Program(name="my-shader", shaders=(
	osg.Shader(osg.Shader.VERTEX, vertex_source),
	osg.Shader(osg.Shader.FRAGMENT, osgx.resolveShaderLibs(fragment_source)),
	osgx.pbr.makeDirectLightingHookShader(),
))
```

This is the same "hook" pattern `osgSlug` uses: a base shader owns `main()`
and only *declares* a fixed entry point; each consumer supplies — or accepts
the library default for — that entry point's definition as a separate
compiled shader object. It exists so the per-light dispatch loop lives in
exactly one place instead of being hand-copied into every consumer's
`main()`.

`osgx::LightGizmos`/`osgx::LightMarkers` (C++: `src/osgx/Gizmos.hpp`/
`src/Gizmos.cpp`, Python: `osgx.LightGizmos`/`osgx.LightMarkers` — flat under
`osgx`, not a `gizmo` submodule) are the matching debug visualization: real
depth-tested marker geometry for point/sphere/spot, plus a non-depth-tested
overlay for directional (which has no position to place a marker at). Both
take a live `osgx.pbr.LightSet` directly and read it through its typed
accessors (`getCount`/`getType`/`getPosIntensity`/`getColor`/`getDirection`/
`getSpotAngles`/`getSourceRadius`).

## Minimal live REPL setup

```python
lights = osgx.pbr.LightSet.create(root.stateSet)  # allocates the SSBO buffer (size MAX_LIGHTS, zero-initialized) + osgx_lightCount on root.stateSet

lights.setCount(1)  # how many of the 6 slots osgx_DirectLighting()'s loop actually reads this frame

# Point -- inverse-square falloff, ideal (zero-size) specular highlight
lights.setPoint(0, osg.Vec3(2.5, -2.5, 6.0), osg.Vec3(0.85, 0.55, 0.30), 12.0)

# Directional -- "travel direction" (KHR_lights_punctual convention), no position, no falloff
lights.setDirectional(0, osg.Vec3(0.2, 0.4, -1.0), osg.Vec3(0.75, 0.70, 0.60), 3.0)

# Spot -- cone-attenuated point light; angles in RADIANS (use math.radians(), no osg.DegreesToRadians)
import math
lights.setSpot(
	0, osg.Vec3(0.0, -4.0, 8.0), osg.Vec3(0.0, 1.0, -0.35), osg.Vec3(0.95, 0.85, 0.65),
	40.0, math.radians(15.0), math.radians(32.0),
)

# Sphere -- NOT a separate call: setPoint(..., sourceRadius>0). Widens the SPECULAR highlight only
# (Karis/UE4 representative-point trick) -- diffuse falloff is deliberately IDENTICAL to a plain
# point light at the same position/intensity. Has visibly ZERO effect on a fully rough/matte
# surface -- that's expected, not a bug.
lights.setPoint(0, osg.Vec3(2.5, -2.5, 6.0), osg.Vec3(0.85, 0.55, 0.30), 12.0, sourceRadius=0.7)

# Read back any field live:
lights.getType(0), lights.getPosIntensity(0), lights.getColor(0), lights.getSourceRadius(0)
```

`LightSet.create()` REPLACES the SSBO buffer + `osgx_lightCount` on that
StateSet — don't call it twice on the same live StateSet if you've already
populated lights there, or you'll zero it out. To WRAP an already-populated
StateSet's LightSet instead, construct `osgx.pbr.LightSet()` and set `.ss`
directly — `LightSet` has exactly one field (`ss`); the setters/getters
mutate the SSBO/uniforms that `ss` already carries, there is no separate
`.lights` handle to assign:

```python
lights = osgx.pbr.LightSet()
lights.ss = already_populated_stateset
```

A rig-building helper (`pyosg-match4-dice.py`'s `add_torch_rig()`):

```python
def add_torch_rig(stateset, torches):
	"""Build an osgx.pbr.LightSet on `stateset` from (position, intensity, color) tuples."""
	lights = osgx.pbr.LightSet.create(stateset)

	for i, (pos, intensity, color) in enumerate(torches):
		lights.setPoint(i, osg.Vec3(*pos), osg.Vec3(*color), intensity)

	lights.setCount(len(torches))

	return lights
```

## Gizmos

`osgx.LightGizmos` is itself an `osg.Group` — construct it and add the one
instance to the scene graph; its constructor already parents both the marker
geometry and the directional overlay as its own children, so don't also
add `.markers`/`.overlay` separately:

```python
gizmos = osgx.LightGizmos(lights, root, 0.4, 10.0)  # (LightSet, scene node for directional's bound-sizing, minMarkerRadius, spotConeLength)

root.children.append(gizmos)
```

`.markers` (an `osgx.LightMarkers`) and `.overlay` (an `osg.Camera`) are
read-only properties for reaching the two pieces individually — e.g. to
toggle visibility:

- `gizmos.markers`' point/spot markers are real scene geometry and DO get
  depth-occluded by actual room geometry (no shadow-mapping in this system,
  so occlusion only affects the debug marker's visibility, never the shading
  math). Keep test-light Z below the real ceiling if you want to see the
  marker.
- `gizmos.overlay` is unaffected (`GL_DEPTH_TEST` off, `POST_RENDER`).
- Toggle `gizmos.markers.nodeMask = 0` / `gizmos.overlay.nodeMask = 0` to
  hide them without removing them.
- `LightGizmos::computeBound()` is overridden to always return an empty
  bound — gizmo geometry deliberately never affects `TrackballManipulator`
  auto-fit/`home()` or cull's near/far, even though the overlay's own
  plane/arrow are sized larger than the scene it annotates.

## Live ImGui control panel

`osgx.imgui`'s Python bindings are function-style wrappers (`slider_float`,
`color_edit3`, `checkbox`, `radio_group`, `button`, `text`, `separator`,
`input_text` — all return `(changed, *new_values)` tuples), not the raw C++
`ImGui::` namespace. There is no `SliderFloat3`, `PushID`/`PopID`, or
`SameLine`. Build a vec3 control from three `slider_float` calls, and give
every widget label a `##<section-scope>` suffix — `Panel::draw()` only
`PushID`s a section when `options.expand=True`, so plain sections share one
global Dear ImGui id namespace and identical labels across sections (every
light type has a "Position"/"Color"/"Intensity") fight over the same drag
state without the suffix.

Working shape — one collapsible section per light type, an
Activate/Deactivate button driving a single shared "live" `LightSet` slot,
sliders scoped per section:

```python
import math

active_slot = 0  # the ONLY light -- lightCount stays 0 until a section is Activated

class LightsState:
	def __init__(self):
		self.active_demo = None
		self.point_position = [2.5, -2.5, 6.0]
		self.point_color = [0.85, 0.55, 0.30]
		self.point_intensity = 12.0
		# ... directional_*, sphere_* (+radius), spot_* (+direction, inner/outer deg, source_radius)

state = LightsState()

def apply_state():
	if state.active_demo is None:
		lights.setCount(0)
		return
	lights.setCount(1)
	if state.active_demo == "Point":
		lights.setPoint(active_slot, osg.Vec3(*state.point_position), osg.Vec3(*state.point_color), state.point_intensity)
	# ... Directional -> setDirectional, Sphere -> setPoint(..., sourceRadius=...), Spot -> setSpot(...)

def point_section(ri):  # addSection()'s callback always takes one osg.RenderInfo arg, even if unused
	# activate_button(name): text("ACTIVE"/"(inactive)") + Activate/Deactivate osgx.imgui.button(),
	# calling apply_state() on either. Every widget label carries a "##point"-style scope suffix.
	# vec3_sliders(prefix, scope, values, lo, hi): three osgx.imgui.slider_float() calls, one per axis.
	activate_button("Point")
	changed = vec3_sliders("Position", "ptpos", state.point_position, -10.0, 10.0)
	c, r, g, b = osgx.imgui.color_edit3("Color##pt", *state.point_color)
	state.point_color[:] = [r, g, b]
	changed = changed or c
	c, v = osgx.imgui.slider_float("Intensity##pt", state.point_intensity, 0.0, 30.0)
	state.point_intensity = v
	changed = changed or c
	if changed and state.active_demo == "Point": apply_state()

# directional_section / sphere_section / spot_section follow the same shape
# (Sphere adds a "Source Radius" slider 0..3; Spot adds Direction, Inner/Outer
# Cone (deg), Source Radius, and clamps inner < outer so GLSL's
# smoothstep(cos(outer), cos(inner), ...) stays well-formed).

lights = osgx.pbr.LightSet.create(root.stateSet)
gizmos = osgx.LightGizmos(lights, root, 0.4, 10.0)
root.children.append(gizmos)

gui = osgx.imgui.Widget(viewer)
gui.addSection("Directional", directional_section)
gui.addSection("Point", point_section)
gui.addSection("Sphere", sphere_section)
gui.addSection("Spot", spot_section)
```

## Known gaps

No `HookList`-style helper (mirroring osgSlug's `HookList`) yet for composing
multiple fragment-stage hooks on one Program — `osgx_DirectLighting()` is the
first hook, added by hand since there's only one so far. `PBRIBL.cpp`'s
`evaluateIBL()` and the final tonemap/composite step are candidates for the
same treatment once a real second consumer needs to override one
specifically.
