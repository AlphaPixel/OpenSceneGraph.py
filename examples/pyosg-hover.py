#!/usr/bin/env python3

"""Continuous hover with onEnter/onLeave scene feedback, ported from osgx's
examples/osgx-hover.cpp -- SYNC path only (osg.Image + osgx.PickReadbackSync,
Mode.CONTINUOUS, 1x1 sub-frustum). No --async here; this is step two toward
pyosg-match4.py's real interaction (see osgx's CLAUDE.md, "Planned/next steps for
picking" item 5) -- confirming onEnter/onLeave scene-graph mutation works from
Python before wiring it to Board.

Same five-sphere scene as pyosg-picking.py, but instead of printing on click, hovering
a sphere scales it up 1.35x (onEnter) and restores it (onLeave). PickHoverCallback
polls PickReadbackSync.lastID() on the update thread and fires onEnter/onLeave on
transitions -- always safe for scene graph mutation, regardless of readback mode.
"""

# Import side effect: fills in OSG_WINDOW/OSG_THREADING/OSG_GL_* env var defaults (see
# pyosg_example.py). Deliberately before `from OpenSceneGraph import *`, matching every other
# example -- these need to land before OSG's DisplaySettings reads them.
from pyosg_example import window_size

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

# Same core-profile-safe minimal Lambertian shader as pyosg-picking.py -- the pick camera's
# own shader (osgx::makePickCamera) is separate and already core-profile safe.
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
	"""Five colored spheres, each carrying a pickID uniform (1-5) and its own
	MatrixTransform -- returns (root, {id: (transform, base_matrix, name)}).
	"""
	root = osg.Group(name="scene")
	entries = {}

	for i, (pos, color, name) in enumerate(OBJECTS):
		base = osg.Matrix.translate(pos)
		mt = osg.MatrixTransform(base)
		geode = osg.Geode(name=name)
		drawable = osg.ShapeDrawable(osg.Sphere(osg.Vec3(), 1.5))

		drawable.color = color

		uid = osg.Uniform(osg.Uniform.Type.UNSIGNED_INT, "pickID")

		uid.value = i + 1

		geode.stateSet.uniforms.extend((uid,))
		geode.drawables.append(drawable)
		mt.children.append(geode)
		root.children.append(mt)

		entries[i + 1] = (mt, base, name)

	prog = osg.Program(name="pyosg-hover-scene", shaders=(
		osg.Shader(osg.Shader.VERTEX, SCENE_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, SCENE_FRAGMENT_SHADER),
	))

	root.stateSet.attributes.append(prog)

	return root, entries

# Set by build_scene(), read by configure_viewer() -- PickCameraSync's sub-frustum math (unlike
# pyosg-picking.py's, which passes pick1x1=False and doesn't use its w/h args at all) genuinely
# needs the real viewport size, but configure_viewer(viewer, root) has no direct way to receive
# it. Both runners and every __main__ block call build_scene() before configure_viewer(), so a
# same-module variable is a safe, ordering-guaranteed channel -- simpler than round-tripping (w, h)
# through the returned Node graph the way rb gets recovered below.
_viewport = (800, 600)

def build_scene(w, h):
	global _viewport

	_viewport = (w, h)

	scene, entries = create_scene()

	def on_enter(pick_id):
		mt, base, name = entries[pick_id]

		osg.notice(f"[pyosg-hover] enter -> ID {pick_id} ({name})")
		mt.matrix = osg.Matrix.scale(1.35, 1.35, 1.35) * base

	def on_leave(pick_id):
		mt, base, name = entries[pick_id]

		osg.notice(f"[pyosg-hover] leave -> ID {pick_id} ({name})")
		mt.matrix = base

	# 1x1 FBO -- PickCameraSync(pick1x1=True) builds a sub-frustum centered on the cursor
	# each frame instead of rendering the full window, so hover is pixel-perfect at zero
	# per-frame GPU cost regardless of scene density.
	pick_image = osg.Image()

	pick_image.allocateImage(1, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE)

	# makePickCamera() zeroes the image itself once attached (osgx/src/Picking.cpp) --
	# otherwise CONTINUOUS-mode hover polls leftover allocateImage() garbage before the
	# pick camera has ever rendered, decoding it as a bogus nonzero pick ID.
	pick_cam = osgx.makePickCamera(1, 1, pick_image)

	pick_cam.children.append(scene)

	rb = osgx.PickReadbackSync(
		1, pick_image, w, h,
		rule=osgx.PickRule.SPIRAL,
		mode=osgx.PickReadbackSync.Mode.CONTINUOUS,
	)

	rb.onEnter = on_enter
	rb.onLeave = on_leave

	# Stashed as pick_cam's updateCallback (a plain Callback, not the eventual
	# NodeCallbacksGroup) purely so configure_viewer() can recover this SAME rb object back out
	# of the returned root -- build_scene()'s contract is "return a Node", no second channel
	# for handing back a plain Python object it also needs later. Same pattern as
	# pyosg-picking.py.
	pick_cam.updateCallback = rb

	root = osg.Group(name="root")

	root.children.append(pick_cam)
	root.children.append(scene)

	return root

def configure_viewer(viewer, root):
	pick_cam, scene = root.children
	rb = pick_cam.updateCallback
	w, h = _viewport

	sync = osgx.PickCameraSync(viewer.camera, True, w, h, rb)
	hover = osgx.PickHoverCallback(rb)

	# Execution order matters: sync (aim the sub-frustum at the cursor) must run before
	# hover (checks rb.lastID(), fires onEnter/onLeave) which must run before rb itself
	# (samples this frame's 1x1 readback for next frame's lastID()). osgx.NodeCallbacksGroup
	# runs its members side by side in list order, same effect as the C++ example's
	# setNestedCallback() chain.
	pick_cam.updateCallback = osgx.NodeCallbacksGroup([sync, hover, rb])

	viewer.eventHandlers.append(osgx.PickHandler(rb, True))

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
