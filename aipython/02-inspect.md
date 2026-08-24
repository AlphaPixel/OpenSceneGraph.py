# Inspecting a scene graph you didn't build

When handed a live viewer or a loaded scene with no prior context, don't
reconstruct its structure by re-reading source or guessing at `StateSet`
contents. Fire `GatherVisitor` at it: every node's type/name, every attached
`Program` (plus each `Shader`'s type and a source preview), every `Uniform`
(name + type), all via `osg.notice()`.

```python
from pyosg_visitor import GatherVisitor

osg.setNotifyLevel(osg.NotifySeverity.NOTICE)  # GatherVisitor reports via osg.notice()

viewer.sceneData.accept(GatherVisitor())
```

`pyosg_visitor.py` lives in `examples/`, alongside `pyosg_repl.py` — a plain
`from pyosg_visitor import GatherVisitor` resolves when your script also
lives there. From a subdirectory, fix `sys.path` first:

```python
import pathlib, sys

examples_dir = pathlib.Path(__file__).resolve().parent.parent

if str(examples_dir) not in sys.path:
	sys.path.insert(0, str(examples_dir))

from pyosg_visitor import GatherVisitor
```

## "Which Python variable is this?" — the `namespace=` hint

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

This is a reverse lookup (`.addr` → matching names, computed once at
construction), not a live namespace walk — it only finds bare top-level
names. An object only reachable via a chain (e.g.
`hud_cam.stateSet.attributes[PROGRAM]`, never assigned its own name) gets no
hint; that's expected.

## Reading a `StateSet`'s attached attributes

`osg.getStateSet(node)` is a **module-level function**, deliberately not a
`Node` method — `node.stateSet` (`getOrCreateStateSet()`) forces a new empty
`StateSet` onto every node it touches, which a read-only visitor must avoid.

`StateSet.attributes[]` is a `MappingProxy` keyed by `StateAttribute::Type`,
same shape as `.uniforms`/`.textureAttributes`, and does real polymorphic
downcasting (`ss.attributes[PROGRAM]` returns a real `osg.Program`):

```python
ss.attributes.append(program)                           # key inferred from program.type
ss.attributes[osg.StateAttribute.PROGRAM] = program      # explicit key, must match program.type
ss.attributes[osg.StateAttribute.PROGRAM] = (program, osg.StateAttribute.OVERRIDE)
```

**Known limitation:** `.attributes[]` only ever addresses `member=0`
(`StateAttribute::getMember()`, overridden by `ClipPlane`/`Light` for
OpenGL's numbered fixed-function slots). Neither is bound in Python yet, so a
`StateSet` holding multiple attributes of the same `Type` at different
members currently only shows one via `.attributes[]`/`keys()`.

## See also

- [`15-shader-hotswap.md`](15-shader-hotswap.md) — once you know which
  `Program`/`Shader` you're looking at, patch its GLSL and hot-swap it live.
- [`20-object-lifetime.md`](20-object-lifetime.md) — scene *structure* (this
  file) vs. object *lifetime* (is it really destroyed, not just detached).
