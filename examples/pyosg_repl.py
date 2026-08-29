#!/usr/bin/env python3

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
#   await _osg_repl_controller.capture_framebuffer("frame.png")  # raw framebuffer PNG
#   _osg_repl_controls.input.locked = True  # temporarily block mouse/keyboard input
#   _osg_repl_controls.frames.target_fps = 30  # best-effort viewer pacing
#
# Type `exit` or Ctrl-D to leave the REPL and close the viewer.

import os
import sys

# setdefault(), not update() -- this module is imported by other examples
# (11-sketchfab.py, 99-repl.py, etc.) that configure their own OSG_WINDOW/
# OSG_THREADING before importing pyosg_repl for its repl() helper. update()
# here would silently clobber whatever the caller already set, since this
# import (inside the caller's `if args.repl:` branch) runs well before
# viewer.realize() actually reads the env var on the first frame(). Only
# fill these in for pyosg_repl.py's own standalone `__main__` use below,
# where nothing else has set them yet.
os.environ.setdefault("OSG_WINDOW", "50 50 800 600")
os.environ.setdefault("OSG_THREADING", "SingleThreaded")

import asyncio
import contextlib
import math
import subprocess
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

class AgentInputLock(osgGA.GUIEventHandler):
	"""Swallows user input (mouse/keyboard) while locked, so an agent driving a live viewer
	from the REPL can do deterministic work -- read/write uniforms, pose the camera, queue a
	capture -- without racing the user's own mouse/keyboard on the same window.

	The race this exists for: a user keypress handled by some other GUIEventHandler (e.g. a
	"retrigger the effect" key) landing on the same frame as the agent independently reading
	or writing state through the REPL -- two uncoordinated control sources on one live viewer,
	each individually correct, racing each other.

	FRAME/RESIZE/CLOSE_WINDOW/etc. always pass through even while locked, so continuous
	rendering and any handler that steps its own animation off FRAME keep working -- only
	events a human could have generated at the keyboard/mouse are swallowed.

	IMPORTANT: this is COOPERATIVE, not enforced -- OSG's own eventHandlers dispatch loop
	(Viewer::eventTraversal()) calls every handler for every event regardless of what
	earlier handlers returned; there is no "stop propagation" mechanism at that level.
	What actually gates things is `osgGA::Event.handled`: `GUIEventHandler::handle()`'s C++
	wrapper (the one OSG's loop actually calls) sets `ea.handled = True` whenever your
	Python `handle(ea, aa)` override returns `True`, and every WELL-BEHAVED handler after
	it is expected to check `ea.handled` at the top of its own `handle()` and bail out if
	it's already set -- exactly how OSG's own `StandardManipulator` (the base of
	`TrackballManipulator` and friends) already does it, which is why camera-manipulator
	input is blocked automatically with zero extra code. A handler that doesn't check
	`ea.handled` (an old example script's own custom handler, say) will keep firing
	regardless of this lock -- there's no way to force it from here, only to follow the
	same convention it should already be following. `insert()`-installed at
	`eventHandlers[0]` only guarantees this handler runs, and therefore sets `ea.handled`,
	BEFORE any other handler in the list sees the event -- it doesn't make later handlers
	respect that flag if they were never written to check it.

	`ViewerREPLController` installs one of these at `eventHandlers[0]` (first refusal, ahead
	of whatever handlers the caller already appended) and exposes it via `.lock_input()`/
	`.unlock_input()`/`.locked_input()` rather than needing to be constructed directly.
	"""

	_INPUT_EVENTS = frozenset((
		osgGA.GUIEventAdapter.PUSH,
		osgGA.GUIEventAdapter.RELEASE,
		osgGA.GUIEventAdapter.DOUBLECLICK,
		osgGA.GUIEventAdapter.DRAG,
		osgGA.GUIEventAdapter.MOVE,
		osgGA.GUIEventAdapter.SCROLL,
		osgGA.GUIEventAdapter.KEYDOWN,
		osgGA.GUIEventAdapter.KEYUP,
	))

	def __init__(self):
		super().__init__()

		self.locked = False

	def handle(self, ea, aa):
		return self.locked and ea.type in self._INPUT_EVENTS

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

	def __init__(self, kind, filename=None, label=None, include_image=False):
		self.kind = kind
		self.filename = filename
		self.label = label
		self.include_image = include_image
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

				if request.filename is not None:
					if not osgDB.writeImageFile(image, request.filename):
						raise RuntimeError(f"failed to write capture {request.filename!r}")

				result = self.controller._capture_metadata(
					request, image, data_type,
				)

				if request.include_image:
					result["image"] = image

				request._future.set_result(result)

				if request.filename is not None:
					print(f"Wrote {request.kind}: {request.filename}", flush=True)

			except Exception as exc:
				request._future.set_exception(exc)
				traceback.print_exc()

		video = self.controller._video_capture

		if video is not None:
			video.capture(self)

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


class VideoCapture:
	"""Stream timed framebuffer captures directly to an FFmpeg process."""

	def __init__(self, controller, filename, fps=24, duration=5, lock_input=False):
		if not isinstance(filename, str) or not filename:
			raise ValueError("video filename must be a non-empty str")

		if not isinstance(fps, (int, float)) or isinstance(fps, bool) or fps <= 0:
			raise ValueError("video fps must be positive")

		if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
			raise ValueError("video duration must be positive")

		if not isinstance(lock_input, bool):
			raise TypeError("video lock_input must be a bool")

		viewport = controller.viewer.camera.viewport

		if viewport is None or not viewport.valid:
			raise RuntimeError("video capture camera has no valid viewport")

		self.controller = controller
		self.filename = filename
		self.fps = float(fps)
		self.duration = float(duration)
		self.width = int(viewport.width)
		self.height = int(viewport.height)
		self.frame_count = int(round(self.fps * self.duration))
		self.captured_frames = 0
		self.started_at = time.monotonic()
		self.next_frame_at = self.started_at
		self._input_was_locked = controller.input_locked
		self._lock_input = lock_input
		self._finished = False
		self._error = None
		self.process = subprocess.Popen([
			"ffmpeg", "-y",
			"-f", "rawvideo",
			"-pixel_format", "rgb24",
			"-video_size", f"{self.width}x{self.height}",
			"-framerate", str(self.fps),
			"-i", "pipe:0",
			"-vf", "vflip",
			"-c:v", "libx264",
			"-pix_fmt", "yuv420p",
			filename,
		], stdin=subprocess.PIPE, bufsize=0)

		if lock_input:
			controller.lock_input("Recording video")

	@property
	def active(self):
		return not self._finished

	@property
	def status(self):
		return {
			"filename": self.filename,
			"fps": self.fps,
			"duration": self.duration,
			"size": (self.width, self.height),
			"captured_frames": self.captured_frames,
			"frame_count": self.frame_count,
			"active": self.active,
			"error": self._error,
		}

	def capture(self, callback):
		if self._finished or time.monotonic() < self.next_frame_at:
			return

		try:
			image = callback._read_framebuffer()
			frame = memoryview(image).tobytes()

			if len(frame) != self.width * self.height * 3:
				raise RuntimeError(
					f"expected {self.width * self.height * 3} RGB bytes, got {len(frame)}"
				)

			self.process.stdin.write(frame)
			self.captured_frames += 1
			self.next_frame_at += 1.0 / self.fps

			if self.captured_frames == self.frame_count:
				self.finish()

		except Exception as exc:
			self.fail(exc)
			traceback.print_exc()

	def finish(self):
		if self._finished:
			return

		self._finished = True
		self.process.stdin.close()

		if self.process.wait() != 0:
			self._error = "FFmpeg encoding failed"

		if self._lock_input and not self._input_was_locked:
			self.controller.unlock_input()

		if self._error is None:
			print(
				f"Saved {self.captured_frames} frames at {self.fps:g} fps to {self.filename}",
				flush=True,
			)

	def fail(self, exc):
		if self._finished:
			return

		self._error = str(exc)
		self._finished = True
		self.process.stdin.close()
		self.process.terminate()
		self.process.wait()

		if self._lock_input and not self._input_was_locked:
			self.controller.unlock_input()


class AgentInputControls:
	"""Model-facing ownership controls for human mouse/keyboard input."""

	def __init__(self, controller):
		self._controller = controller

	@property
	def locked(self):
		return self._controller.input_locked

	@locked.setter
	def locked(self, value):
		if not isinstance(value, bool):
			raise TypeError("input.locked must be a bool")

		if value:
			self._controller.lock_input()

		else:
			self._controller.unlock_input()

	def lock(self, title="LockedByAgent"):
		self._controller.lock_input(title)

	def unlock(self, title="Ready"):
		self._controller.unlock_input(title)

	def locked_input(self, locked_title="LockedByAgent", ready_title="Ready"):
		return self._controller.locked_input(locked_title, ready_title)


class AgentFrameControls:
	"""Model-facing viewer-frame pump controls."""

	def __init__(self, controller):
		self._controller = controller

	@property
	def target_fps(self):
		return self._controller.target_fps

	@target_fps.setter
	def target_fps(self, value):
		if value is not None and (
			not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0
		):
			raise ValueError("frames.target_fps must be positive or None")

		self._controller.target_fps = value

	@property
	def paused(self):
		return not self._controller.running

	@paused.setter
	def paused(self, value):
		if not isinstance(value, bool):
			raise TypeError("frames.paused must be a bool")

		if value:
			self._controller.pause()

		else:
			self._controller.resume()

	def step(self, count=1):
		return self._controller.step(count)


class AgentWindowControls:
	"""Model-facing best-effort controls for the viewer's native window."""

	def __init__(self, controller):
		self._controller = controller
		self._always_on_top = None
		self._title = None

	@property
	def always_on_top(self):
		return self._always_on_top

	@always_on_top.setter
	def always_on_top(self, value):
		if not isinstance(value, bool):
			raise TypeError("window.always_on_top must be a bool")

		try:
			import osgx

			osgx.platform.alwaysOnTop(self._controller.viewer, value)

		except Exception as exc:
			raise RuntimeError("always-on-top is unavailable for this viewer") from exc

		self._always_on_top = value

	@property
	def title(self):
		return self._title

	@title.setter
	def title(self, value):
		if not isinstance(value, str):
			raise TypeError("window.title must be a str")

		self._controller._set_window_title(value)
		self._title = value


class AgentCaptureControls:
	"""Model-facing aliases for the controller's GL-safe capture requests."""

	def __init__(self, controller):
		self._controller = controller

	def framebuffer(self, filename="frame.png", label=None):
		return self._controller.capture_framebuffer(filename, label)

	def framebuffer_image(self, label=None):
		return self._controller.capture_framebuffer_image(label)

	def texture(self, texture, filename="texture.png", data_type=GL_UNSIGNED_BYTE, label=None):
		return self._controller.capture_texture(texture, filename, data_type, label)

	def video(self, filename, fps=24, duration=5, lock_input=False):
		return self._controller.start_video_capture(filename, fps, duration, lock_input)

	@property
	def video_status(self):
		if self._controller._video_capture is None:
			return None

		return self._controller._video_capture.status


class AgentControls:
	"""Central, model-facing controls for a live :class:`ViewerREPLController`."""

	def __init__(self, controller):
		self._controller = controller
		self.input = AgentInputControls(controller)
		self.frames = AgentFrameControls(controller)
		self.window = AgentWindowControls(controller)
		self.capture = AgentCaptureControls(controller)

	@property
	def status(self):
		return {
			"input_locked": self.input.locked,
			"target_fps": self.frames.target_fps,
			"frames_paused": self.frames.paused,
			"always_on_top": self.window.always_on_top,
			"window_title": self.window.title,
			"frames": self._controller.state["frames"],
			"errors": self._controller.state["errors"],
			"video": self.capture.video_status,
		}


class ViewerREPLController(MainLoopController):
	"""Continuous/manual frame driver and queued same-frame capture manager."""

	def __init__(self, viewer, frame_callback=None):
		self.viewer = viewer
		self.frame_callback = frame_callback

		super().__init__(self._osg_step, lambda: viewer.done, target_fps=None)

		# Keep the original diagnostic spelling available to existing examples.
		self.state["frames"] = 0
		self._capture_queue = []
		self._video_capture = None
		self._capture_callback = CaptureQueueCallback(self)
		self.viewer.camera.finalDrawCallback = self._capture_callback

		# insert(0, ...), not append() -- first refusal ahead of whatever handlers the caller
		# already appended (e.g. pyosg-praxis.py's PraxisKeyHandler) before calling repl().
		self.input_lock = AgentInputLock()
		self.viewer.eventHandlers.insert(0, self.input_lock)

	@property
	def steps(self):
		return self.state["steps"]

	@property
	def input_locked(self):
		return self.input_lock.locked

	def lock_input(self, title="LockedByAgent"):
		"""Start swallowing user mouse/keyboard input -- call before deterministic work
		(uniform reads/writes, camera posing, queued captures) that shouldn't race the user
		touching the same live window. See AgentInputLock above for exactly what's swallowed.
		"""

		self.input_lock.locked = True
		self._set_window_title(title)

	def unlock_input(self, title="Ready"):
		"""Stop swallowing user input -- call once the deterministic work is done."""

		self.input_lock.locked = False
		self._set_window_title(title)

	@contextlib.contextmanager
	def locked_input(self, locked_title="LockedByAgent", ready_title="Ready"):
		"""`with controller.locked_input(): ...` -- lock, run the block, always unlock after,
		even on exception. A plain (non-async) context manager is enough here: locking itself
		is synchronous, and `with` around `await`-ing code inside is already valid Python, so
		REPL blocks needing both (e.g. `with controller.locked_input(): await
		controller.capture_framebuffer(...)`) work without an async variant.
		"""

		self.lock_input(locked_title)

		try:
			yield

		finally:
			self.unlock_input(ready_title)

	def _set_window_title(self, title):
		# osgx is a sibling project (not every environment running this module has it built),
		# and window retitling is cosmetic status, not core lock behavior -- so this is soft,
		# best-effort: a missing osgx, a non-X11 backend, or any other failure here must never
		# prevent lock_input()/unlock_input() from doing the part that actually matters.
		try:
			import osgx

			osgx.platform.setWindowTitle(self.viewer, title)

		except Exception:
			pass

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

	def capture_framebuffer_image(self, label=None):
		"""Capture the next framebuffer in RAM; the result contains an ``image`` key."""
		request = CaptureRequest("framebuffer", label=label, include_image=True)

		self._capture_queue.append((request, None, GL_UNSIGNED_BYTE))

		return request

	def start_video_capture(self, filename, fps=24, duration=5, lock_input=False):
		if self._video_capture is not None and self._video_capture.active:
			raise RuntimeError("a video capture is already running")

		self._video_capture = VideoCapture(self, filename, fps, duration, lock_input)

		return self._video_capture

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
	namespace["_osg_repl_controls"] = AgentControls(controller)

	return drive(controller=controller, namespace=namespace)

# --------------------------------------------------------------------------- #
# Viewer setup (deliberately small; the REPL integration is the actual example)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
	viewer = osgViewer.Viewer()

	if len(sys.argv) > 1:
		viewer.sceneData = osgDB.readNodeFile(sys.argv[1])

	viewer.cameraManipulator = osgGA.TrackballManipulator()
	# viewer.cameraManipulator = REPLCameraManipulator()
	# viewer.cameraManipulator = CinematicOrbitManipulator(viewer.camera)
	viewer.eventHandlers.append(DebugHandler())

	# globals() is intentional for this proof: it makes `viewer`, `scene`, `sphere`,
	# osg/osgGA/osgViewer, asyncio, and the helper itself available at the prompt.
	repl(viewer, globals())
