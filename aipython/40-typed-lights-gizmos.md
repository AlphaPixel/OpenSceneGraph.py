# osgx typed direct lights (`osgx.pbr.LightSet`) + `osgx.gizmo`

Renamed off `40-lighting.tmp.md` 2026-08-16 once the dice shader sync (the one blocker the `.tmp`
version was waiting on) landed and was confirmed live -- see "Contract rollout, confirmed live"
below. `~/dev/osgx`'s SSBO/contract branch this doc now describes was uncommitted as of writing;
check `git log -1 -- src/osgx/PBR.hpp` if anything here looks stale.

## What this is

`osgx::pbr::LightSet` (C++: `src/osgx/PBR.hpp`/`src/PBR.cpp`, Python: `osgx.pbr.LightSet`) is a
typed direct-light rig. As of 2026-08-16 its per-light data (`osgx.pbr.MAX_LIGHTS` == 6 slots) lives
in a single `std430` Shader Storage Buffer Object (`osgx_LightBuffer`/`osgx_lights[]`, binding
`osgx.pbr.LIGHT_SSBO_BINDING` == 3) plus one `osgx_lightCount` uniform -- **not** the seven parallel
flat uniform arrays (`lightPosIntensity`/`lightColor`/`lightType`/`lightDir`/`lightSpotAngles`/
`lightSourceRadius`/`lightCount`) an earlier revision of this doc described. The Python-facing
`LightSet` API (`setPoint`/`setDirectional`/`setSpot`/`setCount`) is unchanged by that swap -- only
what's actually on the GPU/StateSet changed. Three real types -- Point, Directional, Spot -- plus a
"Sphere" light that is NOT a fourth type: it's `setPoint(..., sourceRadius>0)`, see below.

Every consumer shader reaches the light array through one hook call,
**`osgx_DirectLighting(N, V, worldPos, mat)`** -- declared by `osgx.pbr.DIRECT_LIGHTING_DECL` (splice into
your own fragment shader's `#pragma osgx::pbr ...` line, alongside `MATERIAL_STRUCT`) and defined by
`osgx.pbr.DIRECT_LIGHTING_HOOK_DEFAULT`, a second, self-contained FRAGMENT shader object added to the
same `Program`. Python callers don't need to hand-assemble that second shader object --
`osgx.pbr.makeDirectLightingHookShader()` returns it ready to append:

```python
program = osg.Program(name="my-shader", shaders=(
	osg.Shader(osg.Shader.VERTEX, vertex_source),
	osg.Shader(osg.Shader.FRAGMENT, osgx.resolveShaderLibs(fragment_source)),
	osgx.pbr.makeDirectLightingHookShader(),
))
```

This is the same "hook" pattern `osgSlug` uses (a base shader owns `main()` and only *declares* a
fixed entry point; each consumer supplies -- or accepts the library default for -- that entry
point's *definition* as a separate compiled shader object). It exists specifically so a per-light
dispatch loop lives in exactly one place instead of being hand-copied into every consumer's
`main()` -- see "Contract rollout, confirmed live" below for why that mattered in practice.

`osgx::gizmo` (C++: `src/osgx/Gizmos.hpp`/`src/Gizmos.cpp`, Python: `osgx.gizmo`) is the matching
debug visualization: real depth-tested marker geometry for point/sphere/spot, plus a
non-depth-tested overlay for directional (which has no position to place a marker at). Both take a
live `osgx.pbr.LightSet` directly now (not a raw `StateSet`) and read it through its typed
accessors (`getCount`/`getType`/`getPosIntensity`/`getColor`/`getDirection`/`getSpotAngles`/
`getSourceRadius`) instead of `stateset.getUniform("light...")`.

## Minimal live REPL setup

```python
lights = osgx.pbr.LightSet.create(root.stateSet)  # allocates the SSBO buffer (size MAX_LIGHTS, zero-initialized) + osgx_lightCount on root.stateSet

lights.setCount(1)  # how many of the 6 slots are actually read by osgx_DirectLighting()'s loop this frame

# Point -- inverse-square falloff, ideal (zero-size) specular highlight
lights.setPoint(0, osg.Vec3(2.5, -2.5, 6.0), osg.Vec3(0.85, 0.55, 0.30), 12.0)

# Directional -- "travel direction" (KHR_lights_punctual convention), no position, no falloff
lights.setDirectional(0, osg.Vec3(0.2, 0.4, -1.0), osg.Vec3(0.75, 0.70, 0.60), 3.0)

# Spot -- cone-attenuated point light; angles in RADIANS (osg has no DegreesToRadians -- use math.radians())
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

# Read back any field live -- e.g. to sanity-check a round-trip, or to drive a gizmo/UI from
# whatever's already set:
lights.getType(0), lights.getPosIntensity(0), lights.getColor(0), lights.getSourceRadius(0)
```

`LightSet.create()` REPLACES the SSBO buffer + `osgx_lightCount` on that StateSet -- don't call it
twice on the same live StateSet if you've already populated lights there (e.g. a `--torches`-style
rig via `add_torch_rig()`, see below), or you'll zero it out. If you just need to WRAP an
already-populated StateSet's LightSet, construct `osgx.pbr.LightSet()` and set both `.ss` and
`.lights` directly instead of calling `create()`.

A rig-building helper looks like this (ported from `pyosg-match4-dice.py`'s `add_torch_rig()`,
confirmed live 2026-08-16 -- see below):

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

```python
gizmos = osgx.gizmo.createLightGizmos(lights, root, 0.4, 10.0)  # (LightSet, scene node for directional's bound-sizing, minMarkerRadius, spotConeLength)

root.children.append(gizmos.markers)  # real depth-tested geometry -- point/sphere circles, spot cone
root.children.append(gizmos.overlay)  # non-depth-tested POST_RENDER plane+arrow -- directional only
```

- `gizmos.markers`' point/spot markers are REAL scene geometry and DO get depth-occluded by actual
  room geometry -- e.g. placing a spot light above a room's true ceiling height hides its marker
  inside the roof mesh even though the light itself still shades correctly (no shadow-mapping in
  this system, so occlusion only affects the debug marker's visibility, never the shading math).
  Keep test-light Z below the real ceiling if you want to see the marker.
- `gizmos.overlay` is unaffected by any of that (`GL_DEPTH_TEST` off, `POST_RENDER`).
- Toggle `gizmos.markers.nodeMask = 0` / `gizmos.overlay.nodeMask = 0` to hide them without
  removing them (e.g. for a clean screenshot comparison).
- **Still-open osgx TODO (not yet fixed)**: light gizmo geometry currently contributes to the
  scene's computed bounds (`getBound()`), which pulls `TrackballManipulator` auto-fit/`home()`
  outward when a light sits far from the real geometry.

## Contract rollout, confirmed live 2026-08-16

The whole point of `osgx_DirectLighting()` existing is that `pyosg_dice.py`'s `FRAGMENT_SHADER_IBL`
used to hand-copy the per-light dispatch loop, and had drifted out of sync with the correct,
type-dispatching version `osgx::gltf::pbribl::createPBRIBLScene()`'s own shader carried (Directional
was nearly invisible on dice, Spot didn't show a true cone edge, `sourceRadius` was a no-op for
both -- Point was the only fully-correct case). Both shaders now call the SAME
`osgx_DirectLighting()` hook, so that drift class cannot recur -- confirmed by construction, not just
by testing, since there is only one copy of the dispatch loop left in the codebase
(`DIRECT_LIGHTING_HOOK_DEFAULT` in `PBR.hpp`).

Live confirmation this session, driving `pyosg-match4-dice.py --repl` (no `--torches`, `--hdr`
omitted, `--env neutral.gltf`, real `--scene mm04.gltf` backdrop loaded):

- **`add_torch_rig()`'s SSBO round-trip**: built a 4-light Point rig via the snippet above; every
  `getType`/`getPosIntensity`/`getColor` read back exactly what was written. Screenshot showed all
  four corner torches visibly lighting the backdrop wall/floor near their positions -- warm glow,
  correct falloff, everything else unlit stayed at the flat IBL baseline.
- **Directional**: `setDirectional()` with a downward-ish travel direction produced a UNIFORM flood
  across the whole backdrop (walls, ceiling) with no falloff and no bogus "position at the world
  origin" artifact -- i.e. exactly what the old buggy dice-only loop got wrong, now correct on the
  backdrop AND (see next point) the dice.
- **Dice pick up direct light through the same hook**: a strong, saturated blue Point light aimed
  at the board produced a clear blue tint/specular shift on the die faces themselves, not just the
  backdrop -- proof `pyosg_dice.py`'s `FRAGMENT_SHADER_IBL` (which shares the SAME `LightSet`/SSBO
  on the scene-root StateSet) is really calling `osgx_DirectLighting()`, not silently falling back to
  IBL-only shading.
- **Spot with `sourceRadius=0.5`**: `getSpotAngles(0)` read back `(cos(12°), cos(28°)) ==
  (0.9781, 0.8829)`, confirming the pre-cosine packing round-trips through the SSBO exactly.
  `gizmos.markers`' wireframe cone rendered aimed correctly at the board, and the lit region on the
  board visibly matched the cone's footprint (attenuated at the edge, not a hard cutoff).
- **`createDirectionalOverlay`**: switching back to Directional rendered the wireframe plane+arrow
  overlay aimed at the board, warm-tinted flood lighting matching the light's color, arrow pointing
  in the correct travel direction.

Nothing here required a workaround or exposed a new bug -- this was a clean pass validating the
SSBO restructure, the `osgx_DirectLighting()` hook rollout to both consumers, and the gizmo API's
`LightSet`-based rewrite, all in one live session.

## Live ImGui control panel (per-light-type sections, ported from `examples/osgx-lights.cpp`)

`osgx.imgui`'s Python bindings are function-style wrappers (`slider_float`, `color_edit3`,
`checkbox`, `radio_group`, `button`, `text`, `separator`, `input_text` -- all return
`(changed, *new_values)` tuples), NOT the raw C++ `ImGui::` namespace the C++ example uses
directly. There is no `SliderFloat3`, no `PushID`/`PopID`, no `SameLine`. Build a vec3 control from
three `slider_float` calls, and give every widget label a `##<section-scope>` suffix -- `Panel::draw()`
(`src/ImGui.cpp`) only `PushID`s a section when `options.expand=True`, so plain sections share one
global Dear ImGui id namespace and identical labels across sections (every type has a "Position"/
"Color"/"Intensity") will fight over the same drag state without the suffix.

This exact pattern -- one collapsible section per light type, an Activate/Deactivate button driving
a single shared "live" `LightSet` slot, live sliders scoped per section -- was live-built and
confirmed working 2026-08-16 (previous session); user reaction: "this is amazing." The `LightSet`
calls inside `apply_state()` below are the SAME `setPoint`/`setDirectional`/`setSpot`/`setCount`
signatures as before the SSBO restructure -- nothing here needed to change for the new backing
store. Full working script:

```python
import math

active_slot = 0  # the ONLY light -- lightCount stays 0 until you Activate a section

class LightsState:
	def __init__(self):
		self.active_demo = None

		self.directional_direction = [0.2, 0.4, -1.0]
		self.directional_color = [0.75, 0.70, 0.60]
		self.directional_intensity = 3.0

		self.point_position = [2.5, -2.5, 6.0]
		self.point_color = [0.85, 0.55, 0.30]
		self.point_intensity = 12.0

		self.sphere_position = [2.5, -2.5, 6.0]
		self.sphere_color = [0.85, 0.55, 0.30]
		self.sphere_intensity = 12.0
		self.sphere_radius = 0.7

		self.spot_position = [0.0, -4.0, 8.0]
		self.spot_direction = [0.0, 1.0, -0.35]
		self.spot_color = [0.95, 0.85, 0.65]
		self.spot_intensity = 40.0
		self.spot_inner_deg = 15.0
		self.spot_outer_deg = 32.0
		self.spot_source_radius = 0.0

state = LightsState()

def apply_state():
	if state.active_demo is None:
		lights.setCount(0)
		return

	lights.setCount(1)

	if state.active_demo == "Directional":
		lights.setDirectional(active_slot, osg.Vec3(*state.directional_direction), osg.Vec3(*state.directional_color), state.directional_intensity)
	elif state.active_demo == "Point":
		lights.setPoint(active_slot, osg.Vec3(*state.point_position), osg.Vec3(*state.point_color), state.point_intensity)
	elif state.active_demo == "Sphere":
		lights.setPoint(active_slot, osg.Vec3(*state.sphere_position), osg.Vec3(*state.sphere_color), state.sphere_intensity, sourceRadius=state.sphere_radius)
	elif state.active_demo == "Spot":
		lights.setSpot(
			active_slot, osg.Vec3(*state.spot_position), osg.Vec3(*state.spot_direction), osg.Vec3(*state.spot_color),
			state.spot_intensity, math.radians(state.spot_inner_deg), math.radians(state.spot_outer_deg), state.spot_source_radius,
		)

def activate_button(name):
	active = state.active_demo == name
	osgx.imgui.text("ACTIVE" if active else "(inactive)")
	if osgx.imgui.button(f"Activate##{name}"):
		state.active_demo = name
		apply_state()
	if active and osgx.imgui.button(f"Deactivate##{name}"):
		state.active_demo = None
		apply_state()

def vec3_sliders(prefix, scope, values, lo, hi):
	changed = False
	for i, axis in enumerate(("X", "Y", "Z")):
		c, v = osgx.imgui.slider_float(f"{prefix} {axis}##{scope}{axis}", values[i], lo, hi)
		values[i] = v
		changed = changed or c
	return changed

def directional_section(ri):
	activate_button("Directional")
	changed = vec3_sliders("Direction", "dirdir", state.directional_direction, -1.0, 1.0)
	c, r, g, b = osgx.imgui.color_edit3("Color##dir", *state.directional_color)
	state.directional_color[:] = [r, g, b]
	changed = changed or c
	c, v = osgx.imgui.slider_float("Intensity##dir", state.directional_intensity, 0.0, 10.0)
	state.directional_intensity = v
	changed = changed or c
	if changed and state.active_demo == "Directional": apply_state()

# ... point_section / sphere_section / spot_section follow the same shape, see
# git history / the live session transcript for the full versions (Sphere adds a
# "Source Radius" slider 0..3; Spot adds Direction, Inner/Outer Cone (deg), Source Radius,
# and clamps inner < outer so GLSL's smoothstep(cos(outer), cos(inner), ...) stays well-formed).

lights = osgx.pbr.LightSet.create(root.stateSet)
gizmos = osgx.gizmo.createLightGizmos(lights, root, 0.4, 10.0)
root.children.append(gizmos.markers)
root.children.append(gizmos.overlay)

gui = osgx.imgui.Widget(viewer)
gui.addSection("Directional", directional_section)
gui.addSection("Point", point_section)
gui.addSection("Sphere", sphere_section)
gui.addSection("Spot", spot_section)
```

## Known gaps / open questions (as of 2026-08-16)

1. Gizmo geometry contributing to `getBound()` -- see the Gizmos section above; not yet fixed.
2. `osgx.pbr` C++ has a `HookList`-style helper (mirroring osgSlug's `HookList`) for composing
   MULTIPLE fragment-stage hooks on one Program -- deliberately not built yet; `osgx_DirectLighting()`
   is the first hook, added by hand (`makeDirectLightingHookShader()` or the raw C++ equivalent) since
   there's only one so far. `PBRIBL.cpp`'s `evaluateIBL()` and final tonemap/composite step are
   noted in osgx's `TODO.md` as the next candidates for the same hook treatment, once a real second
   consumer needs to override one of them specifically.
