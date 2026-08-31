#!/usr/bin/env python3

"""Texture-based object-ID picking, ported from osgx's examples/osgx-picking.cpp --
the simplest slice of it: a full-window SYNC pick camera (osg::Image readback,
osgx.PickReadbackSync), one sphere per pick ID, left-click prints the hit
via osg.notice(). No small-pick/1x1-sub-frustum/async variants here -- this is
step one toward examples/pyosg-hover.py (continuous hover via onEnter/onLeave),
which layers PickHoverCallback on top of the same pieces.

The pick camera renders the SAME scene a second time into an off-screen FBO using
a shader that outputs each object's pickID as a color instead of its real
appearance (see osgx/Picking.hpp's hook-based pick shader) -- osgx.makePickCamera()
builds that camera; the caller (this file) is responsible for parenting the
scene under it and keeping its view/projection synced to the main camera every
frame (osgx.PickCameraSync).
"""

# Import side effect: fills in OSG_WINDOW/OSG_THREADING/OSG_GL_* env var defaults (see
# pyosg_example.py). Deliberately before `from OpenSceneGraph import *`, matching every other
# example -- these need to land before OSG's DisplaySettings reads them.
from pyosg_example import window_size

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

# The pick camera's own shader (osgx::makePickCamera, osgx/Picking.hpp) is already core-profile
# safe and OVERRIDEs it during the pick pass regardless -- this is for the MAIN visible render,
# which had nothing at all before and was silently riding OSG's legacy fixed-function fallback
# (gl_Vertex/gl_Normal/etc.), invisible under a real GL_CORE_PROFILE context. Minimal Lambertian,
# same osg_Vertex/osg_Normal/osg_Color/osg_*Matrix aliasing pattern as pyosg-rtt.py's scene shader.
SCENE_VERTEX_SHADER = """
#version 330 core

in vec4 osg_Vertex;
in vec3 osg_Normal;
in vec4 osg_Color;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;
out vec4 vColor;

void main() {
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vColor = osg_Color;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

SCENE_FRAGMENT_SHADER = """
#version 330 core

in vec3 vNormal;
in vec4 vColor;

out vec4 fragColor;

void main() {
	const vec3 L = vec3(0.4, 0.6, 0.7);

	float diffuse = max(dot(normalize(vNormal), normalize(L)), 0.0);
	float light = 0.35 + 0.65 * diffuse;

	fragColor = vec4(vColor.rgb * light, vColor.a);
}
"""

OBJECTS = (
	(osg.Vec3(-8.0, 0.0, 0.0), osg.Vec4(1.0, 0.2, 0.2, 1.0), "red"),
	(osg.Vec3(-4.0, 0.0, 0.0), osg.Vec4(0.2, 1.0, 0.2, 1.0), "green"),
	(osg.Vec3( 0.0, 0.0, 0.0), osg.Vec4(0.2, 0.2, 1.0, 1.0), "blue"),
	(osg.Vec3( 4.0, 0.0, 0.0), osg.Vec4(1.0, 1.0, 0.2, 1.0), "yellow"),
	(osg.Vec3( 8.0, 0.0, 0.0), osg.Vec4(1.0, 0.2, 1.0, 1.0), "magenta"),
)

def create_scene():
	"""Five colored spheres, each carrying a pickID uniform (1-5). ID 0 = background."""

	root = osg.Group(name="scene")

	for i, (pos, color, name) in enumerate(OBJECTS):
		mt = osg.MatrixTransform(osg.Matrix.translate(pos))
		geode = osg.Geode(name=name)
		drawable = osg.ShapeDrawable(osg.Sphere(osg.Vec3(), 1.5))

		drawable.color = color

		uid = osg.Uniform(osg.Uniform.Type.UNSIGNED_INT, "pickID")

		uid.value = i + 1

		geode.stateSet.uniforms.extend((uid,))
		geode.drawables.append(drawable)
		mt.children.append(geode)
		root.children.append(mt)

	prog = osg.Program(name="pyosg-picking-scene", shaders=(
		osg.Shader(osg.Shader.VERTEX, SCENE_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, SCENE_FRAGMENT_SHADER),
	))

	root.stateSet.attributes.append(prog)

	return root

# Everything here is buildable without a Viewer EXCEPT PickCameraSync (needs viewer.camera) --
# that alone is configure_viewer()'s job below. rb is stashed as pick_cam's updateCallback
# (a plain Callback, not the eventual NodeCallbacksGroup) purely so configure_viewer can recover
# the SAME rb object back out of the returned root -- build_scene()'s contract is "return a Node",
# no second channel for handing back a plain Python object it also needs later.
def build_scene(w, h):
	scene = create_scene()

	pick_image = osg.Image()

	pick_image.allocateImage(w, h, 1, GL_RGBA, GL_UNSIGNED_BYTE)

	pick_cam = osgx.makePickCamera(w, h, pick_image)

	pick_cam.children.append(scene)

	rb = osgx.PickReadbackSync(
		1, pick_image, w, h,
		rule=osgx.PickRule.SPIRAL,
		mode=osgx.PickReadbackSync.Mode.CLICK,
	)

	def on_pick(pick_id, action):
		if pick_id:
			name = OBJECTS[pick_id - 1][2]

			osg.notice(f"[pyosg-picking] pick ({rb.mouseX}, {rb.mouseY}) -> ID {pick_id} ({name})")
		else:
			osg.notice(f"[pyosg-picking] pick ({rb.mouseX}, {rb.mouseY}) -> background")

	rb.onPick = on_pick
	pick_cam.updateCallback = rb

	root = osg.Group(name="root")

	root.children.append(pick_cam)
	root.children.append(scene)

	return root

def configure_viewer(viewer, root):
	pick_cam, scene = root.children
	rb = pick_cam.updateCallback

	# The viewer's master camera exists as soon as the Viewer does -- only its
	# GraphicsContext/window needs realize() -- so it's safe to hand viewer.camera to
	# PickCameraSync's constructor right away.
	sync = osgx.PickCameraSync(viewer.camera, False, 0, 0, rb)

	# osgx.NodeCallbacksGroup runs several same-slot callbacks side by side -- the usual
	# alternative to chaining them one-at-a-time via Callback.nestedCallback.
	pick_cam.updateCallback = osgx.NodeCallbacksGroup([sync, rb])

	viewer.eventHandlers.append(osgx.PickHandler(rb, False))

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	W, H = window_size()

	viewer = osgViewer.Viewer()
	viewer.cameraManipulator = osgGA.TrackballManipulator()

	root = build_scene(W, H)

	viewer.sceneData = root

	configure_viewer(viewer, root)

	while not viewer.done:
		viewer.frame()
