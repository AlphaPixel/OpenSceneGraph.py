#!/usr/bin/env python3

"""Hi-Z/occlusion-culling test scene: a ring of "chunks" placed radially around a
stationary camera, each pairing a visible proxy sphere with an osgx.debug.ShaderClockDrawable
carrying its own fixed, increasing GPU stall duration. Sibling to osgx's C++
examples/osgx-culling.cpp (same CULLED/VISIBLE intent) and examples/osgx-shaderclock.cpp
(same ShaderClockDrawable usage) - this is the Python/osgx.FirstPersonManipulator version.

Proves two things as you look around with WASD + mouse look:

  1. Chunks entirely outside the view frustum are skipped by ordinary OSG node-level
     culling - no custom cull callback needed, the proxy sphere's own bounding sphere
     drives it. Watch them appear/disappear at the edges of the view.

  2. The GPU really does stall by close to the requested amount: the osgx.imgui "Profiler"
     section shows live per-drawable GPU ms (osgx.debug.ProfilerVisitor under the hood), so
     each chunk's stall reads out individually, and culled chunks simply stop reporting -
     turn to bring progressively more (and heavier, redder) chunks into view and watch it
     climb.

Each chunk's proxy sphere is colored/sized green->red, small->large by its assigned
duration, so "heavier" chunks are visually obvious before you even check the stats. Each
sphere also carries its index as an osgx.PixelText decal, oriented to face back toward the
ring's center (where the camera sits) - lets you confirm by eye that the numbers pass evenly
under the crosshair as you spin in place, i.e. that the camera really is centered.

Press 'f' to freeze: releases the mouse (so you can click into the imgui panel) and stops
WASD/look, without tearing down the manipulator. Press 'f' again to resume.
"""

# Also applies the shared example defaults (see pyosg_example.py): OSG_WINDOW/SingleThreaded,
# the GL 4.6 core-profile context, and the osgx.Library.
from pyosg_example import window_size, label

from OpenSceneGraph import *

import argparse
import math
import osgx

# Smallest (lightest, i=0) / largest (heaviest, i=count-1) proxy sphere radius - shared by the
# sphere itself, its label decal's placement, and the floor's sizing below.
SPHERE_RADIUS_MIN = 0.6
SPHERE_RADIUS_MAX = 1.0

def sphere_radius(t):
	return SPHERE_RADIUS_MIN + (SPHERE_RADIUS_MAX - SPHERE_RADIUS_MIN) * t

# A flat proxy floor, sized just large enough to sit under the whole ring (radius + the largest
# sphere's own radius, so nothing overhangs the edge) - purely a visual ground reference, to make
# "am I actually centered/level" judgable by eye instead of guessed at.
def build_floor(radius, thickness=0.1):
	half = radius + SPHERE_RADIUS_MAX
	center_z = -SPHERE_RADIUS_MAX - thickness / 2.0

	geode = osg.Geode(name="floor.geode")
	floor = osg.ShapeDrawable(osg.Box(osg.Vec3(0.0, 0.0, center_z), half * 2.0, half * 2.0, thickness))

	floor.color = osg.Vec4(0.15, 0.15, 0.18, 1.0)

	geode.drawables.append(floor)

	return geode

# A single-digit/double-digit index, decaled onto the near (ring-center-facing) surface of a
# chunk's proxy sphere - same "flat PixelText quad placed in 3D" idea as osgx's Polyhedron-face
# decals, just oriented by hand instead of baked per-face. `angle` is the SAME angle the chunk's
# own position was placed at, so "inward" (back toward the ring center/camera) falls straight
# out of it rather than being re-derived from a world position. Built in the chunk's own LOCAL
# space (sphere center = local origin) so it can be nested directly under that chunk's transform.
def make_label_decal(index, angle, proxy_radius, cell_size=0.5):
	text = str(index)
	pixel_text = osgx.PixelText(text, cell_size)

	pixel_text.ink = osg.Vec4(1.0, 1.0, 1.0, 1.0)

	# PixelText's own default advance equals cellSize (see pyosg_example.label()'s own comment on
	# this) - width = len(text) cells, each cellSize wide.
	text_width = len(text) * cell_size

	# The direction back toward the ring center, where the camera lives - this is local-space,
	# but since the chunk's own transform is a pure translation, a direction computed this way is
	# identical in local and world space.
	inward = osg.Vec3(-math.cos(angle), -math.sin(angle), 0.0)
	outward = osg.Vec3(math.cos(angle), math.sin(angle), 0.0)

	# Anchored a touch beyond the sphere's own surface (toward the camera) so it doesn't
	# z-fight with it. inverse(lookAt(eye, center, up)) maps local +Z to (eye - center), NOT
	# (center - eye) - `center` has to sit further OUTWARD than `eye`, not further inward, or
	# local +Z (PixelText's "toward viewer" face) ends up pointing outward instead of in, and the
	# camera at the ring's center sees the decal's back (horizontally mirrored).
	eye = inward * (proxy_radius + 0.05)
	center = eye + outward * 10.0
	up = osg.Vec3(0.0, 0.0, 1.0)

	# Same "camera placement matrix" idiom as pyosg_repl.py's own view/model matrix helpers:
	# inverse(lookAt()) maps PixelText's local (X=right, Y=up, Z=toward viewer) axes onto
	# (right, up, inward) at `eye`, exactly the orientation a label facing the ring's center needs.
	place = osg.Matrix.inverse(osg.Matrix.lookAt(eye, center, up))
	recenter = osg.Matrix.translate(-text_width / 2.0, -cell_size / 2.0, 0.0)

	geode = osg.Geode(name=f"chunk.{index}.label.geode")

	geode.drawables.append(pixel_text)

	transform = osg.MatrixTransform(recenter * place, name=f"chunk.{index}.label.xf")

	transform.children.append(geode)

	return transform

def build_scene(w, h, count=12, radius=15.0, base_ms=1.0, step_ms=1.0):
	root = osg.Group(name="root")

	root.children.append(build_floor(radius))

	for i in range(count):
		t = i / max(count - 1, 1)
		angle = 2.0 * math.pi * i / count
		x = radius * math.cos(angle)
		y = radius * math.sin(angle)
		duration = base_ms + i * step_ms
		r = sphere_radius(t)

		sphere = osg.ShapeDrawable(osg.Sphere(osg.Vec3(), r))

		sphere.color = osg.Vec4(t, 1.0 - t, 0.25, 1.0)

		stall = osgx.debug.ShaderClockDrawable()

		stall.duration = duration

		geode = osg.Geode(name=f"chunk.{i}.geode")

		geode.drawables.append(sphere)
		geode.drawables.append(stall)

		transform = osg.MatrixTransform(osg.Matrix.translate(x, y, 0.0), name=f"chunk.{i}.xf")

		transform.children.append(geode)
		transform.children.append(make_label_decal(i, angle, r))
		root.children.append(transform)

		print(f"[pyosg-culling] chunk {i}: duration={duration:.1f}ms angle={math.degrees(angle):.0f}deg")

	root.children.append(label("WASD: move | mouse: look | 'f': freeze + free the cursor", w, h))

	return root

# 'f' toggles between the manipulator's normal LookStyle.ALWAYS (continuous hide+warp+accumulate
# mouse look - see osgx::PlayerManipulator<Base> in Manipulators.hpp) and LookStyle.CLICK_HOLD,
# which releases the cursor immediately (CursorCapture::setCaptured(false) un-hides it) and only
# recaptures while the look button is held - FirstPersonManipulator never binds that to LEFT, so
# clicking into the imgui panel is safe either way. moveSpeed is zeroed/restored alongside it so
# WASD doesn't also creep the camera while you're trying to drag a slider.
class FreezeToggleHandler(osgGA.GUIEventHandler):
	def __init__(self, manip):
		super().__init__()

		self.manip = manip
		self.move_speed = manip.moveSpeed
		self.frozen = False

	def handle(self, ea, aa):
		if ea.handled or ea.type != osgGA.GUIEventAdapter.KEYUP or ea.key not in (ord("f"), ord("F")):
			return False

		self.frozen = not self.frozen

		if self.frozen:
			self.manip.lookStyle = osgx.LookStyle.CLICK_HOLD
			self.manip.moveSpeed = 0.0

		else:
			self.manip.lookStyle = osgx.LookStyle.ALWAYS
			self.manip.moveSpeed = self.move_speed

		return True

def configure_viewer(viewer, root):
	manip = osgx.FirstPersonManipulator()

	# Flipped from osgx.FirstPersonManipulator's own default (True - see Manipulators.hpp).
	# manip.invertY = not manip.invertY

	# Camera planted at the ring's center, looking out along +Y - the home position OSG would
	# auto-compute from root's bounds would instead pull the camera BACK to frame everything at
	# once, which defeats the whole point (chunks need to fall in/out of frustum as you turn).
	manip.autoComputeHomePosition = False
	manip.homePosition = (osg.Vec3d(0.0, 0.0, 0.0), osg.Vec3d(0.0, 1.0, 0.0), osg.Vec3d(0.0, 0.0, 1.0))

	viewer.cameraManipulator = manip

	manip.home(0.0)

	viewer.eventHandlers.append(FreezeToggleHandler(manip))

	gui = osgx.imgui.Widget(viewer)

	gui.addStatsSection(viewer, default_open=True)
	gui.addProfilerSection(viewer, root, default_open=True)

def parse_args():
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

	parser.add_argument("--count", type=int, default=12, help="number of chunks placed around the ring (default: 12)")
	parser.add_argument("--radius", type=float, default=15.0, help="ring radius in world units (default: 15.0)")
	parser.add_argument("--base-ms", type=float, default=1.0, help="GPU stall duration of chunk 0, in milliseconds (default: 1.0)")
	parser.add_argument("--step-ms", type=float, default=1.0, help="per-chunk duration increase around the ring, in milliseconds (default: 1.0)")

	return parser.parse_args()

if __name__ == "__main__":
	args = parse_args()

	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	W, H = window_size()

	viewer = osgViewer.Viewer()

	root = build_scene(W, H, args.count, args.radius, args.base_ms, args.step_ms)

	viewer.sceneData = root

	configure_viewer(viewer, root)

	while not viewer.done:
		viewer.frame()
