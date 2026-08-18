# Deterministic captures of time-driven GPU effects

`capture_framebuffer()` makes the GL context current; it does **not** choose
which instant of an animation gets rendered. Triggering an effect and racing a
capture against the next `viewer.frame()` is therefore inherently unreliable.

The fix is an effect-local clock with two modes:

- normal playback derives elapsed time from `osg_SimulationTime - triggerTime`;
- inspection playback supplies an explicit elapsed age in seconds.

This was tested live with `examples/pyosg-praxis.py`: two framebuffer captures
of a shell frozen at age `1.2` seconds, taken `0.5` real seconds apart while
the viewer continued to frame, had identical SHA-256 hashes and were
byte-for-byte equal.

## Shader contract

Add a uniform whose negative value means "use realtime":

```glsl
uniform float osg_SimulationTime;
uniform float triggerTime = -1000.0;
uniform float effectAge = -1.0;

float elapsed = effectAge >= 0.0 ? effectAge : osg_SimulationTime - triggerTime;
float t = clamp(elapsed / duration, 0.0, 1.0);
```

Use `elapsed`, not `osg_SimulationTime`, for **every** time-varying part of
the effect that needs to match the captured instant: movement, noise scroll,
flicker, size envelopes, and fragment breakup. Freezing only the normalized
`t` while a noise lookup still uses realtime leaves the result nondeterministic.

Seed the uniform from Python during construction so the control code can read
or write it immediately:

```python
ss.uniforms["effectAge"] = -1.0
```

## Trigger and scrub helpers

For a nested effect, recurse to drawable-owning leaves. Starting realtime
playback must explicitly clear a previously frozen age:

```python
def trigger(node, viewer):
	now = float(viewer.frameStamp.simulationTime)

	def walk(n):
		if isinstance(n, osg.Group):
			for child in n.children:
				walk(child)
		else:
			n.stateSet.uniforms["effectAge"] = -1.0
			n.stateSet.uniforms["triggerTime"] = now

	walk(node)

def set_age(node, effect_age):
	"""Freeze at elapsed seconds; pass a negative value to resume realtime."""

	def walk(n):
		if isinstance(n, osg.Group):
			for child in n.children:
				walk(child)
		else:
			n.stateSet.uniforms["effectAge"] = effect_age

	walk(node)
```

Age is deliberately measured in seconds rather than normalized phase. Layers
with different durations then stay synchronized to one source event: at age
`1.2`, every layer evaluates itself 1.2 seconds after the trigger and applies
its own duration naturally.

## Live capture workflow

In a tmux-backed `pyosg_repl.py` session, freeze the effect, then use the
controller's queued capture (not a top-level `readPixels()`):

```python
set_age(effect, 1.2)
await _osg_repl_controller.capture_framebuffer("/tmp/effect-age-1.2.png")
```

If a person may be at the same keyboard/mouse while this runs, wrap it in
`_osg_repl_controller.locked_input()` (see `examples/pyosg_repl.py`'s
`AgentInputLock`). This is exactly the scenario that feature exists for: a
user keypress that re-triggers or otherwise mutates the effect (e.g.
`pyosg-praxis.py`'s `1` re-fires `trigger()`) landing on the same frame as
`set_age()`/the capture, unfreezing or invalidating the very state being
inspected.

```python
with _osg_repl_controller.locked_input():
	set_age(effect, 1.2)
	await _osg_repl_controller.capture_framebuffer("/tmp/effect-age-1.2.png")
```

For a proof rather than a plausible-looking screenshot, capture the same
frozen frame twice after allowing realtime frames to advance, then compare the
files outside the REPL. The exposure window here is longer than the single
capture above (a real `sleep`, not one queued frame), so wrapping it in
`locked_input()` matters more, not less:

```python
with _osg_repl_controller.locked_input():
	set_age(effect, 1.2)
	await _osg_repl_controller.capture_framebuffer("/tmp/effect-a.png")
	await asyncio.sleep(0.5)
	await _osg_repl_controller.capture_framebuffer("/tmp/effect-b.png")
```

```bash
sha256sum /tmp/effect-a.png /tmp/effect-b.png
cmp -s /tmp/effect-a.png /tmp/effect-b.png
```

This proves only the frozen nodes are deterministic. To capture a whole
composite effect, every visible time-driven layer must implement the same
clock contract; hide or freeze unrelated animated scenery, UI, camera shake,
and particle layers before comparing capture bytes.

## Short realtime video captures

For a short MP4 rather than a one-off PNG, use the model-controls facade's
callback-driven recorder:

```python
_osg_repl_controls.capture.video("/tmp/take.mp4", fps=24, duration=5)
```

It samples in the final-draw callback on a monotonic wall-clock schedule and
streams raw RGB frames directly to FFmpeg. It is the right tool for recording
a user's live camera manipulation because the call returns immediately and
leaves input unlocked by default. Pass `lock_input=True` when a script is
posing the camera or updating uniforms and a human must not race it:

```python
_osg_repl_controls.capture.video(
	"/tmp/deterministic-take.mp4",
	fps=24,
	duration=5,
	lock_input=True,
)
```

For a reproducible video, first set every time-driven visible effect to its
explicit age (and keep unrelated animation frozen) before starting the
recorder. The video sampler controls *which wall-clock moments are captured*;
it does not make shader time deterministic by itself.

Current implementation note: video readback still uses synchronous
`osg.Image.readPixels()` in the final-draw callback. It avoids the terminal
IPython `asyncio.sleep()` scheduling granularity, but it is not yet a
PBO/fence-backed asynchronous GPU transfer.

## Realtime handoff

After inspecting an age, either resume the existing effect with
`set_age(effect, -1.0)` or restart it with `trigger(effect, viewer)`. Prefer
the latter when the effect may already have elapsed past its duration.

`examples/pyosg-praxis.py` is the current minimal working reference. Promote
this contract into `pyosg-fire.py` only as a coherent change across its fire,
shockwave, smoke, and ember shaders; a partial conversion gives a misleading
"frozen" composite whose remaining layers still race realtime.
