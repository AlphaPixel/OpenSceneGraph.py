# Inspecting a scene graph you didn't build

When you're handed a live viewer (or a loaded scene) with no prior context --
someone else's REPL session, a scene loaded from a file, a scene built by
code you haven't read -- don't reconstruct its structure by re-reading
source or guessing at `StateSet` contents. Fire `GatherVisitor` at it and get
a real read: every node's type/name, every attached `Program` (plus each
component `Shader`'s type and a source preview), and every `Uniform` (name +
type), all via `osg.notice()`.

```python
from pyosg_visitor import GatherVisitor

osg.setNotifyLevel(osg.NotifySeverity.NOTICE)  # GatherVisitor reports via osg.notice()

viewer.sceneData.accept(GatherVisitor())
```

`examples/pyosg_visitor.py` lives in `examples/`, same directory as
`pyosg_repl.py` -- a plain `from pyosg_visitor import GatherVisitor` resolves
directly when your script also lives in `examples/`. From a subdirectory
(e.g. `examples/pyosg-lighting/`), do the same `sys.path` fixup
`11-sketchfab.py` uses for `pyosg_repl`:

```python
import pathlib, sys

examples_dir = pathlib.Path(__file__).resolve().parent.parent

if str(examples_dir) not in sys.path:
    sys.path.insert(0, str(examples_dir))

from pyosg_visitor import GatherVisitor
```

## "Which Python variable is this?" -- the `namespace=` hint

Pass `locals()`/`globals()` in and any gathered object whose `.addr` matches
a bare name in that dict gets an extra hint appended:

```python
viewer.sceneData.accept(GatherVisitor(namespace=globals()))
```

```
[gather] Camera 'Composite HUD' (bound to local: 'hud_cam')
  [gather] Uniforms: ['colorTex', 'depthTex', 'invProjectionMatrix', ...]
    invProjectionMatrix: type=Type.FLOAT_MAT4 (bound to local: 'inv_proj_u')
    colorTex: type=Type.INT
```

This is a *reverse* lookup (object `.addr` -> matching names in the dict you
handed it, computed once at construction), not a live namespace walk -- it
only finds **bare top-level names**. An object only reachable via a chain
(e.g. `hud_cam.stateSet.attributes[PROGRAM]`, never assigned its own name)
won't get a hint, and that's expected, not a bug to chase. Confirmed useful
in practice: on a real multi-pass deferred-shading scene
(`examples/pyosg-mrt.py`), every module-level-bound object picked up its
correct name on the first try, while inline-assigned values (`uniforms["x"]
= 0`, never bound to a local) correctly showed no hint.

## The two real binding gaps this proved out (fixed 2026-08-01)

Building `GatherVisitor` surfaced two genuine gaps in the Python bindings,
not just missing features in the visitor itself:

- **`osg.Node` had no non-creating `getStateSet()`.** Only `.stateSet`
  (`getOrCreateStateSet()`) was exposed, so a read-only visitor walking an
  arbitrary graph would have forced a new empty `StateSet` onto every node
  it touched just by checking for one. Fixed via `osg.getStateSet(node)` --
  a **module-level function**, deliberately not a `Node` method, matching
  the existing `osg.computeLocalToWorld(nodePath)` free-function precedent.
  Kept off `node.<TAB>` on purpose, so it's never reached for by accident in
  place of `.stateSet`.

- **`osg.StateSet` had no way to read a `StateAttribute` back out once
  attached.** `setAttribute()`/`setAttributeAndModes()` existed;
  `getAttribute()` did not. Fixed via `StateSet.attributes[]`, a
  `MappingProxy` keyed by `StateAttribute::Type`, same shape as
  `.uniforms`/`.textureAttributes`:

  ```python
  ss.attributes.append(program)                           # key inferred from program.type
  ss.attributes[osg.StateAttribute.PROGRAM] = program      # explicit key, must match program.type
  ss.attributes[osg.StateAttribute.PROGRAM] = (program, osg.StateAttribute.OVERRIDE)
  ```

  Confirmed the polymorphic downcast works correctly -- `ss.attributes[PROGRAM]`
  returns a real `osg.Program`, not a bare `osg.StateAttribute`.

**Known limitation, not yet hit in practice:** `.attributes[]` only ever
addresses `member=0` (`StateAttribute::getMember()`, overridden by
`ClipPlane`/`Light` for OpenGL's numbered fixed-function slots like
`GL_CLIP_PLANE0..5`/`GL_LIGHT0..7`). Neither `ClipPlane` nor `Light` is
bound in Python yet, so this hasn't bitten anything real -- but a `StateSet`
holding multiple attributes of the *same* `Type` at different members would
currently only show one via `.attributes[]`/`keys()`.

## See also

- [`15-shader-hotswap.md`](15-shader-hotswap.md) -- once `GatherVisitor` has
  told you which `Program`/`Shader` you're looking at, this is how you patch
  its GLSL and hot-swap a replacement live.
- [`20-object-lifetime.md`](20-object-lifetime.md) -- a different concern:
  this file is about scene *structure* (what's attached, what it's called);
  that one is about object *lifetime* (is it really destroyed, not just
  detached). Reach for `debug=`/`.referenceCount` from that doc when the
  question is "did this actually get freed," not "what's in this scene."
