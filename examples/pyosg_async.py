#!/usr/bin/env python3

# Small, reusable pieces of the "async OSG.py" idiom -- not a framework, just the two things every
# example kept hand-rolling: (1) running viewer.frame() as an ordinary asyncio task instead of a
# bespoke synchronous pump loop, so it composes with `await` like any other coroutine, and (2)
# draining a poll()-shaped progress object (see osgx.gltf.AsyncProgress) from the coroutine that's
# already awaiting the background work, instead of routing progress through a queue and a
# call_soon_threadsafe bridge. See aipython/25-async-osgpy.md for why the poll-based half of this
# exists (a real measured 2x async/sync slowdown from the push-based alternative, caused by the
# background thread contending for the GIL with a render loop that -- under OSG_THREADING=
# SingleThreaded -- almost never voluntarily releases it).
#
# This module is intentionally NOT part of the OpenSceneGraph package yet -- it's a migration
# candidate for python/OpenSceneGraph/, alongside pyosg_repl.py and pyosg_visitor.py, once that
# move happens deliberately for all three together.

import asyncio

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

async def run(viewer, *coros, fps=60, max_frames=None):
	"""Runs viewer.frame() as an ordinary asyncio task alongside `coros`, so application code
	never hand-writes its own `while not viewer.done: viewer.frame(); loop.run_until_complete(...)`
	pump -- rendering is just another coroutine competing for the same event loop, the same way a
	browser's requestAnimationFrame callback or Node's setInterval share their loop with everything
	else.

	The window closing (`viewer.done` becoming true, i.e. the user hit Escape or closed it) always
	ends the session immediately, cancelling any `coros` still running -- same as it would in a
	hand-written `while not viewer.done: ...` loop, where nothing after the loop runs once it
	exits. Conversely, a `coros` task finishing early does NOT end the session on its own -- a
	one-shot startup task (e.g. a single load-and-attach coroutine) completing must not close the
	window out from under whoever's still looking at it. These two exit conditions are genuinely
	asymmetric, not "wait for everything": treat `render()`'s own completion as authoritative, and
	`coros` completing as informational only, unless one of them raises (which ends the session
	either way, exception propagated here).

	`fps` bounds how often frame() is called -- await asyncio.sleep(1 / fps) between calls, a real
	sleep, so this task genuinely yields control (including, if it's a busy moment, the GIL) rather
	than spinning. There is no reason to poll faster than the display can show anyway.

	`max_frames`, if given, sets `viewer.done = True` after exactly that many frame() calls --
	matching how the window actually closes (Escape / OS close button), NOT `viewer.close()`
	(see the comment at the actual call site for why that's deliberately avoided) -- for
	deterministic, scriptable runs (apitrace captures, crash repros) that don't depend on a
	human pressing Escape at some approximate moment.
	"""

	frame_interval = 1.0 / fps

	async def render():
		count = 0

		while not viewer.done:
			viewer.frame()

			count += 1

			if max_frames is not None and count >= max_frames:
				# NOT viewer.close() -- that calls GraphicsContext::close(), which (when this
				# context isn't shared) unconditionally runs osg::deleteAllGLObjects(contextID):
				# a blanket "delete every GL object ever registered for this context" sweep,
				# regardless of whether the owning C++ objects are still alive. A still-alive
				# orphaned Camera (kept alive by another task, like Progress.watch()) has its
				# real GL-side Program/buffers deleted out from under it while it still believes
				# it owns them -- confirmed 2026-08-23 as the likely mechanism behind a real
				# "corrupted double-linked list" abort. `done = True` matches how a window
				# actually closes (Escape / OS close button) -- no explicit teardown call here.
				viewer.done = True

				break

			await asyncio.sleep(frame_interval)

	render_task = asyncio.ensure_future(render())
	other_tasks = [asyncio.ensure_future(c) for c in coros]
	pending = {render_task, *other_tasks}

	try:
		# Wait incrementally rather than for one fixed condition -- a `coros` task finishing (in
		# `done`) is only checked for an exception and then dropped from `pending`; the loop keeps
		# going. Only `render_task` leaving `pending` (the window actually closed) ends it, and
		# only that specific check breaks the loop -- an exception from ANY task still ends things
		# immediately via the raise below, on either task's completion.
		while True:
			done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

			for task in done:
				if task.cancelled():
					continue

				exc = task.exception()

				if exc is not None:
					raise exc

			if render_task not in pending:
				break

	finally:
		for task in (render_task, *other_tasks):
			if not task.done():
				task.cancel()

		for task in (render_task, *other_tasks):
			try:
				await task

			except (asyncio.CancelledError, Exception):
				pass

async def run_with_progress(
	blocking_fn,
	*args,
	progress=None,
	on_progress=None,
	stop=None,
	poll_interval=1.0 / 60.0
):
	"""Runs `blocking_fn(*args)` via asyncio.to_thread while polling `progress` (any object with a
	no-arg poll() method returning None-or-an-update, e.g. osgx.gltf.AsyncProgress) from the
	awaiting coroutine's own loop and forwarding each update to `on_progress`. Returns
	blocking_fn's return value.

	This is the "pull" half of the pattern: `blocking_fn` must never call back into Python itself
	(no queue, no loop, no call_soon_threadsafe) -- it only needs to write into `progress` via
	plain atomics, and this coroutine (which already owns the GIL as a matter of course, same as
	any Python code) does the work of noticing and reacting to changes. The one exception is the
	final return value, which really does cross back into Python exactly once, at completion --
	that's asyncio.to_thread's own Future machinery, not something this function adds, and it was
	never the source of the GIL contention this pattern exists to avoid (see the module docstring).

	`poll_interval` MUST be a real, positive sleep, not 0 -- `poll()` itself being cheap (a few
	atomic loads, no GIL crossing) is only free to call often when it's piggybacking on a loop
	that already ticks for other reasons, like `run()`'s render loop above. This loop exists
	*purely* to poll, so `await asyncio.sleep(0)` here would be a genuine unthrottled busy-loop --
	CPython's zero-delay sleep is a bare cooperative yield, not a real wait, so this coroutine
	would be rescheduled continuously for the entire duration of `blocking_fn`, burning ~100% of
	one core on pure polling overhead. That's real OS-level CPU contention with the background
	thread actually doing the work -- measured as a genuine slowdown (worse than the GIL
	contention this pattern was built to remove), not a theoretical concern. Default matches a
	typical 60fps render cadence; there's no reason to poll faster than progress can be displayed
	anyway.

	`stop` (a StopEvent), if given, is set() when this coroutine itself is cancelled, so
	`blocking_fn` gets a chance to notice at its own cooperative checkpoints and return early --
	cancellation here can't preempt a single opaque blocking call already in flight, same
	limitation as `asyncio.CancelledError` has against any synchronous code.
	"""

	task = asyncio.ensure_future(asyncio.to_thread(blocking_fn, *args))

	try:
		while not task.done():
			if progress is not None and on_progress is not None:
				update = progress.poll()

				if update is not None:
					on_progress(update)

			await asyncio.sleep(poll_interval)

		return await task

	except asyncio.CancelledError:
		if stop is not None:
			stop.stop()

		try:
			await asyncio.shield(task)

		except asyncio.CancelledError:
			pass

		raise

class Progress(osg.Camera):
	"""Base class for a screen-space progress indicator, rendered by a dedicated POST_RENDER
	overlay Camera -- guaranteed to draw after (on top of) the main scene regardless of its
	content, same shape as pyosg-fire.py's build_flash_camera(): identity view/projection
	(children emit clip-space coordinates directly, ignoring gl_ModelViewProjectionMatrix
	entirely), ABSOLUTE_RF, and clearMask=0 since this is an overlay -- clearing here would wipe
	out everything the main camera already rendered this frame.

	This is deliberately a real Python subclass of osg.Camera, not a plain osg.Camera returned
	from a factory function with attributes bolted on afterward -- pybind11 types aren't
	dynamic_attr (see feedback_avoid_dynamic_attr_use_proxy), so a genuine subclass is the only
	way to get both `isinstance(x, osg.Camera)` (for attaching into a scene graph the normal way)
	and Python-level state (`fraction`, `update()`) on the same object.

	Subclasses provide the actual geometry/shader (a bar today; a spinner or gauge later) and
	call `self._attach(geometry, program)` once, after `super().__init__()`, to wire them in.
	The `uProgress`/`uFgColor`/`uBgColor` uniform contract is common to any progress
	visualization and is created here, not per-subclass.
	"""

	def __init__(
		self,
		width,
		height,
		fg_color=(0.2, 0.4, 0.2, 1.0),
		bg_color=(0.15, 0.15, 0.15, 1.0),
		**kwargs
	):
		super().__init__(**kwargs)

		self.renderOrder = osg.Camera.POST_RENDER
		self.clearMask = 0
		self.viewport = osg.Viewport(0, 0, width, height)
		self.projectionMatrix = osg.Matrix.identity()
		self.viewMatrix = osg.Matrix.identity()
		self.referenceFrame = osg.Transform.ABSOLUTE_RF
		self.allowEventFocus = False

		ss = self.stateSet

		ss.modes[GL_DEPTH_TEST] = osg.StateAttribute.OFF
		ss.modes[GL_BLEND] = osg.StateAttribute.ON
		ss.attributes[osg.StateAttribute.BLENDFUNC] = (
			osg.BlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA), osg.StateAttribute.ON
		)
		ss.uniforms["uProgress"] = 0.0
		ss.uniforms["uFgColor"] = osg.Vec4(*fg_color)
		ss.uniforms["uBgColor"] = osg.Vec4(*bg_color)

		self._fraction = 0.0

	def _attach(self, geometry, program):
		# self.stateSet.attributes.append(program)
		# self.children.append(geometry)
		geometry.stateSet.attributes.append(program)
		self.children.append(geometry)

	def update(self, fraction):
		"""Set the current progress, clamped to [0, 1]."""

		self._fraction = max(0.0, min(1.0, fraction))
		self.stateSet.uniforms["uProgress"] = self._fraction

	@property
	def fraction(self):
		return self._fraction

	@staticmethod
	def _default_to_fraction(update):
		"""Interprets an osgx.gltf.AsyncProgress-shaped (stage, current, total, section, overall)
		update as a 0..1 fraction -- the only progress-source shape this codebase has today. Uses
		`overall` (a monotonic, whole-load estimate computed on the C++ side) rather than
		re-deriving a fraction from current/total, which resets at every section boundary within
		Parsing and would visibly jump backward. Pass a different `to_fraction` to watch() for any
		other shape (a plain float already in [0, 1], a different tuple layout, whatever); this
		default is a convenience, not a contract.
		"""

		return update[-1]

	async def watch(self, progress, poll_interval=1.0 / 60.0, to_fraction=None):
		"""Drives this indicator's fraction from any `.poll()`-shaped progress source (e.g.
		osgx.gltf.AsyncProgress), independently of however the underlying operation is actually
		run. Deliberately NOT wired through run_with_progress()'s on_progress callback -- add
		this as its own coroutine to pyosg_async.run()'s task list instead:

		    asyncio.run(pyosg_async.run(viewer, load(...), bar.watch(progress)))

		so the load and the display are fully decoupled: `load()` doesn't need to know a bar
		exists (it just runs `progress` through whatever loads it), and this doesn't need to
		know how `load()` runs. Anyone wanting a different display style writes their own
		coroutine of this same shape instead of subclassing anything.

		Runs forever, polling at `poll_interval`, until cancelled -- normally when the whole
		session ends (see pyosg_async.run()'s docstring: only the window closing ends things,
		so this harmlessly keeps polling a progress object that stopped changing once the load
		it's watching finishes, until then).
		"""

		to_fraction = to_fraction or self._default_to_fraction

		while True:
			update = progress.poll()

			if update is not None:
				self.update(to_fraction(update))

			await asyncio.sleep(poll_interval)

	@property
	def fg_color(self):
		return self.stateSet.uniforms["uFgColor"].value

	@fg_color.setter
	def fg_color(self, value):
		self.stateSet.uniforms["uFgColor"] = osg.Vec4(*value)

	@property
	def bg_color(self):
		return self.stateSet.uniforms["uBgColor"].value

	@bg_color.setter
	def bg_color(self, value):
		self.stateSet.uniforms["uBgColor"] = osg.Vec4(*value)

BAR_VERTEX_SHADER = """
	#version 430 core

	uniform float uHeight = 0.05;

	out float vU;

	void main() {
		// Same gl_VertexID-indexed quad-corner trick as pyosg-instanced.py/pyosg-fire.py, but
		// pinned to the bottom of NDC space instead of centered -- a horizontal strip from
		// y=-1 up to y=-1+uHeight, spanning the full width.
		vec2 base[4] = vec2[4](
			vec2(-1.0, -1.0),
			vec2( 1.0, -1.0),
			vec2( 1.0, -1.0 + uHeight),
			vec2(-1.0, -1.0 + uHeight)
		);

		vec2 v = base[gl_VertexID % 4];

		vU = (v.x + 1.0) * 0.5;

		gl_Position = vec4(v, 0.0, 1.0);
	}
"""

BAR_FRAGMENT_SHADER = """
	#version 430 core

	in float vU;

	uniform float uProgress = 0.0;
	uniform vec4 uFgColor = vec4(0.2, 0.8, 0.3, 1.0);
	uniform vec4 uBgColor = vec4(0.15, 0.15, 0.15, 1.0);

	out vec4 fragColor;

	void main() {
		fragColor = vU <= uProgress ? uFgColor : uBgColor;
	}
"""

class ProgressBar(Progress):
	"""A left-to-right horizontal progress bar pinned to the bottom of the screen.

	`bar_height` is a literal pixel thickness (default 2.5x PixelText's native glyph height --
	see NATIVE_TEXT_HEIGHT below), not a window-relative divisor -- unlike the bar's own clip-
	space quad shader, a percentage label needs a REAL pixel size to look right regardless of
	window size (an NDC-relative font would grow/shrink with the window along with the bar), so
	this class converts it to the NDC fraction (`uHeight = 2 * bar_height / height`) itself
	rather than pushing that math onto every caller.
	"""

	# PixelText's font is a fixed 5x7 grid (see osgx::PixelText::GLYPH_ROWS) -- "native" height
	# here means cellSize=GLYPH_ROWS, i.e. one glyph pixel per cellSize unit, the smallest size
	# at which the font is still drawn 1:1 rather than up/down-scaled.
	NATIVE_TEXT_HEIGHT = osgx.PixelText.GLYPH_ROWS

	def __init__(
		self,
		width,
		height,
		bar_height=2.5 * NATIVE_TEXT_HEIGHT,
		show_percentage=True,
		**kwargs
	):
		super().__init__(width, height, **kwargs)

		"""
		g = osg.Geode(debug=True, name="GEODE")

		g.drawables.append(osg.Geometry(debug=True, name="EXPLOSION"))

		self.children.append(g)
		"""

		g = osg.Geometry()

		g.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.TRIANGLE_FAN, 0, 4))
		# No real vertex data -- positions come entirely from gl_VertexID in the shader, so
		# OSG has nothing to compute a bound from. Set one manually, matching the shader's own
		# clip-space output range, or cull traversal (testing against this Camera's own
		# identity-matrix frustum, which IS exactly the NDC cube) drops this silently.
		g.initialBound = osg.BoundingBox(-1, -1, -1, 1, 1, 1)

		p = osg.Program(name="pyosg_async.ProgressBar", shaders=(
			osg.Shader(osg.Shader.VERTEX, BAR_VERTEX_SHADER),
			osg.Shader(osg.Shader.FRAGMENT, BAR_FRAGMENT_SHADER)
		))

		self._attach(g, p)

		self._width = width
		self._height = height
		self._bar_pixel_height = bar_height
		self.stateSet.uniforms["uHeight"] = 2.0 * bar_height / height

		self._label = None

		if show_percentage:
			self._build_label()

	def _build_label(self):
		"""Adds a "NN%" osgx.PixelText label, white-inked, vertically centered inside the bar
		itself -- as a plain child of THIS Camera (same POST_RENDER subgraph as the bar quad),
		not a second nested Camera. PixelText's vertex shader positions glyphs via the standard
		osg_ModelViewProjectionMatrix; since this Camera's view/projection are both identity
		(see Progress.__init__), that MVP is just whatever Model matrix sits above the label in
		the scene graph -- so `self._label_transform` below IS this label's only "projection",
		reproducing an osg.Matrix.ortho2D(0, width, 0, height) camera (the convention every
		other PixelText call site uses, e.g. pyosg-dice.py's HUD label) as one plain matrix
		instead of a second Camera. See _position_label() for the actual math.
		"""

		self._label = osgx.PixelText("0%", 1.0 * self.NATIVE_TEXT_HEIGHT)
		self._label.ink = osg.Vec4(1.0, 1.0, 1.0, 1.0)

		geode = osg.Geode(name="progress-label")

		geode.drawables.append(self._label)

		self._label_transform = osg.MatrixTransform()

		self._label_transform.children.append(geode)

		self.children.append(self._label_transform)

		self._position_label()

	def _position_label(self):
		"""Re-centers the label (both axes) over the bar. Called on every update() since the
		text's width changes as the digit count changes ("0%" vs "100%") -- width is derived
		from cellSize * len(text) rather than PixelText's own bounding box, since advance
		defaults to cellSize (the monospace case) and this avoids depending on a bounding-box
		query that may not be exposed to Python.

		The label's matrix does two jobs at once, applied in this order (OSG's row-vector
		convention: `v * A * B` applies A first, so the written order below IS the applied
		order): position the label first, in the same pixel units PixelText's cellSize is
		already in, then convert THAT ENTIRE pixel-space placement to clip space in one step --
		exactly what osg.Matrix.ortho2D(0, width, 0, height) does as a projection matrix, just
		folded into this one model matrix instead, so it composes correctly under this Camera's
		identity projection without needing a second Camera to hold a real one.
		"""

		cell_size = self._label.cellSize
		text_width = cell_size * len(self._label.text)
		x = (self._width - text_width) / 2.0
		y = (self._bar_pixel_height - cell_size) / 2.0

		self._label_transform.matrix = (
			osg.Matrix.translate(x, y, 0.0) *
			osg.Matrix.scale(2.0 / self._width, 2.0 / self._height, 1.0) *
			osg.Matrix.translate(-1.0, -1.0, 0.0)
		)

	def update(self, fraction):
		super().update(fraction)

		if self._label is not None:
			self._label.text = f"{round(self._fraction * 100)}%"

			self._position_label()
