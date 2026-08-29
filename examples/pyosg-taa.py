#!/usr/bin/env python3

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

# Import side effect: fills in OSG_WINDOW/OSG_THREADING/OSG_GL_* env var defaults (see
# pyosg_example.py). Deliberately before `from OpenSceneGraph import *`, matching every other
# example -- these need to land before OSG's DisplaySettings reads them.
from pyosg_example import window_size

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

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
	tex = osg.Texture2D(
		size=(w, h),
		internalFormat=GL_RGBA16F,
		filter=(osg.Texture.LINEAR if linear else osg.Texture.NEAREST,) * 2,
		wrap=(osg.Texture.CLAMP_TO_EDGE, osg.Texture.CLAMP_TO_EDGE),
		dataVariance=osg.Object.DYNAMIC,
	)
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
	root.stateSet.attributes.append(program("taa_scene", SCENE_VERTEX, GBUFFER_FRAGMENT))
	return root


def create_gbuffer(scene, w, h):
	color = make_texture(w, h)
	normal = make_texture(w, h, False)
	depth = osg.Texture2D(
		size=(w, h),
		internalFormat=GL_DEPTH_COMPONENT24,
		sourceFormat=GL_DEPTH_COMPONENT,
		sourceType=GL_FLOAT,
		filter=(osg.Texture.NEAREST, osg.Texture.NEAREST),
		dataVariance=osg.Object.DYNAMIC,
	)

	cam = osg.Camera(
		name="TAA jittered G-buffer",
		renderOrder=(osg.Camera.PRE_RENDER, 0),
		renderTargetImplementation=osg.Camera.FRAME_BUFFER_OBJECT,
		clearMask=GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT,
		clearColor=osg.Vec4(0, 0, 0, 0),
		viewport=osg.Viewport(0, 0, w, h),
	)
	cam.attach(osg.Camera.COLOR_BUFFER0, color)
	cam.attach(osg.Camera.COLOR_BUFFER1, normal)
	cam.attach(osg.Camera.DEPTH_BUFFER, depth)
	cam.children.append(scene)
	return cam, color, normal, depth


def fullscreen_rtt(name, order, output, inputs, fragment, w, h, uniforms=()):
	cam = osg.Camera(
		name=name,
		referenceFrame=osg.Transform.ABSOLUTE_RF,
		renderOrder=(osg.Camera.PRE_RENDER, order),
		renderTargetImplementation=osg.Camera.FRAME_BUFFER_OBJECT,
		clearMask=GL_COLOR_BUFFER_BIT,
		clearColor=osg.Vec4(0, 0, 0, 1),
		viewport=osg.Viewport(0, 0, w, h),
		projectionMatrix=osg.Matrix.identity(),
		viewMatrix=osg.Matrix.identity(),
		allowEventFocus=False,
	)
	cam.attach(osg.Camera.COLOR_BUFFER0, output)
	cam.stateSet.modes[GL_DEPTH_TEST] = osg.StateAttribute.OFF | osg.StateAttribute.OVERRIDE
	for unit, (texture, uniform_name) in enumerate(inputs):
		cam.stateSet.textureAttributes[unit] = texture
		cam.stateSet.uniforms[uniform_name] = unit
	cam.stateSet.uniforms.extend(uniforms)
	quad = make_quad()
	quad.stateSet.attributes.append(program(name, FULLSCREEN_VERTEX, fragment))
	cam.children.append(quad)
	return cam


def display_camera(name, texture):
	cam = osg.Camera(
		name=name,
		referenceFrame=osg.Transform.ABSOLUTE_RF,
		renderOrder=osg.Camera.POST_RENDER,
		clearMask=0,
		projectionMatrix=osg.Matrix.identity(),
		viewMatrix=osg.Matrix.identity(),
		allowEventFocus=False,
	)
	cam.stateSet.modes[GL_DEPTH_TEST] = osg.StateAttribute.OFF | osg.StateAttribute.OVERRIDE
	cam.stateSet.textureAttributes[0] = texture
	cam.stateSet.uniforms["displayTex"] = 0
	quad = make_quad()
	quad.stateSet.attributes.append(program(name, FULLSCREEN_VERTEX, DISPLAY_FRAGMENT))
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
	"""Drives the whole TAA state machine (jitter/history-swap/weight-ramp) off the
	FRAME event, which osgGA dispatches to every registered handler once per
	viewer.frame() call -- this is what lets a plain `while not viewer.done:
	viewer.frame()` loop (runner-driven or standalone) work here at all, instead of
	requiring pyosg_repl.repl() to drive the loop itself and call back in
	(the original shape this file had, before build_scene()/configure_viewer())."""

	def __init__(self, gbuffer, resolve_ab, resolve_ba, display_current, display_a, display_b,
			history_weight_a, history_weight_b):
		super().__init__()

		self.gbuffer = gbuffer
		self.resolve_ab = resolve_ab
		self.resolve_ba = resolve_ba
		self.display_current = display_current
		self.display_a = display_a
		self.display_b = display_b
		self.history_weight_a = history_weight_a
		self.history_weight_b = history_weight_b

		self.w = int(gbuffer.viewport.width)
		self.h = int(gbuffer.viewport.height)

		self.state = {
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

		# The FIRST FRAME event must render with THIS prepared state, not an already-advanced
		# one -- see the FRAME branch in handle() below.
		self._primed = False

		self.prepare_frame()

		print("0=TAA  1=current frame  2=exaggerated jitter  R=reset", flush=True)

	def prepare_frame(self):
		state = self.state

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
		self.gbuffer.projectionMatrix = osg.Matrix.translate(
			2.0 * jx * jitter_scale / self.w,
			2.0 * jy * jitter_scale / self.h,
			0.0,
		)

		weight = min(state["sample"], HISTORY_LENGTH - 1) / float(
			min(state["sample"], HISTORY_LENGTH - 1) + 1
		)
		self.history_weight_a.value = weight
		self.history_weight_b.value = weight
		state["history_weight"] = weight
		state["history_weights"] = (
			self.history_weight_a.value, self.history_weight_b.value,
		)

		show_current = state["mode"] != 0
		self.display_current.nodeMask = 0xFFFFFFFF if show_current else 0
		if state["write_b"]:
			self.resolve_ab.nodeMask = 0xFFFFFFFF
			self.resolve_ba.nodeMask = 0
			self.display_b.nodeMask = 0 if show_current else 0xFFFFFFFF
			self.display_a.nodeMask = 0
		else:
			self.resolve_ab.nodeMask = 0
			self.resolve_ba.nodeMask = 0xFFFFFFFF
			self.display_a.nodeMask = 0 if show_current else 0xFFFFFFFF
			self.display_b.nodeMask = 0

	def advance(self):
		state = self.state

		state["write_b"] = not state["write_b"]
		state["sample"] += 1
		if state["sample"] == 1:
			print("accumulation started", flush=True)
		elif state["sample"] == HISTORY_LENGTH:
			print(f"accumulation converged at sample {HISTORY_LENGTH}", flush=True)
		self.prepare_frame()

	def reset_history(self, reason="interactive request"):
		"""Reset accumulation now, ready for the next FRAME event."""
		self.state["reset"] = True
		self.state["reset_reason"] = reason
		self.prepare_frame()

	def handle(self, ea, aa):
		if ea.type == osgGA.GUIEventAdapter.FRAME:
			# __init__ already prepared frame 0 -- only ADVANCE (bump sample, swap
			# history buffers) for every frame after that.
			if self._primed:
				self.advance()

			else:
				self._primed = True

			return False

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


# The real pipeline-assembly entrypoint -- returns the root Node, no viewer/window side effects.
# The seven RTT/display cameras are appended to root.children in a fixed order (gbuffer, shade,
# resolve_ab, resolve_ba, display_current, display_a, display_b); configure_viewer() unpacks them
# back out in that same order, the same "recover state from the graph instead of a module-level
# stash" idea as pyosg-mrt.py's Uniform recovery.
def build_scene(w, h):
	current = make_texture(w, h)
	history_a = make_texture(w, h)
	history_b = make_texture(w, h)
	history_weight_a = osg.Uniform("historyWeight", 0.0)
	history_weight_b = osg.Uniform("historyWeight", 0.0)

	gbuffer, color, normal, depth = create_gbuffer(create_scene(), w, h)
	shade = fullscreen_rtt(
		"Deferred shading", 1, current,
		((color, "colorTex"), (normal, "normalTex")), SHADE_FRAGMENT, w, h,
	)
	# A->B and B->A are structurally identical but never enabled together.
	resolve_ab = fullscreen_rtt(
		"TAA A to B", 2, history_b,
		((current, "currentTex"), (history_a, "historyTex")), TAA_FRAGMENT, w, h,
		(history_weight_a,),
	)
	resolve_ba = fullscreen_rtt(
		"TAA B to A", 2, history_a,
		((current, "currentTex"), (history_b, "historyTex")), TAA_FRAGMENT, w, h,
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

	return root

# Controls needs the live viewer to register as an event handler, which build_scene() never
# receives.
def configure_viewer(viewer, root):
	gbuffer, shade, resolve_ab, resolve_ba, display_current, display_a, display_b = root.children
	history_weight_a = resolve_ab.stateSet.uniforms["historyWeight"]
	history_weight_b = resolve_ba.stateSet.uniforms["historyWeight"]

	viewer.eventHandlers.append(Controls(
		gbuffer, resolve_ab, resolve_ba, display_current, display_a, display_b,
		history_weight_a, history_weight_b,
	))

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	W, H = window_size()

	viewer = osgViewer.Viewer()
	root = build_scene(W, H)

	viewer.sceneData = root
	viewer.cameraManipulator = osgGA.TrackballManipulator()

	configure_viewer(viewer, root)

	while not viewer.done:
		viewer.frame()
