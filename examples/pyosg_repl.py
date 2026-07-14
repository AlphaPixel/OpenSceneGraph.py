#!/usr/bin/env python3
#vimrun! python3 ../examples/pyosg-repl.py

# Proof-of-concept for an eventual OpenSceneGraph.repl(viewer, namespace) helper.
#
# Unlike the older version of this example, this does NOT need to be launched by
# `ipython3 -i` and does not register a custom OSG prompt input hook. It embeds a
# directly-configured IPython shell and schedules viewer.frame() on IPython's own
# asyncio event loop. The OSG window therefore keeps rendering and responding while
# IPython is idle at its prompt, and top-level `await` remains available.
#
# The slightly non-obvious setup was proven first in pyosg-lighting/11-sketchfab.py:
#
#   * `IPython.embed(using="asyncio")` is insufficient: it selects the runner for
#     top-level await, but does not make the prompt itself pump asyncio while idle.
#   * shell.enable_gui("asyncio") enables that separate prompt input hook.
#   * the IPython.embed() convenience function clears any preconfigured singleton,
#     so we must construct InteractiveShellEmbed and invoke it directly.
#
# Try these at the prompt while continuing to manipulate the viewer window:
#
#   viewer.camera.clearColor = osg.Vec4(0.15, 0.05, 0.2, 1)
#   scene.nodeMask = 0; await asyncio.sleep(1); scene.nodeMask = 0xffffffff
#   n = _osg_repl_state["frames"]
#   await asyncio.sleep(1); _osg_repl_state["frames"] - n
#
# Type `exit` or Ctrl-D to leave the REPL and close the viewer.

import os

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
})

import asyncio
import signal
import traceback

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

_kernel_repl_driver = None

class DebugHandler(osgGA.GUIEventHandler):
	debug = False

	def handle(self, ea, aa):
		if self.debug:
			if not ea.type == osgGA.GUIEventAdapter.FRAME:
				print(f"DebugHandler.handle(self={self}, ea={ea}, aa={aa}) type={ea.type}")

class REPLCameraManipulator(osgGA.CameraManipulator):
	def __init__(self):
		super().__init__()

		self._matrix = osg.Matrixd()

	def getMatrix(self):
		return self._matrix

	def setByMatrix(self, m):
		self._matrix = m

	def getInverseMatrix(self):
		return osg.Matrix.inverse(self._matrix)

	def setByInverseMatrix(self, m):
		self._matrix = osg.Matrix.inverse(m)

# --------------------------------------------------------------------------- #
# Gathered reusable implementation
# --------------------------------------------------------------------------- #

class WriteFramebufferCallback(osg.Camera.DrawCallback):
	"""One-shot final-framebuffer capture, modeled on OSG ScreenCaptureHandler.

	The callback must run while the graphics context is current. Installing it as
	the viewer camera's finalDrawCallback places readback after nested PRE_RENDER,
	main, and POST_RENDER stages: the completed image actually shown in the window.
	"""

	def __init__(self, camera, filename):
		super().__init__()

		self.camera = camera
		self.filename = filename
		self.done = False

	def __call__(self, ri):
		if self.done:
			return

		vp = self.camera.viewport

		if vp is None or not vp.valid:
			raise RuntimeError("capture camera has no valid viewport")

		image = osg.Image()

		image.readPixels(
			int(vp.x), int(vp.y),
			int(vp.width), int(vp.height),
			GL_RGB,
			GL_UNSIGNED_BYTE
		)

		if not osgDB.writeImageFile(image, self.filename):
			raise RuntimeError(f"failed to write framebuffer capture {self.filename!r}")

		self.done = True

		print(f"Wrote final framebuffer: {self.filename}", flush=True)

class WriteTextureCallback(osg.Camera.DrawCallback):
	"""One-shot GPU texture readback for an RTT/MRT attachment."""

	def __init__(self, camera, texture, filename, data_type=GL_UNSIGNED_BYTE):
		super().__init__()

		self.camera = camera
		self.texture = texture
		self.filename = filename
		self.data_type = data_type
		self.done = False

	def __call__(self, ri):
		if self.done:
			return

		# apply() binds/realizes this texture in the callback's current context;
		# readImageFromCurrentTexture() then copies its actual GPU contents.
		self.texture.apply(ri.state)

		image = osg.Image()

		image.readImageFromCurrentTexture(
			ri.contextID, False, self.data_type,
		)

		if not osgDB.writeImageFile(image, self.filename):
			raise RuntimeError(f"failed to write texture capture {self.filename!r}")

		self.done = True

		print(f"Wrote texture: {self.filename}", flush=True)

def capture_framebuffer(viewer, filename="frame.png"):
	"""Capture the completed window framebuffer on the next rendered frame."""

	callback = WriteFramebufferCallback(viewer.camera, filename)

	viewer.camera.finalDrawCallback = callback

	return callback

def capture_texture(viewer, texture, filename="texture.png", data_type=GL_UNSIGNED_BYTE):
	"""Dump a GPU texture on the next frame, after all viewer render stages."""

	callback = WriteTextureCallback(viewer.camera, texture, filename, data_type)

	viewer.camera.finalDrawCallback = callback

	return callback

def _new_repl_state(backend):
	return {
		"backend": backend,
		"frames": 0,
		"errors": 0,
		"last_exception": None,
	}

def _frame_once(viewer, frame_callback, repl_state, catch_keyboard_interrupt=False):
	try:
		viewer.frame()

		repl_state["frames"] += 1

		if frame_callback is not None:
			frame_callback()

		return True

	except BaseException as exc:
		# asyncio cancellation and process-exit requests must retain their normal
		# semantics. KeyboardInterrupt is recoverable only in the terminal backend,
		# where Ctrl-C must not destroy the viewer process.
		if not isinstance(exc, Exception) and not (
			catch_keyboard_interrupt and isinstance(exc, KeyboardInterrupt)
		):
			raise

		repl_state["errors"] += 1
		failure = (type(exc), str(exc))

		if failure != repl_state["last_exception"]:
			repl_state["last_exception"] = failure

			traceback.print_exc()

		return False

def _kernel_repl(viewer, namespace, frame_callback):
	"""Install an ipykernel GUI loop and return control to the kernel."""

	import time

	import ipykernel.eventloops as eventloops
	from IPython import get_ipython

	global _kernel_repl_driver

	repl_state = _new_repl_state("kernel")
	namespace["_osg_repl_state"] = repl_state

	_kernel_repl_driver = {
		"viewer": viewer,
		"frame_callback": frame_callback,
		"state": repl_state,
	}

	@eventloops.register_integration("osg")
	def osg_kernel_loop(kernel):
		while True:
			driver = _kernel_repl_driver

			if driver is not None and not driver["viewer"].done:
				succeeded = _frame_once(
					driver["viewer"],
					driver["frame_callback"],
					driver["state"],
				)

				if not succeeded:
					time.sleep(0.05)

			if kernel.shell_stream.flush(limit=1):
				return

			time.sleep(min(kernel._poll_interval, 1.0 / 60.0))

	shell = get_ipython()

	# An explicit namespace remains authoritative in kernel mode too. This makes
	# repl(viewer, locals()) useful from functions and from C++ wrapper frames,
	# instead of relying on `%run -i` or caller-frame introspection.
	shell.user_ns.update(namespace)
	shell.enable_gui("osg")

	print(
		"OSG kernel REPL ready; the viewer continues rendering between requests.",
		flush=True,
	)

	return repl_state

def _terminal_repl(viewer, namespace, frame_callback):
	"""Run *viewer* continuously while an embedded terminal prompt is idle."""

	from IPython.core.async_helpers import get_asyncio_loop
	from IPython.terminal.embed import InteractiveShellEmbed
	from IPython.terminal.ipapp import load_default_config

	# InteractiveShellEmbed imports namespace entries into its user namespace; an
	# immutable integer would therefore remain the initially imported value when
	# this function later replaced namespace["..."] with a new integer. Keep one
	# shared mutable object so diagnostics observed at the prompt stay live.
	repl_state = _new_repl_state("terminal")

	namespace["_osg_repl_state"] = repl_state

	loop = get_asyncio_loop()

	asyncio.set_event_loop(loop)

	async def render_loop():
		while not viewer.done:
			succeeded = _frame_once(
				viewer, frame_callback, repl_state,
				catch_keyboard_interrupt=True,
			)

			if not succeeded:
				# A Python draw/update/event callback can propagate through
				# viewer.frame(). Without this boundary, asyncio permanently marks
				# render_loop failed: IPython remains alive but the window freezes.
				# Keep the task recoverable so the offending callback can be fixed
				# live. Report a repeating failure only once to avoid flooding the
				# terminal at render-loop speed.
				await asyncio.sleep(0.05)

				continue

			# Cooperatively yield to IPython and any other asyncio tasks. Display
			# pacing is normally supplied by the graphics context/vsync.
			await asyncio.sleep(0)

	render_task = loop.create_task(render_loop())

	# Keep Ctrl-C recoverable. SIG_DFL terminates the entire process, which makes
	# it impossible to interrupt a stuck live query without also losing the
	# viewer. Preserve the embedding application's handler and restore it when the
	# REPL exits rather than permanently changing process-wide signal behavior.
	previous_sigint_handler = signal.getsignal(signal.SIGINT)

	signal.signal(signal.SIGINT, signal.default_int_handler)

	config = load_default_config()

	config.InteractiveShellEmbed = config.TerminalInteractiveShell
	config.TerminalInteractiveShell.loop_runner = "asyncio"
	config.TerminalInteractiveShell.autoawait = True

	shell = InteractiveShellEmbed.instance(config=config)

	shell.enable_gui("asyncio")

	try:
		shell(
			header="OSG REPL ready; the viewer continues rendering while this prompt is idle.",
			local_ns=namespace,
		)

	finally:
		InteractiveShellEmbed.clear_instance()
		render_task.cancel()

		try:
			loop.run_until_complete(asyncio.gather(render_task, return_exceptions=True))

		except asyncio.CancelledError:
			pass

		signal.signal(signal.SIGINT, previous_sigint_handler)

	return repl_state

def repl(viewer, namespace=None, frame_callback=None):
	"""Run *viewer* continuously alongside terminal IPython or ipykernel.

	`namespace` is made explicitly available so live cameras, textures, uniforms,
	and other example locals remain reliable without caller-frame guessing.
	`frame_callback`, when supplied, runs after each viewer.frame() for applications
	that also need to drain queues or perform other per-frame Python work.

	Terminal IPython embeds a configured asyncio-aware prompt and blocks until that
	prompt exits. Under ipykernel, this registers an OSG event-loop integration and
	returns immediately so Jupyter/MCP requests retain structured results.
	"""

	from IPython import get_ipython

	if namespace is None:
		namespace = {}

	shell = get_ipython()

	if shell is not None and getattr(shell, "kernel", None) is not None:
		return _kernel_repl(viewer, namespace, frame_callback)

	return _terminal_repl(viewer, namespace, frame_callback)

# --------------------------------------------------------------------------- #
# Viewer setup (deliberately small; the REPL integration is the actual example)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
	viewer = osgViewer.Viewer()

	scene = osg.Geode()
	sphere = osg.ShapeDrawable(osg.Sphere(osg.Vec3(), 1.0))

	scene.drawables.append(sphere)

	viewer.sceneData = scene
	viewer.cameraManipulator = osgGA.TrackballManipulator()
	# viewer.cameraManipulator = REPLCameraManipulator()
	viewer.addEventHandler(DebugHandler())

	# globals() is intentional for this proof: it makes `viewer`, `scene`, `sphere`,
	# osg/osgGA/osgViewer, asyncio, and the helper itself available at the prompt.
	repl(viewer, globals())
