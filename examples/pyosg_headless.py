#!/usr/bin/env python3

"""Offscreen (pbuffer) rendering for the examples, with no dependency beyond OpenSceneGraph itself
(osgx optional, for EGL). Two entry points:

- headless_viewer(): an osgViewer.Viewer already rendering into a pbuffer (pyosg_repl re-exports it
  for aipython sessions).
- install(): replaces osgViewer.Viewer with HeadlessViewer for the rest of the process, so an
  UNMODIFIED example renders N frames offscreen, writes a PNG and exits its own frame loop.
  pyosg_example calls this when the command line has --headless (or PYOSG_HEADLESS is set):

python pyosg-rtt.py --headless # egl when available, else native
python pyosg-rtt.py --headless native # OSG's own pbuffer: WGL/Cocoa/GLX (needs X)
python pyosg-rtt.py --headless egl --headless-frames 30 --headless-out /tmp/rtt.png
"""

import ctypes
import ctypes.util
import os
import pathlib
import sys

from OpenSceneGraph import osg, osgDB, osgViewer
from OpenSceneGraph.GL import GL_RGB, GL_UNSIGNED_BYTE

BACKENDS = ("egl", "native")

# Accepted on the command line/PYOSG_HEADLESS as the platform's native pbuffer.
BACKEND_ALIASES = {"glx": "native", "wgl": "native", "cocoa": "native", "auto": None}
DEFAULT_FRAMES = 10
GL_VENDOR, GL_RENDERER, GL_VERSION = 0x1F00, 0x1F01, 0x1F02

def _egl_window_factory():
	try:
		import osgx

	except ImportError:
		return None

	return getattr(osgx.platform, "createEGLWindow", None)

def resolve_backend(backend):
	"""Normalize a backend name (aliases included) to "egl", "native" or None (auto)."""

	backend = BACKEND_ALIASES.get(backend, backend)

	if backend not in (None, *BACKENDS):
		names = ", ".join(repr(name) for name in (*BACKENDS, *BACKEND_ALIASES))

		raise ValueError(f"unknown headless backend {backend!r} (expected one of {names})")

	return backend

def create_context(width, height, samples=None, backend=None):
	"""Create a pbuffer GraphicsContext; returns (gc, backend actually used).

	`backend` is "egl" (osgx.platform.createEGLWindow: Linux, osgx built with OSGX_WITH_EGL, no
	display or window system needed), "native" (OSG's per-platform pbuffer via
	osg.GraphicsContext.createGraphicsContext: WGL on Windows, Cocoa on macOS, GLX on Linux - which
	needs an X display) or None ("egl" when available, otherwise "native").

	The GL context version/profile/flags and MSAA sample count come from osg.DisplaySettings.instance
	(and so from OSG_GL_CONTEXT_VERSION, OSG_GL_CONTEXT_PROFILE_MASK, OSG_MULTI_SAMPLES, ...), as for a
	windowed viewer; `samples` overrides the latter.
	"""

	backend = resolve_backend(backend)
	create_egl_window = _egl_window_factory() if backend != "native" else None

	if backend == "egl" and create_egl_window is None:
		raise RuntimeError("the 'egl' backend requires osgx built with OSGX_WITH_EGL")

	traits = osg.GraphicsContext.Traits(osg.DisplaySettings.instance)
	traits.width = width
	traits.height = height
	traits.pbuffer = True

	# Single-buffered, so reads see what was drawn.
	traits.doubleBuffer = False

	if samples is not None:
		traits.sampleBuffers = 1 if samples else 0
		traits.samples = samples

	if create_egl_window is not None:
		backend = "egl"
		gc = create_egl_window(traits)

	else:
		backend = "native"

		# The X11 implementation targets hostName:displayNum.screenNum; elsewhere this is unused.
		traits.readDISPLAY()

		gc = osg.GraphicsContext.createGraphicsContext(traits)

	if gc is None or not gc.valid():
		hint = ""

		if backend == "native" and os.name == "nt":
			hint = " (needs WGL_ARB_pbuffer - Microsoft's GDI Generic GL 1.1 has none)"

		elif backend == "native" and sys.platform.startswith("linux"):
			hint = " (GLX needs an X display - is DISPLAY set? The 'egl' backend doesn't)"

		raise RuntimeError(f"{backend} pbuffer context could not be created{hint}")

	return gc, backend

def _setup_camera(camera, gc, width, height):
	camera.graphicsContext = gc
	camera.viewport = (0, 0, width, height)
	camera.projectionMatrix = osg.Matrixd.perspective(30.0, width / height, 1.0, 10000.0)

def headless_viewer(width=640, height=480, samples=None, backend=None):
	"""Return an osgViewer.Viewer rendering into an offscreen pbuffer; no window is shown and
	captures read the pbuffer. The viewer is SingleThreaded (draw happens inside frame(), which
	captures and draw callbacks rely on) and its camera gets a viewport and a default perspective
	projection; set its viewMatrix (or a cameraManipulator) before rendering. See create_context()
	for `samples` and `backend`.
	"""

	gc, _ = create_context(width, height, samples, backend)

	viewer = _RealViewer()

	viewer.threadingModel = osgViewer.ViewerBase.SingleThreaded

	_setup_camera(viewer.camera, gc, width, height)

	return viewer

def gl_get_string():
	"""glGetString for the CURRENT context: OSG.py's binding when present, else ctypes against the
	platform GL library. Returns a callable name -> str."""

	native = getattr(sys.modules.get("OpenSceneGraph.GL"), "glGetString", None)

	if native is not None:
		return native

	if os.name == "nt":
		lib = ctypes.WinDLL("opengl32")

	else:
		lib = ctypes.CDLL(ctypes.util.find_library("GL") or "libGL.so.1")

	fn = lib.glGetString
	fn.restype = ctypes.c_char_p
	fn.argtypes = [ctypes.c_uint]

	return lambda name: (fn(name) or b"").decode(errors="replace")

def gl_strings():
	"""{"vendor", "renderer", "version"} of the CURRENT context."""

	get = gl_get_string()

	return {"vendor": get(GL_VENDOR), "renderer": get(GL_RENDERER), "version": get(GL_VERSION)}

# The class install() replaces; HeadlessViewer and headless_viewer() build on it either way.
_RealViewer = osgViewer.Viewer

class HeadlessViewer(_RealViewer):
	"""An osgViewer.Viewer that renders into a pbuffer and ends its own frame loop: the last of
	`frames` frames is read back into a PNG, then `done` is set. Constructed by examples through
	osgViewer.Viewer once install() has run; the settings are class attributes set there."""

	backend = None
	frames = DEFAULT_FRAMES
	out = None
	size = (800, 600)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		width, height = self.size

		try:
			gc, self._backend = create_context(width, height, backend=type(self).backend)

		except RuntimeError as exc:
			raise SystemExit(f"headless: FAIL - {exc}") from None

		self.threadingModel = osgViewer.ViewerBase.SingleThreaded

		_setup_camera(self.camera, gc, width, height)

		self._frame = 0
		self._report = None

		print(
			f"headless: {self._backend} pbuffer {width}x{height}, {self.frames} frames -> {self.out}",
			flush=True
		)

	def frame(self, *args):
		self._frame += 1

		if self._frame != self.frames:
			return super().frame(*args)

		# The master camera's final draw callback runs after every nested/post-render camera, with
		# the pbuffer bound and current; whatever the example installed there still runs first.
		camera = self.camera
		previous = camera.finalDrawCallback

		def capture(render_info):
			if previous is not None:
				previous(render_info)

			self._report = self._capture()

		camera.finalDrawCallback = capture

		try:
			result = super().frame(*args)

		finally:
			camera.finalDrawCallback = previous

		self.done = True
		self._print_report()

		return result

	def setUpViewInWindow(self, *args, **kwargs):
		print("headless: ignoring setUpViewInWindow(); rendering into the pbuffer", flush=True)

	def _capture(self):
		width, height = self.size
		image = osg.Image()

		image.readPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE)

		pixels = memoryview(image).tobytes()

		return {
			**gl_strings(),
			"written": osgDB.writeImageFile(image, self.out),
			"blank": pixels[:3] * (len(pixels) // 3) == pixels,
		}

	def _print_report(self):
		report = self._report

		if report is None:
			print("headless: FAIL - the last frame never reached the final draw callback", flush=True)

			return

		print(f"headless: GL vendor:   {report['vendor']}")
		print(f"headless: GL renderer: {report['renderer']}")
		print(f"headless: GL version:  {report['version']}")

		if not report["written"]:
			print(f"headless: FAIL - could not write {self.out}", flush=True)

		elif report["blank"]:
			print(f"headless: WARNING - every pixel is identical in {self.out}", flush=True)

		else:
			print(f"headless: wrote {self.out}", flush=True)

def parse_argv(argv):
	"""Strip the headless options from `argv[1:]` (in place, before or after a "--") and return
	(enabled, backend, frames, out); PYOSG_HEADLESS/PYOSG_HEADLESS_FRAMES/PYOSG_HEADLESS_OUT supply
	defaults. --headless takes an optional backend (egl, native, or an alias) as its next word.
	"""

	env = os.environ.get("PYOSG_HEADLESS")
	enabled = env is not None and env != "0"
	backend = env if enabled and env not in ("1", "") else None
	frames = int(os.environ.get("PYOSG_HEADLESS_FRAMES", DEFAULT_FRAMES))
	out = os.environ.get("PYOSG_HEADLESS_OUT")
	known = (*BACKENDS, *BACKEND_ALIASES)
	rest = []
	i = 1

	while i < len(argv):
		arg = argv[i]
		name, eq, value = arg.partition("=")

		if name == "--headless":
			enabled = True

			if eq:
				backend = value

			elif i + 1 < len(argv) and argv[i + 1] in known:
				backend = argv[i + 1]
				i += 1

		elif name in ("--headless-frames", "--headless-out"):
			if not eq:
				if i + 1 >= len(argv):
					raise SystemExit(f"{name} needs a value")

				value = argv[i + 1]
				i += 1

			if name == "--headless-frames":
				frames = int(value)

			else:
				out = value

		else:
			rest.append(arg)

		i += 1

	argv[1:] = rest

	if frames < 1:
		raise SystemExit("--headless-frames must be at least 1")

	return enabled, resolve_backend(backend), frames, out

def installed():
	"""Whether install() has replaced osgViewer.Viewer in this process."""

	return osgViewer.Viewer is HeadlessViewer

def install(backend=None, frames=DEFAULT_FRAMES, out=None, size=(800, 600)):
	"""Replace osgViewer.Viewer with HeadlessViewer for the rest of this process. `out` defaults to
	"<script>-headless.png" in the current directory. Only the first call has any effect: a runner
	(OpenSceneGraph.examples, pyosg-cli) installs with its own size and example name before the
	example's own `import pyosg_example` would.
	"""

	if installed():
		return

	if out is None:
		out = f"{pathlib.Path(sys.argv[0]).stem or 'pyosg'}-headless.png"

	HeadlessViewer.backend = backend
	HeadlessViewer.frames = frames
	HeadlessViewer.out = str(pathlib.Path(out).resolve())
	HeadlessViewer.size = tuple(size)

	osgViewer.Viewer = HeadlessViewer
