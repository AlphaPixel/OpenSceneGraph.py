#!/usr/bin/env python3

import os
import pathlib
import sys

# Importing this module applies the examples' shared defaults: the OSG_WINDOW/OSG_THREADING
# environment defaults below and the GL 4.6 core-profile context defaults further down. Set
# PYOSG_EXAMPLE_DEFAULTS=0 before importing to apply none of them, e.g. to use an example's
# build_scene() inside a session whose contexts are configured elsewhere. The osgx.Library below
# is created either way.
APPLY_DEFAULTS = os.environ.get("PYOSG_EXAMPLE_DEFAULTS", "1") != "0"

# setdefault(), not update() - same reason as pyosg_visitor.py: an example that already set its
# own OSG_WINDOW/OSG_THREADING before importing this keeps what it set; this only fills in
# whatever it didn't. Importing this is the ONE place "SingleThreaded is mandatory" (a live
# non-SingleThreaded draw thread can deadlock a Viewer's destructor) is declared - an example
# that imports this for window_size() gets it whether or not its own env block remembers to say
# so, instead of a standing policy that only holds as well as 42 separate copy-pasted blocks do.
if APPLY_DEFAULTS:
	os.environ.setdefault("OSG_WINDOW", "50 50 800 600")
	os.environ.setdefault("OSG_THREADING", "SingleThreaded")

# The process's one osgx.Library, created when an example imports this module and released at
# interpreter exit. None when osgx is not installed (examples that need only OpenSceneGraph run
# without it) or when a Library is already alive (e.g. one an aipython REPL session created).
try:
	import osgx

except ImportError:
	LIBRARY = None

else:
	LIBRARY = None if osgx.Library.alive() else osgx.initialize()

# Derives (width, height) from OSG_WINDOW ("x y width height", e.g. "50 50 800 600") instead of a
# second, separately-hardcoded W, H module constant - one declared value per file instead of two
# that can silently drift apart. Standalone __main__ blocks call this; the pyosg/
# OpenSceneGraph.examples runners never do (they pass their own --width/--height straight into
# build_scene() and viewer.setUpViewInWindow()). See build_scene()'s own contract comment in
# pyosg-mrt.py: (w, h) stays an explicit argument on every build_scene(), never something it reads
# from the environment itself - this function is the caller-side counterpart of that rule, not an
# exception to it.
def window_size(default=(800, 600)):
	spec = os.environ.get("OSG_WINDOW")

	if not spec:
		return default

	x, y, w, h = spec.split()

	return int(w), int(h)

# Deliberately here, not at module top - osg must never be imported before the
# os.environ.setdefault() block above runs (see that block's own comment), and this module gets
# imported by every example specifically so those defaults land before ITS OWN internal osg
# import, let alone the caller's later `from OpenSceneGraph import *`.
from OpenSceneGraph import osg, osgDB
from OpenSceneGraph.GL import GL_DEPTH_TEST
import osgx

osgDB.Registry.instance().addFileExtensionAlias("glb", "gltf")

# GL 4.6 core-profile context defaults. Applied to the DisplaySettings singleton that every
# windowed and headless context is seeded from, not to os.environ: nothing is inherited by child
# processes, and it works whether or not the singleton already exists. A value the user supplied
# via OSG_GL_VERSION/OSG_GL_CONTEXT_VERSION or OSG_GL_CONTEXT_PROFILE_MASK is left alone.
if APPLY_DEFAULTS:
	_settings = osg.DisplaySettings.instance

	if "OSG_GL_VERSION" not in os.environ and "OSG_GL_CONTEXT_VERSION" not in os.environ:
		_settings.glContextVersion = "4.6"

	if "OSG_GL_CONTEXT_PROFILE_MASK" not in os.environ:
		_settings.glContextProfileMask = 1

# --headless [egl|native] (or PYOSG_HEADLESS=egl|native|1): every osgViewer.Viewer the example
# creates renders into a window_size() pbuffer instead of a window, writes its last frame to a PNG
# and ends the example's frame loop. See pyosg_headless.py for the options; they are removed from
# sys.argv here, before the example parses its own arguments.
import pyosg_headless

_headless, _backend, _frames, _out = pyosg_headless.parse_argv(sys.argv)

if _headless:
	pyosg_headless.install(_backend, _frames, _out, window_size())

# True when every osgViewer.Viewer renders offscreen, whether installed above or by a runner.
HEADLESS = pyosg_headless.installed()

# This module installs at the top level of the wheel (OpenSceneGraph/examples/pyosg_example.py),
# a sibling of both `assets/` and the `lighting/` subpackage - so this is the one place a plain
# `.parent` (not `.parent.parent`) correctly reaches the bundled asset tree regardless of which
# depth the CALLING file installs at. Deliberately kept here rather than scoped to the Lighting
# Series specifically - it is general infrastructure any future example (core or official tier)
# can rely on to "find its assets" without reinventing this lookup. Real consequence: pyosg_example.py's
# public surface is now something the examples wheel can depend on, same as any other cross-package
# API - a change here that examples/lighting/*.py relies on means bumping/republishing BOTH
# wheels together, not just openscenegraph-examples alone.
#
# Formerly copy-pasted into every examples/lighting/*.py file (00-11) - that duplication was in
# keeping with the series' deliberate "self-contained, diffable" teaching design for its shader/
# lighting-math code, but this is plain asset-resolution plumbing with no pedagogical value, and
# the duplication cost a real bug: a package-asset fallback fixed once in pyosg-khronos-viewer.py
# never got copied into any of the 12 lighting files, surfacing 2026-09-04 as
# "Cannot find environment manifest" against the newly-published
# openscenegraph-examples wheel. Centralized here instead of re-duplicating the fix 12 times.
PACKAGE_ASSET_DIR = pathlib.Path(__file__).resolve().parent / "assets"

# Bare name (e.g. "Corset") -> glTF-Sample-Assets/Models/<name>/glTF/<name>.gltf via
# osgx.findDataFile() (OSG_FILE_PATH) first, then this wheel's own bundled
# `assets/models/<name>/<name>.gltf`, same convention pyosg-khronos-viewer.py's own
# resolve_model() proved out.
def resolve_model(value):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return str(path)

	found = osgx.findDataFile(value) or osgx.findDataFile(
		path.stem, ("glTF-Sample-Assets/Models/{}/glTF/{}.gltf",)
	)

	if found:
		return found

	path = PACKAGE_ASSET_DIR / "models" / path.stem / f"{path.stem}.gltf"

	return str(path) if path.is_file() else None

# Data files such as a raw --hdr: the path as given, else osgx.findDataFile() (OSG_FILE_PATH),
# accepting only `suffix`. None if neither has it. Environment manifests use resolve_environment().
def resolve_asset(value, suffix):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return str(path)

	return osgx.findDataFile(value, (), suffix) or None

# osgx_environment manifests (--env): osgx.gltf.findEnvironment() (the name as given, else
# env/<stem>.gltf, through the working directory and OSG_FILE_PATH, where osgx-environment bakes
# live, e.g. OpenSceneGraph-Data/env), then this wheel's bundled `assets/env/`. The bundled bakes
# are reduced-size (wheel-sized), so that fallback warns. None if nothing matches.
def resolve_environment(value):
	path = pathlib.Path(value).expanduser()
	found = osgx.gltf.findEnvironment(str(path))

	if found:
		return found

	bundled = PACKAGE_ASSET_DIR / "env" / f"{path.stem}.gltf"

	if not bundled.is_file():
		return None

	print(
		f"pyosg_example: WARNING: no {path.stem!r} environment on OSG_FILE_PATH (env/{path.stem}.gltf); "
		f"using the bundled reduced-size bake {bundled}",
		file=sys.stderr,
	)

	return str(bundled)

def _vec3d(text):
	"""argparse type for an "X,Y,Z" argument."""

	import argparse

	try:
		x, y, z = (float(v) for v in text.split(","))

	except ValueError:
		raise argparse.ArgumentTypeError(f"expected X,Y,Z, got {text!r}")

	return osg.Vec3d(x, y, z)

# The initial-camera options: osgx's C++ examples' (osgx-example.hpp) --camera-eye/--camera-center/
# --camera-up, plus --camera. Pair with apply_camera().
def add_camera_arguments(parser):
	"""Add --camera FILE and --camera-eye/--camera-center/--camera-up X,Y,Z to an argparse parser."""

	group = parser.add_argument_group("initial camera")

	group.add_argument(
		"--camera",
		metavar="FILE",
		help="glTF camera (osgx.gltf.loadCamera(), e.g. a Khronos glTF-Sample-Viewer export): its "
			"pose and vertical field of view",
	)
	group.add_argument("--camera-eye", type=_vec3d, metavar="X,Y,Z", help="initial camera eye")
	group.add_argument("--camera-center", type=_vec3d, metavar="X,Y,Z", help="initial camera look-at center")
	group.add_argument("--camera-up", type=_vec3d, metavar="X,Y,Z", help="initial camera up vector")

# Applies add_camera_arguments()'s options to `viewer` (manipulator and its node already set, not
# yet realized). The pose starts from the manipulator's computed home position (or the camera's
# view matrix without a manipulator), then --camera replaces it, then each --camera-eye/center/up
# replaces its one value. With a manipulator the result becomes its fixed home position, so
# home() (space) returns to it.
#
# A --camera pose's center is moved to the point on its view ray nearest the home center, since a
# glTF camera stores no focus distance and an orbit manipulator pivots about the center. Only its
# fovy is applied to the projection: the aspect ratio stays the window's, and near/far stay OSG's
# per-frame computation.
def apply_camera(viewer, args):
	"""Apply add_camera_arguments()'s options to a viewer; exits if --camera cannot be loaded."""

	if not (args.camera or args.camera_eye or args.camera_center or args.camera_up):
		return

	camera = viewer.camera
	manipulator = viewer.cameraManipulator

	if manipulator is not None:
		if manipulator.autoComputeHomePosition and manipulator.node is not None:
			manipulator.computeHomePosition(camera)

		eye, center, up = manipulator.homePosition

	else:
		eye, center, up = camera.viewMatrix.getLookAt()

	if args.camera:
		exported = osgx.gltf.loadCamera(str(pathlib.Path(args.camera).expanduser()))

		if exported is None:
			sys.exit(f"Failed to load camera: {args.camera}")

		pose = exported.viewpoint.withPivot(center)
		eye, center, up = pose.eye, pose.center, pose.up

		_, aspect, near, far = camera.projectionMatrix.getPerspective()

		camera.projectionMatrix = osg.Matrixd.perspective(exported.fovy, aspect, near, far)

	if args.camera_eye:
		eye = args.camera_eye

	if args.camera_center:
		center = args.camera_center

	if args.camera_up:
		up = args.camera_up

	if manipulator is not None:
		manipulator.autoComputeHomePosition = False
		manipulator.homePosition = (eye, center, up)
		manipulator.home(0.0)

	else:
		camera.viewMatrix = osg.Matrixd.lookAt(eye, center, up)

# Same technique as pyosg_async.py's ProgressBar._build_label()/_position_label() - a plain
# child of an identity-view/projection POST_RENDER Camera, hand-composed translate*scale*translate
# matrix folding pixel-space placement directly into clip space (osg's row-vector convention, so
# written left-to-right IS the applied order: position in pixel space first, then map that whole
# placement into NDC in one step) instead of a second Camera holding a real ortho2D projection.
# Fixed to the (w, h) passed in, same limitation ProgressBar's label has: build_scene(w, h) has no
# live viewer to read a real/resized window size from, so this does not track a later resize --
# pass the SAME (w, h) build_scene() itself received.
def label(text, w, h, corner="bottom-left", scale=2.0, margin=12.0, ink=(1.0, 1.0, 1.0, 1.0)):
	"""A small screen-space HUD text overlay any example can drop into its scene, e.g. for
	"Press R to reroll"-style on-screen hints. Returns a ready-to-attach osg.Camera - add it as a
	child anywhere in build_scene()'s returned graph:

		root.children.append(pyosg_example.label("Press R to reroll", w, h))

	`scale` is a multiple of osgx.PixelText's native glyph size (GLYPH_ROWS tall, GLYPH_COLS
	wide); the default of 2.0 draws at 2x native resolution, per the user's own request.
	`corner` is one of "bottom-left" (default), "bottom-right", "top-left", "top-right".
	`margin` is a literal pixel gap from the chosen corner's two edges.
	"""

	cell_size = osgx.PixelText.GLYPH_ROWS * scale
	pixel_text = osgx.PixelText(text, cell_size)

	# PixelText's own cellSize (and its default advance) is a SQUARE per-character cell sized
	# off GLYPH_ROWS (see osgx::PixelText::createAtlas()'s own comment: "a glyph block is only
	# GLYPH_COLS * pixelScale wide but GLYPH_ROWS * pixelScale tall" - the glyph itself sits
	# centered in that square with margin on the narrower axis). Leaving advance at its default
	# spaces characters a full cellSize apart - visibly wider than the glyph's own native
	# GLYPH_COLS-wide footprint. Tightening it to the glyph's real width gives ordinary,
	# non-monospace-square-cell text spacing instead.
	advance = osgx.PixelText.GLYPH_COLS * scale

	pixel_text.advance = advance
	pixel_text.ink = osg.Vec4(*ink)

	geode = osg.Geode(name="hud-label")

	geode.drawables.append(pixel_text)

	# Matches PixelText's own internal width formula (see PixelText.cpp's computeBoundingBox()):
	# every glyph but the last only takes `advance` of horizontal room; the last one still needs
	# its own full cellSize, since nothing after it truncates its trailing margin.
	text_width = max(len(text) - 1, 0) * advance + cell_size
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
	camera.viewport = osg.Viewport(0, 0, w, h)
	camera.viewMatrix = osg.Matrix.identity()
	camera.projectionMatrix = osg.Matrix.identity()
	camera.allowEventFocus = False
	camera.stateSet.modes[GL_DEPTH_TEST] = osg.StateAttribute.OFF
	camera.children.append(transform)

	return camera
