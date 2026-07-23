# Core rules for any OSG.py + aipython REPL session

Universal, hit-more-than-once lessons. Read this before driving `viewer.frame()`
live, writing any callback, or sending multi-line code through a tmux-backed
session.

## 1. Launch `pyosg_repl.py` as the top-level script, never from inside an already-running `ipython3`

`examples/pyosg_repl.py`'s `repl(viewer, namespace)` embeds its own IPython
shell (`InteractiveShellEmbed`) when driven from a terminal. If you first
launch a bare `ipython3` in the tmux session and then call `repl(...)` from
*inside* that prompt, you get:

```
MultipleInstanceError: An incompatible sibling of 'InteractiveShellEmbed' is
already instanciated as singleton: TerminalInteractiveShell
```

IPython's `traitlets` singleton machinery only allows one shell class instance
at a time, and the already-running top-level `ipython3` claimed that slot.

**Fix:** run the script directly as the entry point --
`../examples/pyosg_repl.py` (or `python3 pyosg_repl.py`) from the build
directory -- so `repl()` is the *first* thing to create a shell, not the
second. If you need a custom scene instead of the module's default empty
`osg.Group()`, edit `pyosg_repl.py`'s `if __name__ == "__main__":` block
directly (it's meant to be edited per-session) rather than trying to drive it
from a pre-existing prompt.

## 2. Bind every free variable in a C++-invoked callback as a default argument, never rely on closure/global lookup

This is the single most expensive lesson in this whole document, confirmed
independently **six separate times** across draw callbacks, `osgDebug.imgui`
section callbacks, `debug=<callable>` deletion callbacks, and
`osg.NodeCallback`/`updateCallback`:

```python
# BROKEN -- will raise NameError: name 'osg' is not defined, unpredictably,
# from inside whatever C++ call path invokes it (render thread, update
# traversal, a destructor, an imgui section draw):
spin_xform.updateCallback = lambda node, nv: setattr(
    node, "matrix", osg.Matrix.rotate(nv.frameStamp.simulationTime * 0.4, osg.Vec3(0, 0, 1))
)

# WORKS -- default arguments are bound to the function object once, at
# def-time, with zero runtime namespace lookup:
spin_xform.updateCallback = lambda node, nv, osg=osg: setattr(
    node, "matrix", osg.Matrix.rotate(nv.frameStamp.simulationTime * 0.4, osg.Vec3(0, 0, 1))
)
```

Root cause is not fully nailed down (an IPython embedded-namespace subtlety),
and it is **not** simply "stale reference from before some event" -- a
*brand new* closure, defined the instant after confirming the same name
resolves fine at the top-level prompt, fails identically. Only
default-argument binding is reliable. `import X` inside the callback body
works too (it's the module-shaped special case of the same trick), but
default-argument binding covers non-module objects as well.

**Consequences of getting this wrong vary by callback type, and can look
like a totally unrelated bug:**
- A `DrawCallback` exception crashes the whole render thread/process.
- An `osgDebug.imgui` section callback exception corrupts ImGui's frame state
  (exception fires after `NewFrame()` but before `Render()`); the *next*
  frame's `NewFrame()` hits a native C++ `assert()` and hard-aborts the
  process -- no Python `try/except` can catch this after the fact.
- A `NodeCallback`/`updateCallback` exception does **not** crash the
  process, but silently breaks the update traversal every frame: queued
  `capture_framebuffer()`/`capture_texture()` requests stop resolving, the
  window stops responding to mouse input, and it looks exactly like a
  hung/dead session -- not a Python exception. Check `_osg_repl_state` and
  try a plain `viewer.frame()` to surface the real traceback if a session
  looks frozen.
- A `debug=<callable>` deletion callback (see
  [`20-object-lifetime.md`](20-object-lifetime.md)) hits the same error from
  an ordinary Python refcounting/GC destructor call, on the main thread, no
  render loop involved at all.

If you must keep a callback resilient against *future* bugs, also: set any
one-shot "done" flag before the risky code (not after), wrap the whole body
in `try/except Exception:` with an except-clause that cannot itself throw,
and write results straight to a file rather than a shared Python
object -- but note `try/except: pass` makes failures *silent, not absent*;
verify with something that logs to a file, don't assume an empty-looking
result means "nothing happened."

## 3. `os.environ.setdefault()`, never `.update()`, in any shared helper module

If a helper (like `pyosg_repl.py`) is imported *after* the caller has already
set its own `OSG_WINDOW`/`OSG_THREADING`/etc., an unconditional
`os.environ.update(...)` in the helper silently clobbers the caller's values
back to the helper's own defaults -- and since `osgViewer::Viewer::realize()`
doesn't read `OSG_WINDOW` until the *first* `frame()` call, this can happen
well after the import, making it look like an unrelated timing/display bug.
Use `setdefault()` so the helper only fills in values nothing else has set.

## 4. Multi-line code sent through a tmux-backed session is fragile

IPython's terminal autoindent adds its own indentation on top of whatever the
pasted text already has, and can cascade into `IndentationError`s that get
worse with every subsequent line -- or, in a triple-quoted string, silently
insert garbage whitespace that happens to be harmless for GLSL but would
*not* be harmless in real code after the string closes.

- Send `%autoindent off` as the very first command in any tmux session before
  sending multi-line `def`/`for`/`if` blocks. This is a permanent per-process
  setting, set it once and forget it.
- Prefer single-line forms (lambdas, `exec("...\n...")` wrapping a whole
  block as one string) for anything defined live, especially callbacks.
- After sending a large block, don't trust the `execute()` call's own
  returned `text` -- it can be a stale mid-flight snapshot. Call `capture()`
  again explicitly to see the true, settled state before concluding a block
  succeeded or failed.

**The most reliable way to run a nontrivial script live**: write it to a real
file, then send exactly these two single-line statements (each safe from
autoindent, since neither has an indented continuation):

```python
p = "/absolute/path/to/script.py"
exec(compile(open(p).read(), p, "exec"), locals())
```

Two non-obvious requirements packed into that one line, both confirmed by
hitting them directly (2026-07-22):

- **Use the real absolute path as the `compile()` filename, never a fake
  short name** like `"script.py"`. This embedded shell's `VerboseTB`
  formatter uses `stack_data`/`executing` to introspect source by filename;
  a name that doesn't resolve on disk makes `executing` itself throw
  (`executing.executing.NotOneValueFound: Expected one value, found 0`),
  which then **replaces the real traceback** with a confusing, wrong-looking
  one (observed: a frame that appeared to be `aipython/integration.py`'s
  shell-exit code, attributed to the wrong file/line entirely) --
  wasted real debugging time before the actual cause (a plain `NameError` in
  the executed script) was found. Once the filename is a real, readable
  path, tracebacks are accurate: correct file, correct line, correct source
  shown.
- **Pass `locals()` explicitly as the exec globals dict.** In this embedded
  shell, `globals() is locals()` is **False** at the top-level prompt --
  almost certainly IPython's top-level-`await` support compiling each cell
  as an async wrapper function, whose `f_locals` differs from its
  `f_globals`. Everything `pyosg_repl.py`'s `from OpenSceneGraph import *`
  put in the namespace (`osg`, `osgGA`, `viewer`, ...) lives in `locals()`,
  not `globals()`. A bare top-level reference to `osg` still resolves fine
  (`LOAD_NAME` checks locals then globals), but a bare `exec(code)` with no
  explicit args uses `(globals(), locals())` of the calling frame -- so any
  `def` executed that way gets `__globals__` bound to the globals-only dict,
  which lacks `osg`, and calling that function later raises `NameError: name
  'osg' is not defined` even though top-level statements in the very same
  exec'd block worked fine. Passing `locals()` as the single explicit arg
  makes exec use that (correct, `osg`-containing) dict for both globals and
  locals of the executed code.

## 5. `help(x)` hangs the session

Opens a pager; the tmux pane blocks waiting for pager input, showing
`idle: false` forever. Send `"q"` to unstick it, then confirm recovery with a
throwaway `execute()` before continuing. Prefer `x.__doc__` or introspecting
`__init__`'s docstring directly instead.

## 6. Screenshots: use the controller's queued capture, not a bare `readPixels()`

```python
# BROKEN from plain top-level/idle-prompt code -- the GL context is not
# necessarily current on this thread between frame() calls, and readPixels()
# will silently return all-zero (black) data with no exception:
img = osg.Image()
img.readPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE)

# WORKS -- queued into the render loop's own finalDrawCallback, where the
# context is guaranteed current:
result = await _osg_repl_controller.capture_framebuffer("/tmp/shot.png")
```

This looks like "the scene is broken/black" when it's actually just the
capture method. If a screenshot comes back solid black, first rule out the
capture path itself (e.g. by checking the window directly, or by confirming
`_osg_repl_state["frames"]` is actually incrementing) before assuming the
scene has a bug.

`capture_framebuffer()`/`capture_texture()` are confirmed reliable on the
**terminal/tmux-embedded** `repl()` flavor. The **ipykernel/Jupyter-kernel**
backend hit a hard crash (session died outright, `session has not been
started` on the next call) on the exact same `await capture_framebuffer(...)`
call in one session -- not yet root-caused, but treat kernel-backend
screenshot capture as unproven until it's retested.

## 7. Backend choice: tmux vs. kernel

- **tmux**: visible, attachable (`tmux attach -t <name>`), and the flavor
  `pyosg_repl.repl()`'s screenshot capture is actually confirmed working on.
  Model-loading and other slow calls can appear to "hang" in the `execute()`
  tool's returned text (it can be a stale snapshot) even though the
  underlying command finished fine -- always `capture()` again to check
  ground truth before assuming something is stuck.
- **kernel**: structured JSON results, better for programmatic
  inspection/completion -- but slow-to-return `execute()` calls have been
  observed hanging for 120s+ on things that complete quickly via tmux (e.g.
  glTF model loading), and the async screenshot-capture path crashed the
  session outright once. Treat as less proven for this project's live-viewer
  workflow than tmux, currently.

If a session using either backend appears completely frozen (no window
response, capture requests never resolving), check rule 2 first -- it's the
most common actual cause, not a backend bug.

## 8. Replacing a live scene graph could abort the whole process (fixed 2026-07-22, verify it's still fixed)

`viewer.frame()`'s binding used to release the GIL unconditionally for the
whole call. OSG defers actual GL-object teardown (dropping the last
`ref_ptr` on an old `Program`/`Uniform`/etc. after a scene-graph replacement)
to a flush pass that can run *inside* a later `frame()` call -- if that drop
is the last reference to a pybind11-tracked Python-wrapped object, its
destructor needs the GIL to deregister the wrapper, which wasn't held. This
aborted the entire process (`pybind11::handle::dec_ref() ... PyGILState_Check()
failure`, `Aborted (core dumped)`) -- not a Python exception, the whole tmux
session and viewer window die, no traceback to work from unless you already
suspect this.

**Trigger, confirmed via a from-scratch minimal repro**: attach a scene with
a `Program`+`Uniform` to an already-running (already-`frame()`'d) viewer,
replace it with a second such scene, keep calling `frame()` -- crashed
reliably every time. Zero relation to what the replacing scene actually
contains; purely "replace a live scene graph while already running," which
every scripted example avoids by building the whole scene *before* the first
`frame()` call. A REPL workflow -- build a scene, tweak it, rebuild and
re-`exec()` the whole script again -- hits exactly this shape.

**Fix**: `pyosg/pyosgViewer.cpp`'s `frame()` binding now only releases the
GIL when `threadingModel != SingleThreaded`. Since this project's standing
default is always `OSG_THREADING=SingleThreaded`, there's no concurrency
benefit lost, only the hazard removed. **As of 2026-07-22 this fix exists
only in a locally rebuilt, uncommitted tree** -- if a fresh checkout hits
this exact abort, this is the first thing to check/reapply, not a new
mystery to re-debug from scratch.
