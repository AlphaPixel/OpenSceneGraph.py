# Headless rendering and visual checks

Render a real scene, capture the framebuffer to a PNG, and Read it back —
without opening a window on the user's desktop or needing an X server at
all. This is the default way to verify "does this render right" before
handing anything graphical to the user.

Sibling doc: [`03-headless-frames.md`](03-headless-frames.md) covers testing
callbacks/events with **no GL context at all**. Use this doc when the thing
under test needs cull + draw + pixels.

Requirements: Linux, `osgx` built with `OSGX_WITH_EGL` (check
`hasattr(osgx.platform, "createEGLWindow")`), an EGL driver with the device
platform (verified on NVIDIA; Mesa should work but is unverified).

## The recipe (identical on kernel and tmux backends)

```python
import os, sys
os.environ.pop("DISPLAY", None)                # proves nothing needs X
os.environ["OSG_THREADING"] = "SingleThreaded"
sys.path[:0] = ["/abs/.../BUILD-g++-13.3.0-NOASAN", "/abs/.../OpenSceneGraph.py/examples"]

from OpenSceneGraph import *
import pyosg_repl

viewer = pyosg_repl.headless_viewer(640, 480)  # EGL pbuffer, viewport + perspective set
viewer.sceneData = scene
viewer.camera.viewMatrix = osg.Matrixd.lookAt(eye, center, up)  # or a cameraManipulator

pyosg_repl.repl(viewer, globals())
```

Then, per check, in any later cell:

```python
ctl = _osg_repl_controller
result = ctl.complete(ctl.capture_framebuffer("/abs/path/check.png", label="what"))
```

…and Read `/abs/path/check.png`. `result` has `size`, `frame_number`,
`label`, etc. Use absolute paths — the session's cwd is not yours.

The canonical, test-proven version of this setup is
`test/aipython_scene.py:setup_source()`; `test/osg_aipython_kernel.py` and
`test/osg_aipython_tmux.py` run it end to end on each backend and
pixel-check the result. If this doc and those tests disagree, the tests win.

- **Kernel backend**: `repl()` returns immediately; frames render between
  cells. Never `await` a capture here (see `01-core.md` §6) — `complete()`.
- **tmux backend**: `repl()` embeds an IPython prompt and blocks, so write
  the setup to a script and launch it as the tmux command
  (`cd /tmp && env -u DISPLAY python3 /abs/script.py`); don't paste it.
  Only `_osg_repl_controller` exists in the namespace — `repl()`'s return
  value is never assigned while its prompt is running.
- **No aipython at all**: `ViewerREPLController(viewer)` +
  `ctl.complete(...)` works in plain Python/pytest, no event loop
  (`test/osg_headless.py`).

## Context: GL version, profile, MSAA

`headless_viewer()` seeds its traits from `osg.DisplaySettings.instance`,
exactly like a windowed viewer, so the same knobs apply:

```python
osg.DisplaySettings.instance.glContextVersion = "3.3"
osg.DisplaySettings.instance.glContextProfileMask = 0x1  # core (GLX/EGL bit values)
viewer = pyosg_repl.headless_viewer(640, 480, samples=4) # samples overrides MSAA
```

(or `OSG_GL_CONTEXT_VERSION` / `OSG_GL_CONTEXT_PROFILE_MASK` /
`OSG_MULTI_SAMPLES` in the environment). Defaults: the driver's highest
**compatibility** context (4.6 compat on NVIDIA) and **no MSAA** — so edges
alias more than a typical windowed run unless you pass `samples`. Captures
from a multisampled pbuffer come back already resolved.

To confirm what you actually got, query the live context from a draw
callback (PyOpenGL; set `PYOPENGL_PLATFORM=egl` before importing it):

```python
import OpenGL.GL as gl
viewer.camera.finalDrawCallback = lambda ri: print(
	gl.glGetIntegerv(gl.GL_CONTEXT_PROFILE_MASK), gl.glGetString(gl.GL_VERSION)
)
```

(Do that BEFORE `repl()` — see "final-draw callbacks" below.)

## Choosing how to verify (cheapest first)

Image tokens scale with pixel area (roughly `width * height / 750`: ~640 for
800x600, ~160 for 400x300). One capture is cheap; sweeps and comparisons
are not. Pick the cheapest check that actually answers the question:

1. **Numbers, not pictures** — zero image tokens. For "did it render / is
   this the right color / is anything covering this region / did the edge
   antialias", check pixels in code (the tests in `test/osg_headless*.py`
   do exactly this). stdlib only:

   ```python
   image = result["image"]  # capture_framebuffer_image(), or osgDB.readImageFile(path)
   data = memoryview(image).tobytes()  # tightly packed rows, no GL row padding
   n = len(data) // (image.s * image.t)  # components per pixel (3 = RGB, 4 = RGBA)

   def pixel(x, y):
   	i = (y * image.s + x) * n
   	return tuple(data[i:i + n])

   import collections
   histogram = collections.Counter(data[i:i + 3] for i in range(0, len(data), n))
   coverage = 1 - histogram[bytes((51, 51, 102))] / (image.s * image.t)  # vs. clear color
   ```

   Row 0 of a `readPixels()` capture is the bottom row (GL convention);
   check orientation with an asymmetric scene before trusting `y` on a
   reloaded file.
2. **Render smaller** — `headless_viewer(400, 300)` is faithful (no
   resampling). Not for resolution-dependent effects (SSAO radius, pixel
   text, blur kernels): those change with size.
3. **Preview next to the full-size file** —
   `ctl.capture_framebuffer(path, preview_downscale=2)` also writes
   `<name>.preview.png` at 1/2 per axis (1/4 the area/tokens), box-averaged
   on the CPU via `osg.Image.scaleImage()`. Read the preview first; open the
   original only when something looks off. `capture_texture()` takes it too.
4. **Contact sheet for more than two or three images** — one image of many
   thumbnails costs about one image, and side-by-side makes inconsistencies
   obvious. `osg.Image.copySubImage()` + `scaleImage()` can tile captures
   natively (unlabeled — keep the tile order alongside it).

## Gotchas

- **Set the view.** `headless_viewer()` sets viewport + a perspective
  projection but no view matrix; with no manipulator and no view you're
  looking from the origin down -Z and will likely capture only clear color.
- **No input.** Nothing feeds OSG's event queue, so manipulators and picking
  won't react to anything. Drive state directly (matrices, uniforms), or use
  synthetic events (`03-headless-frames.md`).
- **X11-only helpers are unavailable/no-ops**: window title (so
  `controls.input.locked`'s retitle is silently skipped), cursor, monitors,
  always-on-top. Input locking itself is moot — there's no window to touch.
- **Final-draw callbacks**: the controller installs its capture hook in
  `camera.finalDrawCallback` and chains whatever was already there. Assign
  your own final-draw callback **before** `repl()`; assigning one after
  replaces the hook and every later capture raises `RuntimeError`
  ("...was replaced..."). Any C++ or Python draw callback is callable from
  Python (`cb(renderInfo)`), so a callback of your own can also call
  `_osg_repl_controller._capture_callback` itself if you must reassign.
- **Multi-pass pipelines work unchanged** — RTT/MRT G-buffers, fullscreen
  passes and live GPU environment bakes all render headless
  (`test/osg_headless_gbuffer.py` runs `examples/pyosg-gbuffer.py`
  unmodified in both modes). A live `osgx.Environment(hdr)` bake completes
  within the first frame (its PRE_RENDER cameras run before the lighting
  pass), so no warm-up frames are needed.
- **`capture_texture()` keeps alpha**: an RGBA attachment's background is
  usually `(0, 0, 0, 0)` and shows as white/checkerboard in image viewers,
  while `capture_framebuffer()` is RGB. Compare pixel values, not looks.
- **Examples bring GL defaults**: importing `pyosg_example` (every example
  does) sets GL 4.6 core profile on `osg.DisplaySettings.instance` for every
  later context in the process — fixed-function drawables render nothing
  under core. To use an example's `build_scene()` in a session whose
  contexts are configured elsewhere, set `PYOSG_EXAMPLE_DEFAULTS=0` before
  the import (skips its env and GL defaults; the `osgx.Library` is still
  created). User-set `OSG_GL_CONTEXT_VERSION`/`OSG_GL_CONTEXT_PROFILE_MASK`
  always win. Nothing is written to `os.environ`, so child processes are
  unaffected either way. Running the example in its own process remains the
  most faithful check.
- **Many viewers per process are fine** — every headless context on a GPU
  shares one EGL display, reference-counted; closing one viewer never
  affects the others.
- **Time-driven effects**: freeze them before capturing
  (`18-deterministic-captures.md`); with no vsync, headless frames run
  uncapped and "N frames later" means very little wall time.
- **Build vs installed libs** still apply (osgx `aipython/00-index.md`):
  a stale `~/local` `libosgxd.so` without the pbuffer path ignores
  `traits.pbuffer`, tries (and, with `DISPLAY` unset, fails) to open an X11
  window, and `headless_viewer()` raises "EGL pbuffer context could not be
  created".

## When NOT to render

For "does this shader compile/link" questions, the no-render check is faster:
dump `prog.shaders`/`sh.source` from the Python scene graph and compile them
in a bare EGL+PyOpenGL context. Render only when the answer depends on
pixels.
