# Building GPU-only, one-shot particle/burst effects live

Patterns for instanced GPU effects (fire, explosions, shockwaves — a swarm of
quads driven by a formula) built live via REPL. First built out in
`examples/pyosg-fire.py`; design/TODO for that specific effect lives in
`ai/context-todo-particles.md`, not here — this file is the reusable
technique.

## 1. Per-instance "seed" data: hash `gl_InstanceID`, don't reach for an SSBO

If per-instance data (emission direction, size variance, phase) is
read-once and never changes after upload, derive it from `gl_InstanceID`
with an in-shader hash instead of an SSBO + CPU-side random buffer:

```glsl
float hash11(float p) {
	p = fract(p * 0.1031);
	p *= p + 33.33;
	p *= p + p;
	return fract(p);
}

vec4 hash14(float p) {
	return vec4(hash11(p+0.13), hash11(p+7.71), hash11(p+23.9), hash11(p+91.7));
}
```

No buffer object, no numpy RNG array, no upload step. An SSBO earns its keep
only once something actually *writes* per-instance state over time (a
compute-shader velocity sim, or multiple independently-triggered effects each
needing their own origin) — not just to read constants once.

## 2. One-shot triggering: a plain `triggerTime` uniform, not a looping `fract()`

For an effect that fires once, drive it from `osg_SimulationTime`
(auto-provided every frame) and a single `triggerTime` uniform, defaulted far
in the past so it's invisible until triggered:

```glsl
uniform float osg_SimulationTime;
uniform float triggerTime = -1000.0;
uniform float duration = 1.2;

float t = (osg_SimulationTime - triggerTime) / duration; // NOT fract()'d
```

An envelope like `smoothstep(0,0.08,t) * (1-smoothstep(0.5,1.0,t))` doubles
as both the grow/shrink curve and the "invisible before t=0 and after t=1"
gate — no separate visibility toggle needed.

```python
def trigger(node, viewer):
	node.stateSet.uniforms["triggerTime"] = float(viewer.frameStamp.simulationTime)
```

Bind number keys to different nodes/presets (`osgGA.GUIEventHandler`,
`ea.type == osgGA.GUIEventAdapter.KEYDOWN`, `ea.key == ord("1")`) for
instant hands-on comparison of variants.

## 3. Additive-blend saturation dominates the read of the effect — tune it first

With a few hundred instances overlapping in a small screen area under
`BlendFunc(GL_ONE, GL_ONE)`, even modest per-quad brightness sums to solid
white fast:

- Weight any secondary color-driving term (e.g. a height-based bias) low
  relative to the primary noise term — `n * 1.0 + heightBias * 0.15`, not
  `heightBias * 0.5`. Too high washes out noise detail into a flat blob.
- Multiply final alpha by a damping factor (~0.5–0.6) so one quad's
  contribution stays below full brightness, leaving room for overlaps to sum
  into mid-ramp colors instead of instantly clipping white.

## 4. A Program hot-swap does NOT reset uniforms already bound on the StateSet

Extends [`15-shader-hotswap.md`](15-shader-hotswap.md). Swapping just the
`Program` (`setAttributeAndModes(newProgram, ON|OVERRIDE)`) leaves any
uniform already explicitly set from Python (`ss.uniforms["duration"] = 2.5`)
bound on the StateSet — it silently overrides the new shader's own
`uniform float duration = 1.2;` GLSL default. If a hot-swap changes intended
defaults, explicitly re-set every uniform that changed.

Reading a uniform's current value back out is `.value`, not `.getFloat()` or
index `[0]`: `fire.stateSet.uniforms["duration"].value`.

## 5. Verifying a fast one-shot effect: force a known `t`, don't chase real-time screenshots

A `duration=1.2s` burst is easy to miss with `capture_framebuffer()` (see
[`01-core.md`](01-core.md) rule 6). Set `triggerTime` to a known offset in
the past instead of triggering "now" and hoping the capture lands mid-animation:

```python
now = float(viewer.frameStamp.simulationTime)
node.stateSet.uniforms["triggerTime"] = now - 0.4  # force t ~= 0.4/duration, right now
```

For a flat/ground-plane effect (a shockwave ring, anything not billboarded),
also consider the default trackball angle can leave it nearly edge-on and
hidden behind a brighter overlapping effect — a temporary top-down
`viewer.camera.viewMatrix = osg.Matrix.lookAt(...)` (gets overwritten by the
live `CameraManipulator` next frame, so capture immediately after) rules that
out before assuming the geometry is broken.

## 6. `del viewer.eventHandlers[i]` can corrupt a LATER handler's Python identity

With `[DebugHandler, HandlerA, HandlerB]`, `del viewer.eventHandlers[1]`
leaves a surviving `HandlerB` that comes back from `__getitem__` as a bare
base-class `osgGA.GUIEventHandler` — Python-side attributes set in its own
`__init__` are gone, and its `handle()` override silently stops firing
(falls back to the C++ base no-op). Not yet root-caused.

**Workaround:** overwrite in place instead of delete —
`viewer.eventHandlers[i] = new_handler` preserves identity correctly. Avoid
`del`-ing a middle element of `eventHandlers` if anything after it needs to
keep working.

## 7. Don't guard a MappingProxy assignment with an existence check first

`ss.uniforms[key] = value` already creates-or-updates on its own
(`UniformsTag::apply()` in `pyosg/osg/State.hpp`). Writing
`if key in ss.uniforms: ss.uniforms[key] = value` makes the assignment
*conditional on the uniform already existing* — silently no-ops a node's
very first trigger, since construction only sets the GLSL default, not a
real bound uniform, until something actually assigns to it. An unconditional
assignment through a `MappingProxy`/`ValueMappingProxy` is already the safe,
correct form; adding an existence check in front of it is closer to
introducing a bug than preventing one.

## 8. Nested one-shot effects need a recursive `trigger()`, not a deeper positional walk

When a builder wraps several effect groups in per-position
`MatrixTransform`s — one level deeper than a flat 2–4 child layout a
`trigger(node, viewer)` originally assumed — recurse to leaf nodes instead of
adding a depth parameter:

```python
def trigger(node, viewer):
	now = float(viewer.frameStamp.simulationTime)

	def walk(n):
		if isinstance(n, osg.Group):
			for child in n.children:
				walk(child)
		else:
			n.stateSet.uniforms["triggerTime"] = now

	walk(node)
```

Strict superset of flat-layout behavior, and handles arbitrarily deeper
nesting for free.

## 9. Multi-instance variety: randomize kwargs per instance, not shared state

When every tunable parameter is already "just a kwarg that flows straight to
a uniform," giving each instance independently `random.uniform()`-jittered
kwargs at construction time is close to free — prefer N independently
parameterized instances of an existing single-instance builder over one
shared preset placed N times, when the builder is already kwargs-shaped.

## 10. Extending a deliberately-minimal ImGui "bin": add a knob only when needed

`osgx.imgui` is intentionally not a general Dear ImGui wrapper — a small,
fixed set of "knob" primitives (`slider_float`, `checkbox`, `radio_group`,
...) each returning a `(changed, value)` tuple, since Python values aren't
mutable references the way ImGui's C++ `&value` out-params expect. Add a
primitive only when a concrete control is needed:

- `button(label) -> bool`
- `color_edit3(label, r, g, b) -> (changed, r, g, b)`

Both are one-line `ImGui::` wrappers in `~/dev/osgx/src/ImGui.cpp` +
`ext/python/osgx-imgui.cpp`, no new C++ classes. **C++-first, as always**
(see [[feedback_cpp_first_design]]): the primitive lives in `osgx::imgui`
proper, Python just calls it.

Two sliders in *different* panel sections sharing the exact same label
collide on the same ImGui ID — `Panel::draw()` only wraps a section in
`PushID` when `expand=True`, so a naive per-layer helper reusing the raw
uniform name as the label (`"duration"` for fire, shockwave, smoke, embers
alike) silently merges all four sliders' drag state. Fix: prefix every
control label with its section name ("Fire Duration", "Shockwave Duration", ...).

A slider that *reads* a uniform's `.value` needs that uniform to already
exist on the `StateSet` (unlike writing, reading is not create-or-update).
Fragment-only tuning knobs that were only ever given a GLSL default (never
assigned from Python) don't exist as a real uniform the first time a slider
section tries to read them. Fix: seed every slider's uniform to its known
default once, unconditionally, right before building the section — not a
guarded "if missing" check (same antipattern as point 7, on the read side).
