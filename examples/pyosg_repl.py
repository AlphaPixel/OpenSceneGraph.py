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
import traceback

from aipython.integration import MainLoopController, drive

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

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

class CaptureRequest:
	"""Awaitable result of a capture queued for the next rendered frame."""

	def __init__(self, kind, filename, label=None):
		self.kind = kind
		self.filename = filename
		self.label = label
		self._future = asyncio.get_event_loop().create_future()

	def __await__(self):
		return self._future.__await__()

	@property
	def done(self):
		return self._future.done()

	def result(self):
		return self._future.result()


class CaptureQueueCallback(osg.Camera.DrawCallback):
	"""Persistent final-draw callback which drains one same-frame capture batch."""

	def __init__(self, controller):
		super().__init__()

		self.controller = controller

	def __call__(self, ri):
		# Move the queue before executing it. Captures queued by completion handlers
		# therefore belong to the following frame, never this partially-drained batch.
		batch = self.controller._capture_queue
		self.controller._capture_queue = []

		for request, texture, data_type in batch:
			try:
				if request.kind == "framebuffer":
					image = self._read_framebuffer()

				else:
					image = self._read_texture(ri, texture, data_type)

				if not osgDB.writeImageFile(image, request.filename):
					raise RuntimeError(f"failed to write capture {request.filename!r}")

				result = self.controller._capture_metadata(
					request, image, data_type,
				)

				request._future.set_result(result)

				print(f"Wrote {request.kind}: {request.filename}", flush=True)

			except Exception as exc:
				request._future.set_exception(exc)
				traceback.print_exc()

	def _read_framebuffer(self):
		vp = self.controller.viewer.camera.viewport
		if vp is None or not vp.valid:
			raise RuntimeError("capture camera has no valid viewport")

		image = osg.Image()
		image.readPixels(
			int(vp.x), int(vp.y), int(vp.width), int(vp.height),
			GL_RGB, GL_UNSIGNED_BYTE,
		)
		return image

	@staticmethod
	def _read_texture(ri, texture, data_type):
		texture.apply(ri.state)
		image = osg.Image()
		image.readImageFromCurrentTexture(ri.contextID, False, data_type)
		return image


class ViewerREPLController(MainLoopController):
	"""Continuous/manual frame driver and queued same-frame capture manager."""

	def __init__(self, viewer, frame_callback=None):
		self.viewer = viewer
		self.frame_callback = frame_callback

		super().__init__(self._osg_step, lambda: viewer.done, target_fps=None)

		# Keep the original diagnostic spelling available to existing examples.
		self.state["frames"] = 0
		self._capture_queue = []
		self._capture_callback = CaptureQueueCallback(self)
		self.viewer.camera.finalDrawCallback = self._capture_callback

	@property
	def steps(self):
		return self.state["steps"]

	def _osg_step(self):
		self.viewer.frame()

		if self.frame_callback is not None:
			self.frame_callback()

	def _step_once(self, catch_keyboard_interrupt=False):
		succeeded = super()._step_once(catch_keyboard_interrupt)

		self.state["frames"] = self.state["steps"]

		return succeeded

	def capture_framebuffer(self, filename="frame.png", label=None):
		request = CaptureRequest("framebuffer", filename, label)

		self._capture_queue.append((request, None, GL_UNSIGNED_BYTE))

		return request

	def capture_texture(
		self,
		texture,
		filename="texture.png",
		data_type=GL_UNSIGNED_BYTE,
		label=None
	):
		request = CaptureRequest("texture", filename, label)

		self._capture_queue.append((request, texture, data_type))

		return request

	def _capture_metadata(self, request, image, data_type):
		frame_stamp = self.viewer.frameStamp

		return {
			"kind": request.kind,
			"filename": request.filename,
			"label": request.label,
			"frame_number": None if frame_stamp is None else frame_stamp.frameNumber,
			"controller_step": self.steps + 1,
			"size": (image.s, image.t),
			"pixel_format": image.pixelFormat,
			"data_type": image.dataType if image.dataType else data_type,
		}

def repl(viewer, namespace=None, frame_callback=None):
	"""Drive *viewer* alongside terminal IPython or ipykernel.

	`namespace` is made explicitly available so live cameras, textures, uniforms,
	and other example locals remain reliable without caller-frame guessing.
	`frame_callback`, when supplied, runs after each viewer.frame() for applications
	that also need to drain queues or perform other per-frame Python work.

	The returned ViewerREPLController supports continuous rendering, deterministic
	pause/step control, and queued same-frame captures. Terminal IPython embeds a
	configured asyncio-aware prompt and blocks until that prompt exits. Under
	ipykernel, this registers an OSG event-loop integration and returns immediately
	so Jupyter/MCP requests retain structured results.
	"""

	if namespace is None:
		namespace = {}
	controller = ViewerREPLController(viewer, frame_callback)
	namespace["_osg_repl_controller"] = controller
	namespace["_osg_repl_state"] = controller.state
	return drive(controller=controller, namespace=namespace)

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
