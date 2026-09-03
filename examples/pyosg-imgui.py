#!/usr/bin/env python3

# Minimal osgx.imgui.Widget smoke test -- mirrors osgx's own
# examples/osgx-imgui.cpp almost exactly (three spheres, StatsSection,
# and one custom addSection with a slider knob). Deliberately simple: if the
# panel/mouse-capture behaves correctly here but not in a more complex scene
# (e.g. 11-sketchfab.py's MRT/G-buffer pipeline), the bug is in that scene's
# camera/GL-state setup, not in the Python bindings themselves.

# Import side effect: fills in OSG_WINDOW/OSG_THREADING/OSG_GL_* env var defaults (see
# pyosg_example.py). Deliberately before `from OpenSceneGraph import *`, matching every other
# example -- these need to land before OSG's DisplaySettings reads them.
from pyosg_example import window_size

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

def build_scene(w, h):
	root = osg.Group(name="Root")

	for i in range(3):
		xform = osg.MatrixTransform(osg.Matrix.translate(osg.Vec3(i * 12.0, 0.0, 0.0)))
		xform.name = f"Transform_{i}"

		geode = osg.Geode(name=f"Geode_{i}")

		sphere = osg.ShapeDrawable(osg.Sphere(osg.Vec3(), 5.0))
		sphere.name = f"Sphere_{i}"

		geode.drawables.append(sphere)
		xform.children.append(geode)
		root.children.append(xform)

	return root

# osgx.imgui.Widget needs a live Viewer (it pushes itself onto the view's event handler list),
# which build_scene() never receives -- same reason pyosg-mrt.py's own interactivity lives here
# instead of in build_scene().
def configure_viewer(viewer, root):
	gui = osgx.imgui.Widget(viewer)

	gui.addStatsSection(viewer)

	knob = {"value": 1.0}

	def draw_demo_knob(ri):
		osgx.imgui.text("Hello from a Python addSection callback")
		osgx.imgui.separator()

		changed, value = osgx.imgui.slider_float("Demo Knob", knob["value"], 0.0, 4.0)

		if changed:
			knob["value"] = value

			print(f"[demo] knob={value:.3f}", flush=True)

	gui.addSection("Demo", draw_demo_knob)

if __name__ == "__main__":
	v = osgViewer.Viewer()
	root = build_scene(*window_size())

	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()

	configure_viewer(v, root)

	while not v.done:
		v.frame()
