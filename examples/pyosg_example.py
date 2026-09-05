#!/usr/bin/env python3

import os
import pathlib

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

# This module installs at the top level of the wheel (OpenSceneGraph/examples/pyosg_example.py),
# a sibling of both `assets/` and the `lighting/` subpackage -- so this is the one place a plain
# `.parent` (not `.parent.parent`) correctly reaches the bundled asset tree regardless of which
# depth the CALLING file installs at. Deliberately kept here rather than scoped to the Lighting
# Series specifically (see [[project_lighting_series_package_asset_backport]]) -- the user wants
# this available as general infrastructure any future example (core or official tier) can rely on
# to "find its assets" without reinventing this lookup. Real consequence: pyosg_example.py's
# public surface is now something the examples wheel can depend on, same as any other cross-package
# API -- a change here that examples/lighting/*.py relies on means bumping/republishing BOTH
# wheels together, not just openscenegraph-examples alone.
#
# Formerly copy-pasted into every examples/lighting/*.py file (00-11) -- that duplication was in
# keeping with the series' deliberate "self-contained, diffable" teaching design for its shader/
# lighting-math code, but this is plain asset-resolution plumbing with no pedagogical value, and
# the duplication cost a real bug: a package-asset fallback fixed once in pyosg-khronos-viewer.py
# (see ai/context-todo-examplespackage.md) never got copied into any of the 12 lighting files,
# surfacing 2026-09-04 as "Cannot find environment manifest" against the newly-published
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

# HDR/manifest assets: osgx.findDataFile() (OSG_FILE_PATH) first, then this wheel's own bundled
# `assets/env/`. Only pre-baked manifests (.gltf) are ever bundled there, so a raw --hdr lookup
# (suffix="hdr") still falls through to the caller's own "clone glTF-Sample-Environments" error --
# correct, this wheel never ships the raw floating-point HDR sources, only baked env/ manifests.
def resolve_asset(value, suffix):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return str(path)

	found = osgx.findDataFile(value, (), suffix)

	if found:
		return found

	path = PACKAGE_ASSET_DIR / "env" / f"{path.stem}.{suffix}"

	return str(path) if path.is_file() else None

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

	`scale` is a multiple of osgx.PixelText's native glyph size (GLYPH_ROWS tall, GLYPH_COLS
	wide); the default of 2.0 draws at 2x native resolution, per the user's own request.
	`corner` is one of "bottom-left" (default), "bottom-right", "top-left", "top-right".
	`margin` is a literal pixel gap from the chosen corner's two edges.
	"""

	cell_size = osgx.PixelText.GLYPH_ROWS * scale
	pixel_text = osgx.PixelText(text, cell_size)

	# PixelText's own cellSize (and its default advance) is a SQUARE per-character cell sized
	# off GLYPH_ROWS (see osgx::PixelText::createAtlas()'s own comment: "a glyph block is only
	# GLYPH_COLS * pixelScale wide but GLYPH_ROWS * pixelScale tall" -- the glyph itself sits
	# centered in that square with margin on the narrower axis). Leaving advance at its default
	# spaces characters a full cellSize apart -- visibly wider than the glyph's own native
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
