#!/usr/bin/env python3
#vimrun! ../examples/pyosg-mrt.py

# MRT (Multiple Render Targets) proof-of-concept.
#
# pyosg-rtt.py proves COLOR_BUFFER + DEPTH_BUFFER -- two different attachment
# *types*, one color slot. pyosg-blur.py proves chained multi-pass (several
# separate single-output passes feeding each other). Neither proves the thing
# a deferred G-buffer actually needs: ONE geometry pass writing to MULTIPLE
# color attachments SIMULTANEOUSLY (COLOR_BUFFER0 + COLOR_BUFFER1) from a
# single shader invocation per pixel, via GLSL `layout(location = n) out`.
#
# This example proves that, then goes one step further and actually USES the
# extra normal buffer: the toon lighting from pyosg-rtt.py's scene shader is
# moved OUT of the geometry pass entirely (deferred) into the composite pass,
# computed from the color+normal+depth G-buffer instead -- the same shape
# Step 11 of the lighting-class series (see ai/context-todo-lighting-class.md)
# will need for its SSAO/SSR post-processing stack. The composite outline is
# also upgraded to combine depth-edge AND normal-edge detection (silhouette
# vs. crease/grazing-angle edges), which is measurably more robust than
# pyosg-rtt.py's depth-only Sobel-ish outline.
#
# Press 1/2/3 to visualize the raw color/depth/normal G-buffer channels;
# press 0 to return to the deferred-lit composite (the default).

import os
import sys

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6"
})

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

W, H = 800, 600

# --------------------------------------------------------------------------- #
# Shaders
# --------------------------------------------------------------------------- #

SCENE_VERTEX_SHADER = """
#version 330 core

in vec4 osg_Vertex;
in vec4 osg_Color;
in vec3 osg_Normal;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat3 osg_NormalMatrix;

out vec4 vColor;
out vec3 vNormal;

void main() {
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vColor = osg_Color;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

# G-buffer write pass: NO lighting happens here at all -- just raw albedo and
# view-space normal, written to two color attachments SIMULTANEOUSLY (true
# MRT, via the two `layout(location = n) out` declarations below). Depth
# comes "for free" from this camera's own DEPTH_BUFFER attachment/z-test.
GBUFFER_FRAGMENT_SHADER = """
#version 330 core

in vec4 vColor;
in vec3 vNormal;

layout(location = 0) out vec4 outColor;   // COLOR_BUFFER0: unlit albedo
layout(location = 1) out vec4 outNormal;  // COLOR_BUFFER1: view-space normal

void main() {
	outColor = vColor;
	outNormal = vec4(normalize(vNormal), 1.0);
}
"""

FULLSCREEN_VERTEX_SHADER = """
#version 330 core

in vec4 osg_Vertex;
in vec2 osg_MultiTexCoord0;

out vec2 uv;

void main() {
	uv = osg_MultiTexCoord0;
	gl_Position = osg_Vertex;
}
"""

# Deferred composite: reads the G-buffer (color/normal/depth) back and does
# ALL of the actual lighting HERE instead of in the geometry pass -- the same
# cel-shaded diffuse + rim light as pyosg-rtt.py, just computed from the
# G-buffer instead of inline per-vertex/per-fragment during the geometry
# pass. View-space position is reconstructed from depth + the inverse
# projection matrix (the same reconstruction technique a real SSAO/SSR pass
# needs the depth buffer for).
COMPOSITE_FRAGMENT_SHADER = """
#version 330 core

uniform sampler2D colorTex;
uniform sampler2D normalTex;
uniform sampler2D depthTex;
uniform mat4 invProjectionMatrix;
uniform float znear;
uniform float zfar;
uniform int visualizeMode; // 0=lit composite, 1=color, 2=depth, 3=normal

in vec2 uv;

out vec4 fragColor;

// Convert depth buffer value -> camera-space Z distance.
float linearizeDepth(float d, float near, float far) {
	float z = d * 2.0 - 1.0;

	return (2.0 * near * far) / (far + near - z * (far - near));
}

// Reconstruct view-space position from a screen UV + depth-buffer sample.
vec3 reconstructViewPos(vec2 uv, float d) {
	vec4 clip = vec4(vec3(uv, d) * 2.0 - 1.0, 1.0);
	vec4 viewPos = invProjectionMatrix * clip;

	return viewPos.xyz / viewPos.w;
}

void main() {
	vec4 albedo = texture(colorTex, uv);
	vec3 rawNormal = texture(normalTex, uv).rgb;
	float d = texture(depthTex, uv).r;

	// --- Raw G-buffer visualize modes (bypass lighting entirely) -------- //
	if (visualizeMode == 1) {
		fragColor = albedo;

		return;
	}

	if (visualizeMode == 2) {
		float lin = linearizeDepth(d, znear, zfar);
		float t = clamp((lin - znear) / (zfar - znear), 0.0, 1.0);

		fragColor = vec4(vec3(t), 1.0);

		return;
	}

	if (visualizeMode == 3) {
		// Raw (unnormalized) sample -- background pixels the G-buffer pass
		// never touched read back as (0,0,0) -> mid-gray here, which is a
		// harmless "no data" tell rather than a NaN from normalizing a zero
		// vector.
		fragColor = vec4(rawNormal * 0.5 + 0.5, 1.0);

		return;
	}

	// --- Deferred lit composite (default) -------------------------------- //
	// A cleared-but-never-written background pixel has a zero-length normal
	// (real written normals are always unit length) -- use that as a sentinel
	// for "no geometry here" instead of trusting the color clear value, which
	// would otherwise get relit as if it were a real (very dark) surface.
	if (dot(rawNormal, rawNormal) < 0.0001) {
		fragColor = vec4(0.1, 0.5, 0.2, 1.0); // same green as pyosg-rtt.py's clear color

		return;
	}

	vec3 N = normalize(rawNormal);

	const vec3 L = vec3(0.268, 0.358, 0.894);
	const vec3 rimColor = vec3(0.9, 0.6, 0.0);
	const float rimPower = 5.0;
	const float rimBase = 0.3;
	const float rimTint = 0.4;

	float diffuse = max(dot(N, L), 0.0);
	diffuse = floor(diffuse * 3.0) / 3.0;

	float ambient = 0.25;
	float light = ambient + diffuse;

	vec3 viewPos = reconstructViewPos(uv, d);
	vec3 viewDir = normalize(-viewPos);
	float rim = pow(1.0 - clamp(dot(N, viewDir), 0.0, 1.0), rimPower);
	vec3 rimLight = rim * (vec3(rimBase) + rimColor * rimTint);

	vec3 color = albedo.rgb * light + rimLight;

	// --- Combined depth-edge + normal-edge outline ----------------------- //
	// Depth-edge alone (pyosg-rtt.py's original technique) catches silhouette
	// edges where geometry meets background/other geometry, but misses edges
	// where depth barely changes yet the surface is turning sharply (grazing
	// angles, or two coplanar-ish faces meeting at a crease) -- normal-edge
	// catches exactly those. Neighbor normal taps are deliberately left
	// UNnormalized: a background neighbor's zero vector then contributes a
	// clean "maximum edge" via dot(N, vec3(0)) == 0, with no normalize(0) NaN
	// risk, which conveniently reinforces the silhouette outline for free.
	vec2 texel = 1.0 / vec2(textureSize(depthTex, 0));

	float dL = texture(depthTex, uv + vec2(-texel.x, 0.0)).r;
	float dR = texture(depthTex, uv + vec2( texel.x, 0.0)).r;
	float dU = texture(depthTex, uv + vec2(0.0, texel.y)).r;
	float dD = texture(depthTex, uv + vec2(0.0, -texel.y)).r;

	float z  = linearizeDepth(d,  znear, zfar);
	float zL = linearizeDepth(dL, znear, zfar);
	float zR = linearizeDepth(dR, znear, zfar);
	float zU = linearizeDepth(dU, znear, zfar);
	float zD = linearizeDepth(dD, znear, zfar);

	float edgeH = abs(zL - zR);
	float edgeV = abs(zU - zD);
	float depthEdge = sqrt(edgeH * edgeH + edgeV * edgeV);
	float depthThreshold = z * 0.03;
	float depthOutline = smoothstep(depthThreshold * 0.5, depthThreshold * 1.5, depthEdge);

	vec3 nL = texture(normalTex, uv + vec2(-texel.x, 0.0)).rgb;
	vec3 nR = texture(normalTex, uv + vec2( texel.x, 0.0)).rgb;
	vec3 nU = texture(normalTex, uv + vec2(0.0, texel.y)).rgb;
	vec3 nD = texture(normalTex, uv + vec2(0.0, -texel.y)).rgb;

	float normalEdge = (1.0 - dot(N, nL)) + (1.0 - dot(N, nR)) + (1.0 - dot(N, nU)) + (1.0 - dot(N, nD));
	float normalOutline = smoothstep(0.05, 0.3, normalEdge);

	float outline = max(depthOutline, normalOutline);

	color = mix(color, vec3(0.0), outline);

	fragColor = vec4(color, 1.0);
}
"""

# --------------------------------------------------------------------------- #
# Scene / camera setup
# --------------------------------------------------------------------------- #

# Same four spheres as pyosg-rtt.py -- this example is about proving/using
# MRT, not about the scene content, so keep that constant for a fair
# comparison against the existing example.
def create_scene():
	g = None

	if len(sys.argv) >= 2:
		g = osgDB.readNodeFile(sys.argv[1])

	else:
		g = osg.Geode(drawables=(
			osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 2.0, 0), 1.0)),
			osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 5.0, 0), 1.5)),
			osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 8.0, 0), 2.0)),
			osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 12.0, 0), 3.0))
		))

	p = osg.Program(name="gbufferProgram", shaders=(
		osg.Shader(osg.Shader.VERTEX, SCENE_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, GBUFFER_FRAGMENT_SHADER)
	))

	g.stateSet.setAttributeAndModes(p)

	return g

# Creates the G-buffer RTT camera: THREE simultaneous attachments (color,
# normal, depth) from one geometry pass. Returns the camera plus all three
# `Texture` instances, which the composite HUD camera samples from directly.
def create_gbuffer_camera(w=W, h=H):
	color_tex = osg.Texture2D()
	color_tex.size = (w, h)
	color_tex.internalFormat = GL_RGBA
	color_tex.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)

	# Float format so signed [-1, 1] normal components need no encode/decode
	# remap -- same convention as the lighting-class series (env_tex/cube_tex/
	# prefilter_tex all use GL_RGB16F for the same reason).
	normal_tex = osg.Texture2D()
	normal_tex.size = (w, h)
	normal_tex.internalFormat = GL_RGB16F
	normal_tex.filter = (osg.Texture.NEAREST, osg.Texture.NEAREST)

	depth_tex = osg.Texture2D()
	depth_tex.size = (w, h)
	depth_tex.internalFormat = GL_DEPTH_COMPONENT24
	depth_tex.sourceFormat = GL_DEPTH_COMPONENT
	depth_tex.sourceType = GL_FLOAT
	depth_tex.filter = (osg.Texture.NEAREST, osg.Texture.NEAREST)

	cam = osg.Camera()
	cam.renderOrder = osg.Camera.PRE_RENDER
	cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	cam.clearMask = GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT
	cam.clearColor = osg.Vec4(0.0, 0.0, 0.0, 0.0)
	cam.viewport = osg.Viewport(0, 0, w, h)
	cam.name = "G-Buffer Camera"

	# True MRT: two SIMULTANEOUS color attachments from a single geometry
	# pass, plus depth -- the thing neither pyosg-rtt.py (COLOR+DEPTH, one
	# color slot) nor pyosg-blur.py (chained single-output passes) proves.
	cam.attach(osg.Camera.COLOR_BUFFER0, color_tex)
	cam.attach(osg.Camera.COLOR_BUFFER1, normal_tex)
	cam.attach(osg.Camera.DEPTH_BUFFER, depth_tex)

	return cam, color_tex, normal_tex, depth_tex

# Creates the composite/HUD camera: samples all three G-buffer textures and
# either runs the deferred toon-lighting pass or dumps one raw buffer to the
# screen, depending on `visualizeMode` (see VisualizeModeHandler below).
def create_hud_camera(color_tex, normal_tex, depth_tex):
	cam = osg.Camera()
	cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	cam.renderOrder = osg.Camera.POST_RENDER
	cam.clearMask = 0
	cam.allowEventFocus = False
	cam.projectionMatrix = osg.Matrix.identity()
	cam.viewMatrix = osg.Matrix.identity()
	cam.name = "Composite HUD"

	g = osg.Geode()
	g.drawables.append(osg.createTexturedQuadGeometry(
		osg.Vec3(-1.0, -1.0, -1.0),
		osg.Vec3(2.0, 0.0, 0.0),
		osg.Vec3(0.0, 2.0, 0.0)
	))

	cam.children.append(g)

	cam.stateSet.textureAttributes[0] = color_tex
	cam.stateSet.textureAttributes[1] = normal_tex
	cam.stateSet.textureAttributes[2] = depth_tex

	cam.stateSet.uniforms["colorTex"] = 0
	cam.stateSet.uniforms["normalTex"] = 1
	cam.stateSet.uniforms["depthTex"] = 2

	p = osg.Program(name="compositeProgram", shaders=(
		osg.Shader(osg.Shader.VERTEX, FULLSCREEN_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, COMPOSITE_FRAGMENT_SHADER)
	))

	g.stateSet.setAttributeAndModes(p)

	return cam

# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #

class VisualizeModeHandler(osgGA.GUIEventHandler):
	"""Press 1/2/3 to visualize the raw color/depth/normal G-buffer channels; 0 for the lit composite."""

	def __init__(self, mode_uniform):
		super().__init__()
		self.mode_uniform = mode_uniform

	def handle(self, ea, aa):
		if ea.handled or ea.type != osgGA.GUIEventAdapter.KEYUP:
			return False

		if ea.key == ord("0"):
			self.mode_uniform.value = 0
		elif ea.key == ord("1"):
			self.mode_uniform.value = 1
		elif ea.key == ord("2"):
			self.mode_uniform.value = 2
		elif ea.key == ord("3"):
			self.mode_uniform.value = 3
		else:
			return False

		return True

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	v = osgViewer.Viewer()
	r = osg.Group()

	gbuffer_cam, color_tex, normal_tex, depth_tex = create_gbuffer_camera(W, H)
	hud_cam = create_hud_camera(color_tex, normal_tex, depth_tex)

	gbuffer_cam.children.append(create_scene())

	r.children.extend((gbuffer_cam, hud_cam))

	znear_u = osg.Uniform("znear", 0.0)
	zfar_u = osg.Uniform("zfar", 0.0)
	inv_proj_u = osg.Uniform("invProjectionMatrix", osg.Matrixf.identity())
	visualize_mode_u = osg.Uniform("visualizeMode", 0)

	hud_cam.stateSet.uniforms.extend((znear_u, zfar_u, inv_proj_u, visualize_mode_u))

	# Same idea as pyosg-rtt.py's update_uniforms: OSG recomputes znear/zfar
	# every frame based on the CameraManipulator, so depth linearization and
	# view-space reconstruction both need fresh values every frame, not just
	# at startup.
	def update_uniforms(ri):
		pm = ri.state.projectionMatrix
		fovy, aspect, near, far = pm.getPerspective()

		znear_u.value = float(near)
		zfar_u.value = float(far)
		inv_proj_u.value = osg.Matrixf(osg.Matrix.inverse(pm))

	v.sceneData = r
	v.cameraManipulator = osgGA.TrackballManipulator()
	v.camera.preDrawCallback = update_uniforms
	v.eventHandlers.append(VisualizeModeHandler(visualize_mode_u))

	print("Press 1=color 2=depth 3=normal 0=lit composite (default)", flush=True)

	while not v.done:
		v.frame()
