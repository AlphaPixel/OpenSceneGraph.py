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
import sys

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
})

import asyncio
import math
import time
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

class CinematicOrbitManipulator(osgGA.CameraManipulator):
	"""Algorithmically-driven "camera drone" orbit around the loaded model.

	Unlike REPLCameraManipulator above (a passive matrix box you pose by hand),
	this one poses itself: getMatrix()/getInverseMatrix() are computed on every
	call from wall-clock time, so there's nothing to step or drive from the REPL
	loop -- just assign it and watch.

	Two out-of-phase sinusoids drive azimuth (constant spin) and elevation (bob
	above/below a base pitch); a third drives a zoom "breathe" whose far point is
	clamped, every frame, to whatever distance keeps the model's bounding sphere
	at *least* `min_screen_fraction` of the smaller screen dimension -- so it can
	never drift out to a speck regardless of model size or window shape. The
	look-at point is always the model's own bounding-sphere center: it never
	drifts, so the model stays framed dead-center throughout. Assumes a Z-up
	scene, matching OSG's default and the up-axis correction OSG's own loaders
	(glTF, etc.) already apply.

	Needs the live camera (not just its projection matrix at construction time)
	because the projection changes on window resize and the framing constraint
	has to track that.

	Overrides setNode()/getNode() to store the scene node into self._node, and
	home() to (re)compute the bounding sphere from it -- both of these used to
	be broken in the pybind11 bindings (CameraManipulator's trampoline didn't
	intercept setNode()/getNode() at all, so a Python override of either was
	silently never called; and home()'s two-argument overload crashed trying
	to copy a non-copyable GUIEventAdapter when forwarding to a Python
	override). Both are fixed now, so this no longer needs the
	node-as-constructor-argument workaround an earlier version of this class
	used. Note the trampoline fix only makes overriding setNode()/getNode()
	*possible* -- it doesn't give a subclass free storage for free; a
	subclass that doesn't override them still gets the C++ base class's
	no-op defaults, same as any plain C++ CameraManipulator subclass would.

	Try it live from the aipython REPL:

		viewer.cameraManipulator = CinematicOrbitManipulator(viewer.camera)
	"""

	def __init__(
		self,
		camera,
		azimuth_speed=0.3,
		elevation_speed=0.45,
		elevation_center=0.3,
		elevation_amplitude=0.6,
		distance_speed=0.35,
		distance_min_fraction=0.6,
		min_screen_fraction=0.5,
	):
		super().__init__()

		self.camera = camera
		self.azimuth_speed = azimuth_speed
		self.elevation_speed = elevation_speed
		self.elevation_center = elevation_center
		self.elevation_amplitude = elevation_amplitude
		self.distance_speed = distance_speed
		self.distance_min_fraction = distance_min_fraction
		self.min_screen_fraction = min_screen_fraction

		self._node = None
		self._start = time.monotonic()
		self._center = osg.Vec3d(0, 0, 0)
		self._radius = 1.0

	def setNode(self, node):
		self._node = node

	def getNode(self):
		return self._node

	def home(self, *args):
		# Called by View.setCameraManipulator(..., resetPosition=True) -- i.e. as
		# soon as `viewer.cameraManipulator = self` runs -- with self._node
		# already populated (setNode() always runs first), so the model's real
		# size/position is available here rather than needing to be guessed at
		# construction time.
		bound = self._node.bound if self._node is not None else None

		if bound is not None and bound.valid():
			self._center = osg.Vec3d(bound.center)
			self._radius = max(bound.radius, 1e-3)
		else:
			self._center = osg.Vec3d(0, 0, 0)
			self._radius = 1.0

		self._start = time.monotonic()

	def _max_distance(self):
		# The bounding sphere's angular radius as seen from distance d is
		# asin(radius / d); solving for the distance at which its angular
		# *diameter* equals min_screen_fraction of a given axis' FOV gives the
		# farthest the camera can sit and still satisfy that axis. The axis
		# with the larger FOV is the binding (smaller-max-distance) one, so
		# using max(fovy, fovx) here guarantees the floor holds on both axes.
		fovy_deg, aspect, _near, _far = self.camera.projectionMatrix.getPerspective()

		fovy_rad = math.radians(fovy_deg)
		fovx_rad = 2.0 * math.atan(aspect * math.tan(fovy_rad * 0.5))
		limiting_fov = max(fovy_rad, fovx_rad)

		return self._radius / math.sin(0.5 * self.min_screen_fraction * limiting_fov)

	def _pose(self):
		t = time.monotonic() - self._start

		azimuth = t * self.azimuth_speed
		elevation = self.elevation_center + self.elevation_amplitude * math.sin(
			t * self.elevation_speed
		)

		max_distance = self._max_distance()
		zoom_t = 0.5 + 0.5 * math.sin(t * self.distance_speed)
		distance = max_distance * (1.0 - (1.0 - self.distance_min_fraction) * zoom_t)

		cos_el = math.cos(elevation)

		offset = osg.Vec3d(
			math.cos(azimuth) * cos_el,
			math.sin(azimuth) * cos_el,
			math.sin(elevation),
		) * distance

		eye = self._center + offset

		return eye, self._center, osg.Vec3d(0, 0, 1)

	def getMatrix(self):
		eye, center, up = self._pose()

		return osg.Matrix.inverse(osg.Matrix.lookAt(eye, center, up))

	def setByMatrix(self, m):
		pass

	def getInverseMatrix(self):
		eye, center, up = self._pose()

		return osg.Matrix.lookAt(eye, center, up)

	def setByInverseMatrix(self, m):
		pass

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

	if len(sys.argv) <= 1:
		scene = osg.Geode()
		sphere = osg.ShapeDrawable(osg.Sphere(osg.Vec3(), 1.0))

		scene.drawables.append(sphere)

	else:
		scene = osgDB.readNodeFile(sys.argv[1])

	viewer.sceneData = scene
	viewer.cameraManipulator = osgGA.TrackballManipulator()
	# viewer.cameraManipulator = REPLCameraManipulator()
	# viewer.cameraManipulator = CinematicOrbitManipulator(viewer.camera)
	viewer.eventHandlers.append(DebugHandler())

	# globals() is intentional for this proof: it makes `viewer`, `scene`, `sphere`,
	# osg/osgGA/osgViewer, asyncio, and the helper itself available at the prompt.
	repl(viewer, globals())
