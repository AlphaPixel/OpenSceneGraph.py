# Building GPU-only, one-shot particle/burst effects live

Patterns for building instanced GPU effects (fire, explosions, shockwaves --
anything "a swarm of quads driven by a formula") from scratch in a live REPL
session, plus the sharp edges hit doing exactly that. First built out in
`examples/pyosg-fire.py`; full design/TODO for that specific effect lives in
`ai/context-todo-particles.md`, not here -- this file is the reusable
technique, that one is the project status.

## 1. Per-instance "seed" data: hash `gl_InstanceID`, don't reach for an SSBO

If the per-instance data (emission direction, size variance, phase) is
**read-once and never changes after upload**, derive it from `gl_InstanceID`
with an in-shader hash instead of building an SSBO + CPU-side random buffer:

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
only once something actually **writes** per-instance state over time (a
compute-shader velocity sim, or multiple independently-triggered effects each
needing their own origin) -- not just to read constants once.

## 2. One-shot triggering: a plain `triggerTime` uniform, not a looping `fract()`

For an effect that fires once (not an ambient/looping particle emitter),
drive it from `osg_SimulationTime` (auto-provided every frame, no Python setup
needed) and a single `triggerTime` uniform, defaulted far in the past so it's
invisible until triggered:

```glsl
uniform float osg_SimulationTime;
uniform float triggerTime = -1000.0;
uniform float duration = 1.2;

float t = (osg_SimulationTime - triggerTime) / duration; // NOT fract()'d
```

An envelope like `smoothstep(0,0.08,t) * (1-smoothstep(0.5,1.0,t))` does
double duty as both the visual grow/shrink curve and the "invisible before
t=0 and after t=1" gate -- no separate visibility toggle needed. From Python:

```python
def trigger(node, viewer):
	node.stateSet.uniforms["triggerTime"] = float(viewer.frameStamp.simulationTime)
```

Bind number keys to different nodes/presets (`osgGA.GUIEventHandler`,
`ea.type == osgGA.GUIEventAdapter.KEYDOWN`, `ea.key == ord("1")`) for instant
hands-on comparison of variants without touching the REPL.

## 3. Additive-blend saturation dominates the read of the effect -- tune it first

With a few hundred instances overlapping in a small screen area under
`BlendFunc(GL_ONE, GL_ONE)`, even modest per-quad brightness sums to solid
white fast. Before anything else looks right:

- Weight any secondary color-driving term (e.g. a height-based bias) **low**
  relative to the primary noise term -- `n * 1.0 + heightBias * 0.15`, not
  `heightBias * 0.5`. Too high washes out all noise detail into a flat blob.
- Multiply final alpha by a damping factor (`~0.5-0.6`) so a single quad's
  contribution stays below full brightness, leaving room for overlapping
  quads to sum into the mid-ramp colors instead of instantly clipping to the
  ramp's white end.

Get this wrong and the effect looks like "a blurry white/yellow blob," not
fire -- confirmed directly, this was the very first result before tuning.

## 4. A Program hot-swap does NOT reset uniforms already bound on the StateSet

Extends [`15-shader-hotswap.md`](15-shader-hotswap.md). Swapping just the
`Program` (`setAttributeAndModes(newProgram, ON|OVERRIDE)`) leaves any
uniform **already explicitly set from Python** (`ss.uniforms["duration"] =
2.5`) bound on the StateSet -- it silently overrides the new shader's own
`uniform float duration = 1.2;` GLSL default. If a hot-swap changes intended
default values, explicitly re-set every uniform that changed; don't rely on
the new GLSL default taking effect.

Reading a uniform's current value back out (e.g. to compute a standalone
loop's re-trigger delay) is `.value`, not `.getFloat()` or index `[0]`:
`fire.stateSet.uniforms["duration"].value`.

## 5. Verifying a fast one-shot effect: force a known `t`, don't chase real-time screenshots

A `duration=1.2s` burst is easy to completely miss with
`capture_framebuffer()` (see [`01-core.md`](01-core.md) rule 6) -- several
attempts came back solid black despite the effect visibly working live in the
actual window at the same moment. For a deterministic screenshot, set
`triggerTime` to a known offset in the past instead of triggering "now" and
hoping the capture lands mid-animation:

```python
now = float(viewer.frameStamp.simulationTime)
node.stateSet.uniforms["triggerTime"] = now - 0.4  # force t ~= 0.4/duration, right now
```

For a flat/ground-plane effect (a shockwave ring, anything not billboarded),
also consider that the default trackball camera angle can leave it nearly
edge-on and hidden behind a brighter overlapping effect -- a temporary
top-down `viewer.camera.viewMatrix = osg.Matrix.lookAt(...)` (note: gets
overwritten by the live `CameraManipulator` on the next frame, so re-capture
immediately after setting it) is a fast way to rule that out before assuming
the geometry itself is broken.

## 6. `del viewer.eventHandlers[i]` can corrupt a LATER handler's Python identity

Confirmed live: with `[DebugHandler, HandlerA, HandlerB]`, running
`del viewer.eventHandlers[1]` left a 2-element list, but the surviving
`HandlerB` came back from `__getitem__` as a bare base-class
`osgGA.GUIEventHandler` object -- a Python-side attribute set in `HandlerB`'s
own `__init__` was gone (`hasattr(h, "some_attr")` was `False`). Its `handle()`
override would silently stop firing (falls back to the C++ base no-op). Not
the same bug as the already-fixed SSBO/array `__delitem__` issue -- this is a
different container/binding, not yet root-caused.

**Workaround:** overwrite in place instead of delete -- `viewer.eventHandlers[i]
= new_handler` preserved identity correctly in the same session, immediately
after the `del` corruption. Avoid `del`-ing a middle element of
`eventHandlers` if anything after it needs to keep working.

## 7. Don't guard a MappingProxy assignment with an existence check first

`ss.uniforms[key] = value` already creates-or-updates on its own (see
`UniformsTag::apply()` in `pyosg/osg/State.hpp` -- CASE 3 explicitly handles
"mutation or creation"). Writing `if key in ss.uniforms: ss.uniforms[key] =
value` doesn't make it safer, it makes the assignment **conditional on the
uniform already existing** -- which silently no-ops a node's very first
trigger, since `build_fire()`-style construction only sets the GLSL default,
not a real bound uniform, until something actually assigns to it.

Confirmed live: `pyosg-fire.py`'s `trigger()` had exactly this guard. It
looked reasonable (defensive existence check before use) and even *worked* in
testing, because earlier debug commands had already force-created the uniform
via direct assignment moments before -- masking the bug. A pristine node's
first-ever key-triggered burst did nothing, while the handler's "triggered"
console print fired unconditionally regardless (the print doesn't know
whether the guarded assignment inside `trigger()` actually ran). Root-caused
fast by installing a temporary diagnostic `GUIEventHandler` that read the
uniform back and let it raise `KeyError` instead of silently doing nothing --
turned an invisible no-op into a traceback pointing at the exact guard. The
general lesson: an unconditional assignment through a `MappingProxy`/
`ValueMappingProxy` is *already* the safe, correct form; adding an existence
check in front of it is closer to introducing a bug than preventing one.

## 8. Nested one-shot effects need a recursive `trigger()`, not a deeper positional walk

`build_multiburst()` wraps several full `build_fire()`/`build_shockwave()`/etc.
groups in per-position `MatrixTransform`s -- one extra `Group` level beyond
`build_explosion()`'s flat 2-4 child layout the original `trigger(node,
viewer)` assumed (`node.children if isinstance(node, osg.Group) else
(node,)`, one level only). Rather than special-case the new depth, `trigger()`
became a small recursive walk:

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

This is a strict superset of the old one-level behavior (still correct for
`build_explosion()`'s flat groups) and now also handles arbitrarily deeper
nesting for free. General lesson: when a "walk this node's direct children"
helper meets a second caller that nests one level deeper, recursing to a
leaf-node test is usually less code than adding a depth parameter or a
second bespoke walker -- and it stops being a landmine for the *next* caller
that nests differently.

## 9. Multi-instance variety: randomize kwargs per instance, not shared state

`build_multiburst()`'s four bursts call `build_fire()`/`build_smoke()`/
`build_embers()` with independently `random.uniform()`-jittered kwargs (and a
`colorsys.hsv_to_rgb()`-randomized hue per burst -- see point 10) instead of
building one shared preset and repositioning copies of it. Since every
tunable parameter in this file was already "just a kwarg that flows straight
to a uniform" (the file's own running theme), giving each instance its own
independently-rolled kwargs at construction time was close to free -- no new
plumbing, just calling the same `build_*()` functions with different
arguments in a loop. Worth remembering as a default move any time a "several
of X" layer is requested: prefer N independently-parameterized instances of
an existing single-instance builder over one shared preset placed N times,
when the builder is already kwargs-shaped.

## 10. Extending a deliberately-minimal ImGui "bin": add a knob only when a real one is needed

`osgx.imgui` is intentionally not a general Dear ImGui wrapper -- a small,
fixed set of "knob" primitives (`slider_float`, `checkbox`, `radio_group`,
...) each returning a `(changed, value)` tuple, since Python values aren't
mutable references the way ImGui's C++ `&value` out-params expect (see
`~/dev/osgx/osgx/ImGui.hpp`'s own "knobs, not frameworks" framing). Extending
it for `pyosg-fire.py`'s live-tuning panel added exactly two new primitives,
both because a concrete control was needed, not speculatively:

- `button(label) -> bool` -- a thin `ImGui::Button()` wrapper, needed because
  the panel's "Triggers" section fires presets from the GUI instead of only
  the keyboard.
- `color_edit3(label, r, g, b) -> (changed, r, g, b)` -- wraps
  `ImGui::ColorEdit3` with the same tuple-out-param pattern as everything
  else in the module, needed to retint `build_fire()`'s new `midColor`/
  `coreColor` uniforms live.

Both are one-line `ImGui::` wrappers in `~/dev/osgx/src/ImGui.cpp` +
`ext/python/osgx-imgui.cpp` bindings, no new C++ classes -- matching the
existing `slider_float`/`checkbox` shape exactly. **C++-first, as always**
(see [[feedback_cpp_first_design]]): the primitive lives in `osgx::imgui`
proper, Python just calls it, not a Python-side shim reimplementing
`ImGui::Button` semantics.

A repeated gotcha worth flagging again here, distinct from point 6's
header-vs-control collision: **two sliders in *different* panel sections
sharing the exact same label collide on the same ImGui ID.**
`Panel::draw()` does not wrap each section's callback in its own `PushID` (it
only does that for `expand`-flagged sections), so `slider_float_nudge`'s own
internal `PushID(label)` is the *only* ID scoping in play. A naive per-layer
helper reusing the raw uniform name as the label (`"duration"` for fire,
shockwave, smoke, and embers alike) would silently merge all four sliders'
drag state into one. Fix: prefix every control label with its section name
("Fire Duration", "Shockwave Duration", ...) -- unique text across the whole
panel, not just within one section.

One more small pattern from the same panel: a slider that reads a uniform's
`.value` needs that uniform to already exist on the `StateSet` (unlike
*writing*, reading is not create-or-update). `build_fire()`/`build_smoke()`
only ever explicitly set the uniforms their own kwargs cover -- fragment-only
tuning knobs like `noiseScale`/`scrollSpeed`/`warpStrength`/`maxAlpha` were
never assigned from Python, only given a GLSL default, so `ss.uniforms[name]`
doesn't exist yet the first time a slider section tries to read it. Fix:
seed every slider's uniform to its known default once, unconditionally, right
before building the section -- not a guarded "if missing" check (that's the
antipattern from point 7 again, just on the read side instead of the write
side), just a plain assignment that happens to reproduce a value already
correct for the uniforms that *were* set, and creates the ones that weren't.
