# Core rules for any OSG.py + aipython REPL session

Read this before driving `viewer.frame()` live, writing any callback, or sending
multi-line code through a tmux-backed session.

## 1. Launch `pyosg_repl.py` directly — never from inside an already-running `ipython3`

`repl(viewer, namespace)` embeds its own IPython shell (`InteractiveShellEmbed`).
Launching a bare `ipython3` first and calling `repl()` from inside it raises:

```
MultipleInstanceError: An incompatible sibling of 'InteractiveShellEmbed' is
already instanciated as singleton: TerminalInteractiveShell
```

Run the script directly (`python3 pyosg_repl.py`) so `repl()` is the first shell
created. Edit the `if __name__ == "__main__":` block for a custom scene instead
of driving a pre-existing prompt.

## 2. Bind free variables into callbacks as default args

C++-invoked callbacks (draw callbacks, `osgx.imgui` sections, `debug=` deletion
callbacks, `NodeCallback`/`updateCallback`, event handlers) can fail to resolve
names defined at the prompt after the shell embedded — `user_ns` and
`user_module.__dict__` can be separate dicts. The terminal backend merges them
at embed time, but defend anyway:

```python
spin_xform.updateCallback = lambda node, nv, osg=osg: setattr(
	node, "matrix", osg.Matrix.rotate(nv.frameStamp.simulationTime * 0.4, osg.Vec3(0, 0, 1))
)
```

Consequences differ by callback type:
- A `DrawCallback` exception crashes the render thread/process.
- An `osgx.imgui` section exception corrupts ImGui's frame state; the *next*
  frame hard-aborts the process — no `try/except` catches this after the fact.
- A `NodeCallback`/`updateCallback` exception doesn't crash but silently
  breaks the update traversal every frame — queued captures stop resolving,
  input stops responding. Check `_osg_repl_state` and try a plain
  `viewer.frame()` to surface the real traceback.
- A `debug=<callable>` deletion callback (see [`20-object-lifetime.md`](20-object-lifetime.md))
  hits the same error from an ordinary GC destructor call, main thread, no
  render loop involved.

If wrapping defensively: set a one-shot "done" flag before risky code, wrap
the body in `try/except Exception:`, write results to a file rather than a
shared Python object — `except: pass` makes failures silent, not absent.

## 3. `os.environ.setdefault()`, never `.update()`, in shared helper modules

An unconditional `os.environ.update(...)` in a helper (e.g. `pyosg_repl.py`)
clobbers a caller's already-set `OSG_WINDOW`/`OSG_THREADING`/etc. back to the
helper's defaults. `Viewer::realize()` doesn't read `OSG_WINDOW` until the
first `frame()` call, so this can look like an unrelated timing/display bug
well after import. Use `setdefault()`.

## 4. Multi-line code sent through tmux is fragile

IPython's terminal autoindent stacks on top of pasted indentation and can
cascade into `IndentationError`, or silently corrupt a triple-quoted string.

- Send `%autoindent off` as the first command in any tmux session, once.
- Prefer single-line forms (lambdas, `exec("...")`) for anything defined live.
- After a large block, call `capture()` again explicitly rather than trusting
  `execute()`'s returned text, which can be a stale snapshot.

Most reliable way to run a nontrivial script live — two single-line
statements, neither has an indented continuation:

```python
p = "/absolute/path/to/script.py"
exec(compile(open(p).read(), p, "exec"), locals())
```

Two requirements:
- Use the real absolute path as the `compile()` filename — a fake name makes
  `stack_data`/`executing` throw and replaces the real traceback with a wrong
  one pointing at unrelated code.
- Pass `locals()` explicitly. `globals() is locals()` is `False` at this
  shell's top-level prompt (top-level-await wraps each cell in an async
  function), so a bare `exec(code)` binds any `def`'s `__globals__` to a dict
  missing `osg`/`viewer`/etc., raising `NameError` only when that function is
  later called from elsewhere.

## 5. `help(x)` hangs the session

Opens a pager; the tmux pane blocks waiting for input (`idle: false` forever).
Send `"q"` to unstick it, confirm recovery with a throwaway `execute()`.
Prefer `x.__doc__` instead.

## 6. Screenshots: use the controller's queued capture, never bare `readPixels()`

```python
# BROKEN — the GL context isn't necessarily current here; silently returns
# all-zero (black) data, no exception:
img = osg.Image()
img.readPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE)

# WORKS — queued into the render loop's own finalDrawCallback, context
# guaranteed current:
result = await _osg_repl_controller.capture_framebuffer("/tmp/shot.png")
```

If a screenshot comes back black, rule out the capture path first (check the
window directly, check `_osg_repl_state["frames"]` is incrementing) before
assuming the scene is broken. Confirmed reliable on the terminal/tmux backend;
the ipykernel backend has crashed outright on this call — treat as unproven
there.

### Model controls facade

```python
controls = _osg_repl_controls

controls.input.locked = True       # swallow human mouse/keyboard input
controls.frames.target_fps = None  # uncapped — never "lock the user out"
controls.frames.target_fps = 30
controls.frames.paused = True
print(controls.status)
```

FRAME/resize/close events still pass through while input is locked.
`controls.window.always_on_top` uses `osgx.platform.alwaysOnTop()`. For a
short MP4 with no intermediate image files:

```python
controls.capture.video("/tmp/take.mp4", fps=24, duration=5)
print(controls.capture.video_status)
```

Samples in the final-draw callback on a monotonic wall-clock schedule and
streams RGB directly to FFmpeg; the call returns immediately. Pass
`lock_input=True` only when the capture must be deterministic. Readback is
still synchronous `readPixels()` in the draw callback, not yet PBO/fence-backed.
A resize during a take fails that capture.

## 7. Backend choice: tmux vs. kernel

- **tmux**: visible, attachable (`tmux attach -t <name>`), the only backend
  screenshot capture is confirmed on. `execute()`'s returned text can be a
  stale snapshot for slow calls — always `capture()` again before assuming
  something is stuck.
- **kernel**: structured JSON, better for programmatic inspection — but slow
  calls have hung 120s+ on things that finish quickly via tmux, and async
  screenshot capture has crashed the session outright. Less proven for this
  project's live-viewer workflow.

If a session looks frozen on either backend, check rule 2 first — it's the
most common actual cause, not a backend bug.

## 8. `viewer.frame()` doesn't release the GIL under `SingleThreaded`

Deliberate: OSG can drop the last `ref_ptr` on a GL-tracked object during
`frame()`'s own flush pass, and that pybind11 wrapper's destructor needs the
GIL to deregister. Releasing the GIL during `frame()` under `SingleThreaded`
(this project's standing default) aborts the process
(`PyGILState_Check()` failure, no Python traceback) the moment a live scene
graph is replaced while already running. `pyosg/pyosgViewer.cpp`'s `frame()`
binding only releases the GIL when `threadingModel != SingleThreaded` — don't
"fix" this by releasing it unconditionally.

## 9. OSG's matrix and quaternion multiplication order is reversed vs. GLSL

OSG is row-vector (`v' = v * M`), GLSL is column-vector (`v' = M * v`). A
chain that reads left-to-right in GLSL (`A * B * C_vec`, apply `C` first)
must be written reversed in Python/OSG (`C_vec_source * B * A`). Translation
lives in **row 3**, not column 3. See [`ai/context-core.md`](../ai/context-core.md)
for the full derivation.

`osg.Quat` has the same reversed convention: `q1 * q2` applied to a vector
applies `q1` first, then `q2` — opposite of the standard Hamilton product.
Don't extend this rule to a new case by analogy; verify empirically:

```python
combined = a * b
print(combined * known_vector)  # does this match "apply a, then b", or the reverse?
```

## 10. `MatrixTransform.matrix` is a live C++ alias, not a snapshot

`getMatrix()` returns `const osg::Matrix&`; reading `.matrix` aliases the
transform's native matrix. Rebuilding a pose from "rest" each frame using a
bare read compounds every update:

```python
rest = transform.matrix
transform.matrix = osg.Matrix.rotate(angle, axis) * rest  # WRONG — rest aliases the live matrix
```

Take an explicit copy once:

```python
rest = osg.Matrix(transform.matrix)

def update(node, nv):
	transform.matrix = osg.Matrix.rotate(angle, axis) * rest
	return True
```

`test/osg_Transform.py::test_matrixtransform_matrix_is_a_live_reference` locks
this down.

## 11. Title any extra debug `osgViewer.Viewer()` window

Any REPL-created `osgViewer.Viewer()` beyond the user's primary session
viewer should be titled immediately after `realize()`, before pumping visible
frames — otherwise identical-looking windows become impossible to tell apart:

```python
osgx.platform.setWindowTitle(viewer, "SOME-DESCRIPTIVE-LABEL")
```

Pick a label describing what's different about this one. Close throwaway
windows explicitly (`viewer.close()`) once done.
