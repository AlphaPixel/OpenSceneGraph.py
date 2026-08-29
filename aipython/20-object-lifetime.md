# Object introspection and lifetime debugging

Every `osg::Object` subclass in these bindings exposes a small cluster of
introspection primitives — for "what is this node actually holding" and "did
this object actually get destroyed," not just serialization.

## `.dumps()` — OSGT text serialization

```python
print(node.dumps().decode())
```

Verifies what attributes, textures, and state are actually attached to a
node/geometry without a separate viewer or tool. Works on live objects
mid-session.

## `.addr` — the real C++ memory address

A `void*` to the actual object, not a vtable-offset pointer. Use to confirm
two Python handles refer to the *same* underlying C++ object (`a.addr ==
b.addr`) rather than two separate wrappers, or to correlate with addresses
printed by C++-side `osg::notify()` output.

## `.referenceCount` — `RefCounts(cpp=N, py=M)`

The real OSG-side `ref_ptr` count and the Python-side refcount, separately.

**The `py` count is artificially inflated inside an interactive IPython
session** — `Out[]` history caching, `_`/`__`/`___`, and other REPL
bookkeeping can hold references you didn't intentionally keep. A high `py`
count does not by itself mean a leak. Removing an object from a scene graph
container only drops *one* `cpp` ref; if a Python variable (or `Out[]`
history) still points at it, the object stays fully alive.

## `debug=True` / `debug=<callable>` — ground-truth destruction proof

Pass as a kwarg to an `osg.Object`-derived constructor to attach a lifetime
probe via the object's `UserDataContainer`:

```python
node = osg.Node(debug=True)                    # notify()'s "Observing"/"Destroying"
node = osg.Node(debug=lambda addr, type_, name, deletions=deletions: ...)  # custom callback
```

**Only works for types wired into the binding layer's `kwargs_init` chain**
(see `pyosg/pyosg.hpp`'s manifest — `kwargs_base<T>` + each type's own
`kwargs_init_own`). Most `osg::Object` subclasses are, but it isn't automatic
just from deriving from `osg::Object` in C++ — a type hand-written with plain
`py::init<...>()` overloads silently rejects `debug=` (and `name=`,
`dataVariance=`) with a constructor-overload-mismatch error rather than a
clear "unsupported kwarg" message. If `debug=`/`name=` fails with
`incompatible constructor arguments`, check whether the type is in that
manifest before assuming the probe itself is broken.

Since the probe lives inside the target's own `UserDataContainer`, its
destructor fires at true C++ destruction — not "removed from the scene
graph," not "Python variable went out of scope." This is the ground-truth
tool for verifying an object is actually gone, as opposed to inferring it
from refcounts alone.

**The `debug=<callable>` callback is subject to the exact same
cross-context free-variable `NameError` as any other C++-invoked Python
callback** (see [`01-core.md`](01-core.md) rule 2) — bind anything it needs
as a default argument: `def on_delete(addr, type_, name, deletions=deletions):
...`. This applies even though the trigger here is an ordinary Python
refcounting/GC destructor call on the main thread, not the render loop or any
background thread.

## How to combine these when investigating a leak

1. `.dumps()` to see what's really attached.
2. `.addr` + `.referenceCount` together to distinguish "detached from the
   scene graph" (a removed-but-still-Python-referenced object shows `cpp` >
   0) from "actually destroyed."
3. `debug=` when you need proof, not inference — especially when the bug
   might be in the binding layer itself (proxy/container implementation),
   not application code.
