# Live GLSL hot-swapping for shader-side debugging

For debugging shader-side logic in a live REPL session, patch the actual GLSL
source and hot-swap a new `osg.Program` onto the live node's `StateSet` —
don't reimplement the shader's math in Python/NumPy and compare numbers.
Matrix-convention mistakes (row vs. column vector, upload transpose) are easy
to get subtly wrong reimplementing shader math by hand; a live edit that
visualizes the GPU's *actual* computation (e.g. color-coding which branch of
an `if` a fragment took) sidesteps that ambiguity.

Find the `Program`'s owning node — often a child `Geode`, not the `Camera`
itself (the shader is typically attached to the fullscreen-quad `Geode`, not
the camera's own `StateSet`). Then, live in the REPL:

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

To prove the old `Program`/`Shader`s actually got destroyed (not just
detached), add `debug=True` to each constructor call — see
[`20-object-lifetime.md`](20-object-lifetime.md). Requires the type to be
wired into `kwargs_init`; check the manifest if `debug=` raises a constructor
mismatch instead of trusting the swap-and-drop-the-old-ref pattern on faith.

## The deeper trap: a live variable reassignment silently not reaching the running callback

Two layers, both real:

**Layer 1 — wrong variable.** A per-frame callback may read a
closure-captured local from setup time (e.g. `light_proj`, captured when the
callback was defined) rather than the live object property it looks like it
should read (e.g. `shadow_cam.projectionMatrix`, which may have since
changed). Reassigning the object property silently no-ops if the callback
never reads it. Grep the actual callback body for what it reads — don't
assume based on the object's name alone.

**Layer 2 — even the right variable name can fail.** Reassigning the correct
bare name (`light_proj = new_value`) at the prompt — even via
`exec(open(path).read())` — can silently fail to reach the namespace a
running callback actually reads from, **despite `globals() is
callback.__globals__` printing `True`**. Verify via
`callback.__globals__['light_proj']` showing a different `id()` than a bare
`light_proj` lookup in the same command before trusting a "fix had zero
effect" conclusion.

The reliable pattern — write through the callback's own `__globals__`
explicitly:

```python
cb = shadow_cam.preDrawCallback
g = cb.__globals__          # the namespace the callback ACTUALLY reads from
g['light_proj'] = new_value
g['shadow_cam'].projectionMatrix = new_value  # keep any live object property in sync too
```

Then re-verify by rebuilding the dependent live GPU uniform from `g[...]`
and diffing it against the actual uniform value before drawing any
conclusion from the visual result.

See [`01-core.md`](01-core.md) rule 2 for the related but distinct
free-variable `NameError` trap — that one is about a name never resolving at
all; this one is about a name resolving to a *stale* value in a namespace
that looks, but isn't, the same one.
