#!/usr/bin/env python3
#vimrun! ../examples/pyosg-taa.py

# Minimal temporal anti-aliasing (TAA) / temporal supersampling proof.
#
# This is deliberately only "Layer 1" of a modern TAA implementation:
#
#   1. Jitter the geometry camera by a different sub-pixel offset each frame.
#   2. Accumulate those samples into a persistent history texture.
#   3. Reset history when the user moves the camera.
#
# A still view therefore converges over 16 frames to a visibly smoother image.
# During camera interaction it starts over; it does NOT drag stale pixels across
# the screen and call that TAA.
#
# Two possible later layers are intentionally out of scope here:
#
#   Layer 2 -- camera-motion reprojection
#     Reconstruct each current pixel from depth, project it through last frame's
#     view/projection matrix, and sample history at that previous screen position.
#     Add neighborhood clamping/depth rejection to limit ghosting and disocclusion.
#
#   Layer 3 -- independently moving/deforming objects
#     Add a velocity MRT and retain previous model (and, for skinned meshes, bone)
#     transforms. This makes temporal state part of the scene/animation system,
#     rather than merely a fullscreen post-process.
#
# The plumbing follows pyosg-mrt.py: a PRE_RENDER geometry camera writes an MRT
# G-buffer, a fullscreen PRE_RENDER pass shades it, another fullscreen pass performs
# the temporal resolve, and a POST_RENDER camera displays the newest history texture.
# Two resolve cameras and two display cameras alternate via nodeMask, avoiding an
# illegal read/write feedback loop on one texture.
#
# Keys:
#   0 = accumulated TAA (default)
#   1 = current jittered frame (no accumulation)
#   2 = exaggerate jitter 12x, to make the sampling pattern obvious
#   R = reset history

import os

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6",
})

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import pyosg_repl

W, H = 800, 600
HISTORY_LENGTH = 16

SCENE_VERTEX = """
#version 330 core
in vec4 osg_Vertex;
in vec4 osg_Color;
in vec3 osg_Normal;
uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat3 osg_NormalMatrix;
out vec4 vColor;
out vec3 vNormal;
void main() {
	vColor = osg_Color;
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

GBUFFER_FRAGMENT = """
#version 330 core
in vec4 vColor;
in vec3 vNormal;
layout(location=0) out vec4 outColor;
layout(location=1) out vec4 outNormal;
void main() {
	outColor = vColor;
	outNormal = vec4(normalize(vNormal), 1.0);
}
"""

FULLSCREEN_VERTEX = """
#version 330 core
in vec4 osg_Vertex;
in vec2 osg_MultiTexCoord0;
out vec2 uv;
void main() {
	uv = osg_MultiTexCoord0;
	gl_Position = osg_Vertex;
}
"""

# Simple directional shading gives the sphere both a smooth curved silhouette and
# high-contrast internal detail. TAA itself remains completely independent of it.
SHADE_FRAGMENT = """
#version 330 core
uniform sampler2D colorTex;
uniform sampler2D normalTex;
in vec2 uv;
out vec4 fragColor;
void main() {
	vec4 albedo = texture(colorTex, uv);
	vec3 rawN = texture(normalTex, uv).xyz;
	if (dot(rawN, rawN) < 0.01) {
		fragColor = vec4(0.025, 0.025, 0.035, 1.0);
		return;
	}
	vec3 N = normalize(rawN);
	float light = 0.18 + 0.82 * max(dot(N, normalize(vec3(.3, .4, 1.0))), 0.0);
	fragColor = vec4(albedo.rgb * light, 1.0);
}
"""

TAA_FRAGMENT = """
#version 330 core
uniform sampler2D currentTex;
uniform sampler2D historyTex;
uniform float historyWeight;
in vec2 uv;
out vec4 fragColor;
void main() {
	vec3 current = texture(currentTex, uv).rgb;
	vec3 history = texture(historyTex, uv).rgb;
	fragColor = vec4(mix(current, history, historyWeight), 1.0);
}
"""

DISPLAY_FRAGMENT = """
#version 330 core
uniform sampler2D displayTex;
in vec2 uv;
out vec4 fragColor;
void main() { fragColor = texture(displayTex, uv); }
"""


def make_texture(w, h, linear=True):
	tex = osg.Texture2D()
	tex.size = (w, h)
	tex.internalFormat = GL_RGBA16F
	tex.filter = (osg.Texture.LINEAR if linear else osg.Texture.NEAREST,) * 2
	tex.wrap = (osg.Texture.CLAMP_TO_EDGE, osg.Texture.CLAMP_TO_EDGE)
	tex.dataVariance = osg.Object.DYNAMIC
	return tex


def make_quad():
	g = osg.Geode()
	g.drawables.append(osg.createTexturedQuadGeometry(
		osg.Vec3(-1, -1, -1), osg.Vec3(2, 0, 0), osg.Vec3(0, 2, 0)
	))
	return g


def program(name, vertex, fragment):
	return osg.Program(name=name, shaders=(
		osg.Shader(osg.Shader.VERTEX, vertex),
		osg.Shader(osg.Shader.FRAGMENT, fragment),
	))


def create_scene():
	# Thin boxes make sub-pixel edges easy to inspect (orbit slightly to make them
	# diagonal); the sphere supplies a smooth curved edge. All geometry is static
	# because motion is Layer 2/3 work.
	root = osg.Group()
	geode = osg.Geode()
	geode.drawables.extend((
		osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 4, 0), 2.0)),
		osg.ShapeDrawable(osg.Box(osg.Vec3(-2.7, 4, 0), 0.12, 7.0, 0.12)),
		osg.ShapeDrawable(osg.Box(osg.Vec3( 2.7, 4, 0), 0.12, 7.0, 0.12)),
	))
	root.children.append(geode)
	root.stateSet.setAttributeAndModes(program("taa_scene", SCENE_VERTEX, GBUFFER_FRAGMENT))
	return root


def create_gbuffer(scene):
	color = make_texture(W, H)
	normal = make_texture(W, H, False)
	depth = osg.Texture2D()
	depth.size = (W, H)
	depth.internalFormat = GL_DEPTH_COMPONENT24
	depth.sourceFormat = GL_DEPTH_COMPONENT
	depth.sourceType = GL_FLOAT
	depth.filter = (osg.Texture.NEAREST, osg.Texture.NEAREST)
	depth.dataVariance = osg.Object.DYNAMIC

	cam = osg.Camera()
	cam.name = "TAA jittered G-buffer"
	cam.renderOrder = (osg.Camera.PRE_RENDER, 0)
	cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	cam.clearMask = GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT
	cam.clearColor = osg.Vec4(0, 0, 0, 0)
	cam.viewport = osg.Viewport(0, 0, W, H)
	cam.attach(osg.Camera.COLOR_BUFFER0, color)
	cam.attach(osg.Camera.COLOR_BUFFER1, normal)
	cam.attach(osg.Camera.DEPTH_BUFFER, depth)
	cam.children.append(scene)
	return cam, color, normal, depth


def fullscreen_rtt(name, order, output, inputs, fragment, uniforms=()):
	cam = osg.Camera()
	cam.name = name
	cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	cam.renderOrder = (osg.Camera.PRE_RENDER, order)
	cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	cam.clearMask = GL_COLOR_BUFFER_BIT
	cam.clearColor = osg.Vec4(0, 0, 0, 1)
	cam.viewport = osg.Viewport(0, 0, W, H)
	cam.projectionMatrix = osg.Matrix.identity()
	cam.viewMatrix = osg.Matrix.identity()
	cam.allowEventFocus = False
	cam.attach(osg.Camera.COLOR_BUFFER0, output)
	cam.stateSet.setMode(GL_DEPTH_TEST, osg.StateAttribute.OFF | osg.StateAttribute.OVERRIDE)
	for unit, (texture, uniform_name) in enumerate(inputs):
		cam.stateSet.textureAttributes[unit] = texture
		cam.stateSet.uniforms[uniform_name] = unit
	cam.stateSet.uniforms.extend(uniforms)
	quad = make_quad()
	quad.stateSet.setAttributeAndModes(program(name, FULLSCREEN_VERTEX, fragment))
	cam.children.append(quad)
	return cam


def display_camera(name, texture):
	cam = osg.Camera()
	cam.name = name
	cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	cam.renderOrder = osg.Camera.POST_RENDER
	cam.clearMask = 0
	cam.projectionMatrix = osg.Matrix.identity()
	cam.viewMatrix = osg.Matrix.identity()
	cam.allowEventFocus = False
	cam.stateSet.setMode(GL_DEPTH_TEST, osg.StateAttribute.OFF | osg.StateAttribute.OVERRIDE)
	cam.stateSet.textureAttributes[0] = texture
	cam.stateSet.uniforms["displayTex"] = 0
	quad = make_quad()
	quad.stateSet.setAttributeAndModes(program(name, FULLSCREEN_VERTEX, DISPLAY_FRAGMENT))
	cam.children.append(quad)
	return cam


def halton(index, base):
	result = 0.0
	fraction = 1.0
	while index:
		fraction /= base
		result += fraction * (index % base)
		index //= base
	return result


class Controls(osgGA.GUIEventHandler):
	def __init__(self, state):
		super().__init__()
		self.state = state

	def handle(self, ea, aa):
		# Any manipulator input invalidates same-pixel history. Reprojection would
		# preserve it, but that is precisely the omitted Layer 2.
		if ea.type in (
			osgGA.GUIEventAdapter.PUSH, osgGA.GUIEventAdapter.DRAG,
			osgGA.GUIEventAdapter.RELEASE, osgGA.GUIEventAdapter.SCROLL,
		):
			self.state["reset"] = True
			self.state["reset_reason"] = "camera input"

		if ea.type in (osgGA.GUIEventAdapter.PUSH, osgGA.GUIEventAdapter.DRAG):
			if not self.state["camera_moving"]:
				print("camera motion started", flush=True)
			self.state["camera_moving"] = True
		elif ea.type == osgGA.GUIEventAdapter.RELEASE:
			if self.state["camera_moving"]:
				print("camera motion stopped", flush=True)
			self.state["camera_moving"] = False

		if ea.type != osgGA.GUIEventAdapter.KEYUP:
			return False
		if ea.key == ord("0"):
			self.state["mode"] = 0
			self.state["reset_reason"] = "display mode changed"
		elif ea.key == ord("1"):
			self.state["mode"] = 1
			self.state["reset_reason"] = "display mode changed"
		elif ea.key == ord("2"):
			self.state["mode"] = 2
			self.state["reset_reason"] = "display mode changed"
		elif ea.key in (ord("r"), ord("R")):
			self.state["reset"] = True
			self.state["reset_reason"] = "manual reset"
		else:
			return False
		self.state["reset"] = True
		return True


if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	current = make_texture(W, H)
	history_a = make_texture(W, H)
	history_b = make_texture(W, H)
	history_weight_a = osg.Uniform("historyWeight", 0.0)
	history_weight_b = osg.Uniform("historyWeight", 0.0)

	gbuffer, color, normal, depth = create_gbuffer(create_scene())
	shade = fullscreen_rtt(
		"Deferred shading", 1, current,
		((color, "colorTex"), (normal, "normalTex")), SHADE_FRAGMENT,
	)
	# A->B and B->A are structurally identical but never enabled together.
	resolve_ab = fullscreen_rtt(
		"TAA A to B", 2, history_b,
		((current, "currentTex"), (history_a, "historyTex")), TAA_FRAGMENT,
		(history_weight_a,),
	)
	resolve_ba = fullscreen_rtt(
		"TAA B to A", 2, history_a,
		((current, "currentTex"), (history_b, "historyTex")), TAA_FRAGMENT,
		(history_weight_b,),
	)
	display_current = display_camera("Display current", current)
	display_a = display_camera("Display history A", history_a)
	display_b = display_camera("Display history B", history_b)

	root = osg.Group()
	root.children.extend((
		gbuffer, shade, resolve_ab, resolve_ba,
		display_current, display_a, display_b,
	))

	viewer = osgViewer.Viewer()
	viewer.sceneData = root
	viewer.cameraManipulator = osgGA.TrackballManipulator()
	state = {
		"mode": 0,
		"reset": True,
		"reset_reason": "startup",
		"sample": 0,
		"write_b": True,
		"sequence_index": None,
		"jitter": None,
		"history_weight": 0.0,
		"history_weights": (0.0, 0.0),
		"camera_moving": False,
	}
	viewer.eventHandlers.append(Controls(state))

	def prepare_frame():
		if state["reset"]:
			print(f"history reset: {state['reset_reason']}", flush=True)
			state["sample"] = 0
			state["reset"] = False

		sequence_index = state["sample"] % HISTORY_LENGTH + 1
		jx = halton(sequence_index, 2) - 0.5
		jy = halton(sequence_index, 3) - 0.5
		jitter_scale = 12.0 if state["mode"] == 2 else 1.0
		state["sequence_index"] = sequence_index
		state["jitter"] = (jx, jy)
		# This camera is RELATIVE_RF: its tiny projection translation is composed
		# with the viewer camera's real projection during cull traversal.
		gbuffer.projectionMatrix = osg.Matrix.translate(
			2.0 * jx * jitter_scale / W,
			2.0 * jy * jitter_scale / H,
			0.0,
		)

		weight = min(state["sample"], HISTORY_LENGTH - 1) / float(
			min(state["sample"], HISTORY_LENGTH - 1) + 1
		)
		history_weight_a.value = weight
		history_weight_b.value = weight
		state["history_weight"] = weight
		state["history_weights"] = (
			history_weight_a.value, history_weight_b.value,
		)

		show_current = state["mode"] != 0
		display_current.nodeMask = 0xFFFFFFFF if show_current else 0
		if state["write_b"]:
			resolve_ab.nodeMask = 0xFFFFFFFF
			resolve_ba.nodeMask = 0
			display_b.nodeMask = 0 if show_current else 0xFFFFFFFF
			display_a.nodeMask = 0
		else:
			resolve_ab.nodeMask = 0
			resolve_ba.nodeMask = 0xFFFFFFFF
			display_a.nodeMask = 0 if show_current else 0xFFFFFFFF
			display_b.nodeMask = 0


	def after_frame():
		state["write_b"] = not state["write_b"]
		state["sample"] += 1
		if state["sample"] == 1:
			print("accumulation started", flush=True)
		elif state["sample"] == HISTORY_LENGTH:
			print(f"accumulation converged at sample {HISTORY_LENGTH}", flush=True)
		prepare_frame()

	def reset_history(reason="interactive request"):
		"""Reset accumulation now, ready for the next manual or continuous frame."""
		state["reset"] = True
		state["reset_reason"] = reason
		prepare_frame()

	prepare_frame()
	print("0=TAA  1=current frame  2=exaggerated jitter  R=reset", flush=True)
	controller = pyosg_repl.repl(viewer, globals(), after_frame)
