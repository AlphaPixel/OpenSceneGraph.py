#!/usr/bin/env python3

import os

# setdefault(), not update() -- same reason as pyosg_visitor.py: an example that already set its
# own OSG_WINDOW/OSG_THREADING/etc. (window size, a non-default GL version, ...) before importing
# this keeps what it set; this only fills in whatever it didn't. Importing this is now the ONE
# place "SingleThreaded is mandatory" (see feedback_viewer_close_threading_deadlock -- a live
# non-SingleThreaded draw thread can deadlock a Viewer's destructor) is declared -- an example
# that imports this for window_size() gets it whether or not its own env block remembers to say
# so, instead of a standing policy that only holds as well as 42 separate copy-pasted blocks do.
os.environ.setdefault("OSG_WINDOW", "50 50 800 600")
os.environ.setdefault("OSG_THREADING", "SingleThreaded")
os.environ.setdefault("OSG_GL_CONTEXT_PROFILE_MASK", "1")
os.environ.setdefault("OSG_GL_VERSION", "4.6")
os.environ.setdefault("OSG_GL_CONTEXT_VERSION", "4.6")

# Derives (width, height) from OSG_WINDOW ("x y width height", e.g. "50 50 800 600") instead of a
# second, separately-hardcoded W, H module constant -- one declared value per file instead of two
# that can silently drift apart. Standalone __main__ blocks call this; the pyosg/
# OpenSceneGraph.examples runners never do (they pass their own --width/--height straight into
# build_scene() and viewer.setUpViewInWindow()). See build_scene()'s own contract comment in
# pyosg-mrt.py: (w, h) stays an explicit argument on every build_scene(), never something it reads
# from the environment itself -- this function is the caller-side counterpart of that rule, not an
# exception to it.
def window_size(default=(800, 600)):
	spec = os.environ.get("OSG_WINDOW")

	if not spec:
		return default

	x, y, w, h = spec.split()

	return int(w), int(h)

# Deliberately here, not at module top -- osg must never be imported before the
# os.environ.setdefault() block above runs (see that block's own comment), and this module gets
# imported by every example specifically so those defaults land before ITS OWN internal osg
# import, let alone the caller's later `from OpenSceneGraph import *`.
from OpenSceneGraph import osg
from OpenSceneGraph.GL import GL_DEPTH_TEST
import osgx

# Same technique as pyosg_async.py's ProgressBar._build_label()/_position_label() -- a plain
# child of an identity-view/projection POST_RENDER Camera, hand-composed translate*scale*translate
# matrix folding pixel-space placement directly into clip space (osg's row-vector convention, so
# written left-to-right IS the applied order: position in pixel space first, then map that whole
# placement into NDC in one step) instead of a second Camera holding a real ortho2D projection.
# Fixed to the (w, h) passed in, same limitation ProgressBar's label has: build_scene(w, h) has no
# live viewer to read a real/resized window size from, so this does not track a later resize --
# pass the SAME (w, h) build_scene() itself received.
def label(text, w, h, corner="bottom-left", scale=2.0, margin=12.0, ink=(1.0, 1.0, 1.0, 1.0)):
	"""A small screen-space HUD text overlay any example can drop into its scene, e.g. for
	"Press R to reroll"-style on-screen hints. Returns a ready-to-attach osg.Camera -- add it as a
	child anywhere in build_scene()'s returned graph:

		root.children.append(pyosg_example.label("Press R to reroll", w, h))

	`scale` is a multiple of osgx.PixelText's native glyph size (GLYPH_ROWS); the default of 2.0
	draws at 2x native resolution, per the user's own request. `corner` is one of "bottom-left"
	(default), "bottom-right", "top-left", "top-right". `margin` is a literal pixel gap from the
	chosen corner's two edges.
	"""

	cell_size = osgx.PixelText.GLYPH_ROWS * scale
	pixel_text = osgx.PixelText(text, cell_size)

	pixel_text.ink = osg.Vec4(*ink)

	geode = osg.Geode(name="hud-label")

	geode.drawables.append(pixel_text)

	text_width = cell_size * len(text)
	corners = {
		"bottom-left": (margin, margin),
		"bottom-right": (w - margin - text_width, margin),
		"top-left": (margin, h - margin - cell_size),
		"top-right": (w - margin - text_width, h - margin - cell_size),
	}

	if corner not in corners:
		raise ValueError(f"label: unknown corner {corner!r} (expected one of {sorted(corners)})")

	x, y = corners[corner]
	transform = osg.MatrixTransform()

	transform.matrix = (
		osg.Matrix.translate(x, y, 0.0) *
		osg.Matrix.scale(2.0 / w, 2.0 / h, 1.0) *
		osg.Matrix.translate(-1.0, -1.0, 0.0)
	)
	transform.children.append(geode)

	camera = osg.Camera(name="hud-label-camera")

	camera.renderOrder = osg.Camera.POST_RENDER
	camera.clearMask = 0
	camera.referenceFrame = osg.Transform.ABSOLUTE_RF
	camera.viewMatrix = osg.Matrix.identity()
	camera.projectionMatrix = osg.Matrix.identity()
	camera.allowEventFocus = False
	camera.stateSet.modes[GL_DEPTH_TEST] = osg.StateAttribute.OFF
	camera.children.append(transform)

	return camera
