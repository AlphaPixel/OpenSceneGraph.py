# Live GLSL hot-swapping for shader-side debugging

For debugging shader-side logic bugs in a live REPL session, the most
trustworthy technique is patching the actual GLSL source and hot-swapping a
new `osg.Program` onto the live node's `StateSet` -- not reimplementing the
shader's math in Python/NumPy and comparing numbers. Matrix-convention
mistakes (row vs. column vector, OSG-vs-GLSL upload transpose) are easy to
get subtly wrong reimplementing shader math by hand, and a live edit that
visualizes the GPU's *actual* computation (e.g. color-coding which branch of
an `if` a fragment took) sidesteps all of that ambiguity.

**How:** find the `Program`'s owning node -- often a child `Geode`, not the
`Camera` itself (e.g. `composite_cam.children[0].stateSet`, since the shader
is typically attached to the fullscreen-quad `Geode`, not the camera's own
`StateSet`). Then, live in the REPL:

```python
src = COMPOSITE_FRAGMENT_SHADER  # the original global string
assert src.count(marker) == 1  # a non-unique match silently patches the wrong occurrence
src2 = src.replace(marker, patched_substring, 1)
p = osg.Program(shaders=(
    osg.Shader(osg.Shader.VERTEX, FULLSCREEN_VERTEX),
    osg.Shader(osg.Shader.FRAGMENT, src2)
))
node.stateSet.setAttributeAndModes(p, osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE)
```

No restart needed, no loss of current camera position/state.

## The deeper trap: a live variable reassignment silently not reaching the running callback

Two layers of this, both real, both cost significant debugging time before
being pinned down:

**Layer 1 -- wrong variable.** A per-frame callback may read a
**closure-captured local from setup time** (e.g. `light_proj`, captured when
the callback was defined) rather than the live object property it looks like
it should read (e.g. `shadow_cam.projectionMatrix`, which may have since
changed). Reassigning the object property silently no-ops if the callback
never actually reads it. Always grep the *actual callback body* for what it
reads, don't assume based on the object's name alone.

**Layer 2 -- even the right variable name can fail.** Reassigning the
correct bare name (e.g. `light_proj = new_value`) at the IPython prompt --
even via `exec(open(path).read())` -- can silently fail to reach the
namespace a running callback actually reads from, **despite `globals() is
callback.__globals__` printing `True`**. Confirmed via
`callback.__globals__['light_proj']` showing a stale value with a different
`id()` than a bare `light_proj` lookup gave in the same command. Several
"the fix had zero effect" conclusions turned out to be false negatives caused
by this, not evidence the fix itself was wrong.

**The reliable pattern -- write through the callback's own `__globals__`
explicitly:**

```python
cb = shadow_cam.preDrawCallback
g = cb.__globals__          # the namespace the callback ACTUALLY reads from
g['light_proj'] = new_value
g['shadow_cam'].projectionMatrix = new_value  # keep any live object property in sync too
```

Then **re-verify** by rebuilding the dependent live GPU uniform from `g[...]`
and diffing it against the actual uniform value, before trusting a live
reassignment took effect and drawing any conclusion from the visual result.

See [`01-core.md`](01-core.md) rule 2 for the closely-related (but distinct)
free-variable `NameError` trap in callbacks defined at the prompt -- that one
is about a name never resolving at all; this one is about a name resolving to
a *stale* value in a namespace that looks, but isn't, the same one.
