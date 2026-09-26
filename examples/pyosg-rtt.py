#!/usr/bin/env python3

import os

os.environ.setdefault("OSG_WINDOW", "50 50 800 600")

# Shared example defaults: SingleThreaded, the GL 4.6 core-profile context, and the osgx.Library
# that osgx.resolveShaderLibs() below requires.
import pyosg_example

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

SCENE_VERTEX_SHADER = """
#version 330 core

in vec4 osg_Vertex;
in vec4 osg_Color;
in vec3 osg_Normal;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat4 osg_ProjectionMatrix;
uniform mat3 osg_NormalMatrix;

out vec4 vColor;
out vec3 vNormal;
out vec3 vPosition;

void main() {
	vec4 posEye = osg_ModelViewMatrix * osg_Vertex;

	vPosition = posEye.xyz;
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vColor = osg_Color;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

SCENE_FRAGMENT_SHADER = """
#version 330 core

in vec4 vColor;
in vec3 vNormal;
in vec3 vPosition;

out vec4 color;

void main() {
	const vec3 L = vec3(0.268, 0.358, 0.894);
	const vec3 rimColor = vec3(0.9, 0.6, 0.0);
	const float rimPower = 5.0;
	const float rimBase = 0.3;
	const float rimTint = 0.4;

	vec3 N = normalize(vNormal);

	float diffuse = max(dot(N, L), 0.0);
	diffuse = floor(diffuse * 3.0) / 3.0;

	float ambient = 0.25;
	float light = ambient + diffuse;

	vec3 viewDir = normalize(-vPosition);

	float rim = pow(1.0 - clamp(dot(N, viewDir), 0.0, 1.0), rimPower);

	vec3 rimLight = rim * (vec3(rimBase) + rimColor * rimTint);

	color = vec4(vColor.rgb * light + rimLight, vColor.a);
}
"""

HUD_VERTEX_SHADER = """
#version 330 core

in vec4 osg_Vertex;
in vec2 osg_MultiTexCoord0;

out vec2 uv;

void main() {
	uv = osg_MultiTexCoord0;

	gl_Position = osg_Vertex;
}
"""

HUD_FRAGMENT_SHADER = """
#version 330 core

// osgx_LinearizeDepth(depth, projection): depth buffer value -> camera-space Z distance.
#pragma osgx::projection DEPTH

uniform sampler2D colorTex;
uniform sampler2D depthTex;

// The projection the RTT camera actually rendered its depth with (see build_scene()).
uniform mat4 osgx_depthProjection;

in vec2 uv;

out vec4 color;

void main() {
	vec4 c = texture(colorTex, uv);
	float d = texture(depthTex, uv).r;

	// Texel size for neighbor sampling
	vec2 texel = 4.0 / vec2(800.0, 600.0);

	// Sample depth at 4 neighbors
	float dL = texture(depthTex, uv + vec2(-texel.x, 0.0)).r;
	float dR = texture(depthTex, uv + vec2( texel.x, 0.0)).r;
	float dU = texture(depthTex, uv + vec2(0.0, texel.y)).r;
	float dD = texture(depthTex, uv + vec2(0.0, -texel.y)).r;

	// Linearize them all so edges are consistent across depth range
	float z = osgx_LinearizeDepth(d, osgx_depthProjection);
	float zL = osgx_LinearizeDepth(dL, osgx_depthProjection);
	float zR = osgx_LinearizeDepth(dR, osgx_depthProjection);
	float zU = osgx_LinearizeDepth(dU, osgx_depthProjection);
	float zD = osgx_LinearizeDepth(dD, osgx_depthProjection);

	// Sobel-ish edge detection on linearized depth
	float edgeH = abs(zL - zR);
	float edgeV = abs(zU - zD);
	float edge = sqrt(edgeH * edgeH + edgeV * edgeV);

	// Threshold relative to depth (edges far away need less delta)
	float threshold = z * 0.03;
	float outline = smoothstep(threshold * 0.5, threshold * 1.5, edge);

	// Black outline over scene color
	color = mix(c, vec4(0.0, 0.0, 0.0, 1.0), outline);
}
"""

# Create the actual 3D scene you're interested in manipulating! This function has
# no awareness of an RTT setup; it simply creates the scene and returns it. You
# could, for example, set the returned `Node` as `viewer.sceneData` directly and
# view it OUTSIDE of the RTT pipeline.
def create_scene():
	g = osg.Geode(drawables=(
		osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 2.0, 0), 1.0)),
		osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 5.0, 0), 1.5)),
		osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 8.0, 0), 2.0)),
		osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 12.0, 0), 3.0))
	))

	p = osg.Program(name="sceneProgram")

	# Similar to `Group.children`, MOST THINGS in OSG.py that "behave" like sequences
	# in C++ are wrapped with sequence-like "proxies" in Python (and support all of
	# the official "Sequence Protocol" behaviors a Python programmer would expect)!
	p.shaders.append(osg.Shader(osg.Shader.VERTEX, SCENE_VERTEX_SHADER))
	p.shaders.append(osg.Shader(osg.Shader.FRAGMENT, SCENE_FRAGMENT_SHADER))

	g.stateSet.attributes.append(p)

	return g

# Create the RTT (Render To Texture) `Camera` instance using the specified width/height
# dimensions. Any children attached to this instance will be rendered using the attached
# color buffer and depth buffers, which we will later query in a secondary "HUD" `Camera`.
#
# NOTE: In addition to the `Camera`, this function also returns the color/depth buffer
# `Texture` instances, which the "HUD" will need in order to directly "sample" from them
# in its own shader pipeline.
def create_rtt_camera(w=512, h=512):
	cb = osg.Texture2D()
	db = osg.Texture2D()

	cb.size = (w, h)
	cb.internalFormat = GL_RGBA
	cb.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)

	db.size = (w, h)
	db.internalFormat = GL_DEPTH_COMPONENT24
	db.sourceFormat = GL_DEPTH_COMPONENT
	db.sourceType = GL_FLOAT
	db.filter = (osg.Texture.NEAREST, osg.Texture.NEAREST)

	# osgx.RTT replaces the four lines every hand-rolled RTT camera used to repeat - PRE_RENDER,
	# FRAME_BUFFER_OBJECT, a viewport matching (w, h), and a reference frame - with one
	# constructor call, plus clearColor/name via the same kwargs support osg.Camera itself has.
	# clearMask is deliberately NOT passed: GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT is already
	# osg.Camera's own default (osg/Camera.cpp's constructor), so restating it is pure boilerplate.
	#
	# RELATIVE_RF here is a deliberate choice, not the "didn't bother" default it might look like:
	# this camera never sets its own view/projection, so it inherits whatever the cull traversal's
	# current matrices are at its position in the scene graph - in this example, that's the SAME
	# live view the interactive viewer is using, diverted into an FBO instead of the backbuffer.
	# Use ABSOLUTE_RF (osgx.RTT's own default) instead when the RTT camera needs a fixed,
	# independent view/projection of its own.
	cam = osgx.RTT(
		w, h, osg.Transform.RELATIVE_RF,
		clearColor=osg.Vec4(0.1, 0.5, 0.2, 1.0),
		name="RTT Camera"
	)

	# One declarative call instead of two - osgx.RTT.attach() takes a list of
	# (component, texture) pairs (same shape as osgx.HookList), attached in order.
	cam.attach([
		(osg.Camera.COLOR_BUFFER, cb),
		(osg.Camera.DEPTH_BUFFER, db)
	])

	return cam, cb, db

# Creates a special "HUD" `Camera` using the specified color/depth `Texture` arguments.
# These types of cameras typically access one or more "sources" (the buffer/texture
# attachments) to "composite" a scene within a screen-aligned, NDC quad. This process
# forms the basis for "Render To Texture", and once your "HUD" `Camera` has access
# to the raw buffers in its shader pipeline (via `sampler2d` or similar in GLSL), all
# kinds of cool techniques open up!
def create_hud_camera(cb, db):
	# NOT an osgx.RTT camera: this one composites onto the real backbuffer (no FBO, no
	# texture attachments of its own) - it's the CONSUMER of the RTT camera's output, not
	# an RTT camera itself. osgx.RTT specifically means "render into a texture"; reaching
	# for it here just because it also builds a fullscreen NDC quad (see osgx.RTT.fullscreenQuad)
	# would be misleading even where it happened to work, since fullscreenQuad() returns an
	# RTT camera already shaped for PRE_RENDER + FRAME_BUFFER_OBJECT.
	#
	# osg.Camera has the SAME kwargs-forwarding constructor osgx.RTT uses (they share the same
	# pybind11x::kwargs_init chain). Only the properties that actually DIFFER from a fresh
	# osg.Camera's own defaults are listed here - renderOrder (already POST_RENDER) and
	# projectionMatrix/viewMatrix (osg.Matrix's own default constructor is already identity)
	# used to be set explicitly below too, but were pure restated boilerplate the whole time.
	cam = osg.Camera(
		referenceFrame=osg.Transform.ABSOLUTE_RF,
		clearMask=0,
		allowEventFocus=False,
		name="HUD Camera"
	)

	g = osg.Geode()

	# We use the OSG helper here, passing in width/height arguments that result in a
	# screen aligned, full-sized NDC ("Normalized Device Coordinates") quad. This is
	# sometimes referred to as "clip space", as well as a handful of other names.
	g.drawables.append(osg.createTexturedQuadGeometry(
		osg.Vec3(-1.0, -1.0, -1.0),
		osg.Vec3(2.0, 0.0, 0.0),
		osg.Vec3(0.0, 2.0, 0.0)
	))

	cam.children.append(g)

	# cam.stateSet.setTextureAttributeAndModes(0, cb)
	# cam.stateSet.setTextureAttributeAndModes(1, db)
	cam.stateSet.textureAttributes[0] = cb
	cam.stateSet.textureAttributes[1] = db

	cam.stateSet.uniforms["colorTex"] = 0
	cam.stateSet.uniforms["depthTex"] = 1

	# Most properties on OSG.py objects can OPTIONALLY be set during creation using
	# keyword arguments; key/value pairs are passed down the entire inheritance chain,
	# and each object's constructor chooses which key/value pairs are appropriate for it.
	p = osg.Program(name="hudProgram", shaders=(
		osg.Shader(osg.Shader.VERTEX, HUD_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, osgx.resolveShaderLibs(HUD_FRAGMENT_SHADER))
	))

	g.stateSet.attributes.append(p)

	return cam

# The real pipeline-assembly entrypoint - returns the root Node, no viewer/window side
# effects. This is what external tooling (e.g. etc/pyside6-glsl.py's shader-editor scaffold,
# ../pyosg-cli) imports and calls directly, so it MUST stay side-effect-free w.r.t. any
# global viewer state. Takes (w, h) explicitly rather than reading module-level constants.
def build_scene(w, h):
	rttCam, cb, db = create_rtt_camera(w, h)
	hudCam = create_hud_camera(cb, db)

	# This is how the RTT camera "knows" what to render...
	rttCam.children.append(create_scene())

	# OSG recomputes each camera's near/far every frame (based on what it culls) so the depth range
	# has as much precision as possible, and it does so on the RTT camera's own private copy of the
	# projection - neither the viewer camera's projectionMatrix nor the HUD camera's own
	# osg_ProjectionMatrix is the matrix the depth was written with. osgx.DepthProjectionCallback,
	# run right after the RTT camera draws, records that exact matrix into a uniform the HUD pass
	# reads (osgx_depthProjection above). MANY post-processing techniques rely on linearizing depth
	# correctly, so it's important to use the projection that actually produced it.
	depth_projection = osgx.DepthProjectionCallback()

	rttCam.postDrawCallback = depth_projection
	hudCam.stateSet.uniforms.append(depth_projection.projection)

	root = osg.Group()
	root.children.extend((rttCam, hudCam))

	return root

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	v = osgViewer.Viewer()

	v.sceneData = build_scene(800, 600)
	v.cameraManipulator = osgGA.TrackballManipulator()

	# You could just call `v.run()`, but it's informative to demonstrate different ways of
	# "driving" the redraw/render process.
	while not v.done:
		v.frame()
